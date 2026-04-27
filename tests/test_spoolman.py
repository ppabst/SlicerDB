# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Spoolman sync: unit tests for the mapper + integration test for the route.

We avoid hitting a real Spoolman by monkey-patching `SpoolmanClient.filaments`
to return canned data. The real client is exercised by the production deploy
on the VM where Spoolman is on the loopback.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import get_engine
from app.models import Filament
from app.services.spoolman import (
    SpoolmanClient,
    _filament_fields_from_spoolman,
    _normalise_hex,
    sync_filaments,
)


def _payload(
    *,
    id_: int,
    name: str,
    vendor: str,
    material: str = "PLA",
    color: str = "000000",
    extruder_temp: int = 200,
    bed_temp: int = 60,
) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "vendor": {"id": 99, "name": vendor},
        "material": material,
        "color_hex": color,
        "settings_extruder_temp": extruder_temp,
        "settings_bed_temp": bed_temp,
    }


def test_normalise_hex_prepends_hash() -> None:
    assert _normalise_hex("ff00ff") == "#ff00ff"
    assert _normalise_hex("#ff00ff") == "#ff00ff"
    assert _normalise_hex("") is None
    assert _normalise_hex(None) is None


def test_filament_fields_from_spoolman() -> None:
    fields = _filament_fields_from_spoolman(
        _payload(id_=1, name="PLA Schwarz", vendor="DEEPLEE", color="000000")
    )
    assert fields["name"] == "PLA Schwarz"
    assert fields["manufacturer"] == "DEEPLEE"
    assert fields["color_hex"] == "#000000"
    # Spoolman's single extruder temp lands in both min and max.
    assert fields["hotend_temp_min"] == fields["hotend_temp_max"] == 200


@pytest.fixture
def fake_spoolman(monkeypatch: pytest.MonkeyPatch):
    """Patches SpoolmanClient.filaments to return a list-driven response."""
    state: dict[str, Any] = {"payloads": [], "calls": 0, "raise": None}

    async def fake_filaments(self):  # type: ignore[no-untyped-def]
        state["calls"] += 1
        if state["raise"] is not None:
            raise state["raise"]
        return state["payloads"]

    monkeypatch.setattr(SpoolmanClient, "filaments", fake_filaments)
    return state


async def test_sync_inserts_then_updates(client: TestClient, fake_spoolman) -> None:
    fake_spoolman["payloads"] = [
        _payload(id_=1, name="PLA Basic Schwarz", vendor="DEEPLEE", color="000000"),
        _payload(id_=2, name="PLA Wood", vendor="Creality", color="bf7628",
                 extruder_temp=210),
    ]
    spoolman_client = SpoolmanClient("http://stub")

    with Session(get_engine()) as session:
        result = await sync_filaments(session, spoolman_client)
        assert result.ok and result.inserted == 2 and result.updated == 0

        rows = session.exec(
            select(Filament).order_by(Filament.spoolman_filament_id)
        ).all()
        assert [r.spoolman_filament_id for r in rows] == [1, 2]
        assert rows[0].color_hex == "#000000"
        assert rows[1].hotend_temp_min == 210 == rows[1].hotend_temp_max

    # Same payload again — nothing changes.
    with Session(get_engine()) as session:
        result = await sync_filaments(session, spoolman_client)
        assert result.inserted == 0 and result.unchanged == 2

    # Mutate the payload — only the changed row counts as updated.
    fake_spoolman["payloads"][0]["color_hex"] = "111111"
    with Session(get_engine()) as session:
        result = await sync_filaments(session, spoolman_client)
        assert result.inserted == 0 and result.updated == 1 and result.unchanged == 1
        row = session.exec(
            select(Filament).where(Filament.spoolman_filament_id == 1)
        ).one()
        assert row.color_hex == "#111111"


async def test_sync_leaves_local_filaments_alone(
    client: TestClient, fake_spoolman
) -> None:
    # User-created filament without spoolman id.
    client.post(
        "/filaments",
        data={"name": "Hand-Made", "manufacturer": "Pierre", "material": "PLA"},
    )
    fake_spoolman["payloads"] = [
        _payload(id_=1, name="From Spoolman", vendor="X")
    ]
    with Session(get_engine()) as session:
        await sync_filaments(session, SpoolmanClient("http://stub"))
        # Both rows exist; the local one is untouched.
        local = session.exec(
            select(Filament).where(Filament.spoolman_filament_id.is_(None))
        ).one()
        synced = session.exec(
            select(Filament).where(Filament.spoolman_filament_id.is_not(None))
        ).one()
        assert local.name == "Hand-Made"
        assert synced.name == "From Spoolman"


async def test_sync_handles_network_failure_gracefully(
    client: TestClient, fake_spoolman
) -> None:
    fake_spoolman["raise"] = ConnectionError("spoolman down")
    with Session(get_engine()) as session:
        result = await sync_filaments(session, SpoolmanClient("http://stub"))
    assert not result.ok
    assert "spoolman down" in (result.error or "")


def test_sync_route_without_spoolman_url_shows_message(client: TestClient) -> None:
    response = client.post("/filaments/sync")
    assert response.status_code == 200
    assert "nicht konfiguriert" in response.text


async def test_sync_route_with_mock(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, fake_spoolman
) -> None:
    # Spoolman config now lives in the DB (app_settings table). Set the
    # URL via the runtime_settings service so the route picks it up.
    from app.services.runtime_settings import update_spoolman_settings

    with Session(get_engine()) as s:
        update_spoolman_settings(
            s,
            url="http://stub",
            public_url=None,
            auto_sync=True,
            interval_seconds=21600,
        )

    fake_spoolman["payloads"] = [
        _payload(id_=42, name="Galaxy Black", vendor="Polymaker", color="222222")
    ]

    response = client.post("/filaments/sync")
    assert response.status_code == 200
    body = response.text
    assert "Sync ok" in body
    assert "Galaxy Black" in body
    # Synced filament shows the Spoolman badge.
    assert "↻ Spoolman" in body
    # No public URL configured + URL is "http://stub" (not loopback-looking
    # but also not browser-relevant in tests) — link or read-only either
    # works, just check we didn't render the regular Bearbeiten button.
    assert ">Bearbeiten</button>" not in body


def test_index_shows_spoolman_panel(client: TestClient) -> None:
    response = client.get("/filaments")
    assert response.status_code == 200
    # Panel renders the "not configured" hint when SLICERDB_SPOOLMAN_URL is unset.
    assert "Spoolman" in response.text
    assert "Nicht konfiguriert" in response.text


def _make_synced_filament(client: TestClient, *, public_url: str | None) -> None:
    """Configure Spoolman + create one synced filament directly in the DB."""
    from app.services.runtime_settings import update_spoolman_settings

    with Session(get_engine()) as s:
        update_spoolman_settings(
            s,
            url="http://localhost:7912",
            public_url=public_url,
            auto_sync=True,
            interval_seconds=21600,
        )
        s.add(
            Filament(
                spoolman_filament_id=42,
                name="Test PLA",
                manufacturer="DEEPLEE",
                material="PLA",
                color_hex="#000000",
                hotend_temp_min=210,
                hotend_temp_max=210,
                bed_temp=60,
            )
        )
        s.commit()


def test_synced_row_shows_link_when_public_url_set(client: TestClient) -> None:
    _make_synced_filament(client, public_url="http://192.168.1.5:7912")
    body = client.get("/filaments").text
    assert "→ Spoolman" in body
    assert 'href="http://192.168.1.5:7912/filament/show/42"' in body
    assert 'target="_blank"' in body


def test_synced_row_uses_url_when_no_public_url(client: TestClient) -> None:
    """If only the API URL is set and it's a real LAN address, use it as link."""
    from app.services.runtime_settings import update_spoolman_settings

    with Session(get_engine()) as s:
        update_spoolman_settings(
            s,
            url="http://192.168.1.42:7912",
            public_url=None,
            auto_sync=True,
            interval_seconds=21600,
        )
        s.add(
            Filament(
                spoolman_filament_id=7,
                name="Real",
                manufacturer="X",
                material="PLA",
            )
        )
        s.commit()

    body = client.get("/filaments").text
    assert 'href="http://192.168.1.42:7912/filament/show/7"' in body


def test_synced_row_skips_link_for_loopback_url(client: TestClient) -> None:
    """Don't render a link to localhost — it points at the user's own machine."""
    _make_synced_filament(client, public_url=None)  # API url is localhost in helper
    body = client.get("/filaments").text
    assert "→ Spoolman" not in body
    assert "read-only" in body
