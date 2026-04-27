# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings page: persist Spoolman config to DB via the GUI."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import get_engine
from app.models import SINGLETON_ID, AppSettings
from app.services.runtime_settings import get_app_settings


def test_settings_page_renders(client: TestClient) -> None:
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Spoolman" in response.text
    assert "Verbindung testen" in response.text
    # The singleton row should now exist (created on first read).
    with Session(get_engine()) as s:
        row = s.get(AppSettings, SINGLETON_ID)
        assert row is not None
        # No env config in tests → bootstrap row is empty.
        assert row.spoolman_url is None


def test_save_spoolman_persists_to_db(client: TestClient) -> None:
    response = client.post(
        "/settings/spoolman",
        data={
            "spoolman_url": "http://my-spoolman:7912",
            "spoolman_public_url": "http://192.168.1.10:7912/",
            "auto_sync": "1",
            "interval_hours": 2,
        },
    )
    assert response.status_code == 200
    assert "Gespeichert" in response.text

    with Session(get_engine()) as s:
        row = get_app_settings(s)
        assert row.spoolman_url == "http://my-spoolman:7912"
        # Trailing slash gets stripped — link templates do their own join.
        assert row.spoolman_public_url == "http://192.168.1.10:7912"
        assert row.spoolman_auto_sync is True
        assert row.spoolman_sync_interval_seconds == 2 * 3600


def test_save_with_blank_url_clears_integration(client: TestClient) -> None:
    # Set then clear.
    client.post(
        "/settings/spoolman",
        data={"spoolman_url": "http://x:7912", "auto_sync": "1", "interval_hours": 6},
    )
    response = client.post(
        "/settings/spoolman",
        data={"spoolman_url": "", "interval_hours": 6},
    )
    assert response.status_code == 200
    with Session(get_engine()) as s:
        row = get_app_settings(s)
        assert row.spoolman_url is None
        # auto_sync checkbox missing → False
        assert row.spoolman_auto_sync is False


def test_save_clamps_interval(client: TestClient) -> None:
    # interval_hours must satisfy 0 < x <= 24 at the form layer; this checks
    # the seconds clamp inside the service for over-large values that bypass
    # the form (should never happen via UI, but we want to prove the clamp).
    from app.services.runtime_settings import update_spoolman_settings

    with Session(get_engine()) as s:
        row = update_spoolman_settings(
            s, url="http://x", public_url=None, auto_sync=True, interval_seconds=10
        )
        assert row.spoolman_sync_interval_seconds == 60  # min clamp
        row = update_spoolman_settings(
            s, url="http://x", public_url=None, auto_sync=True, interval_seconds=999_999
        )
        assert row.spoolman_sync_interval_seconds == 86400  # max clamp


@pytest.fixture
def stub_spoolman_info(monkeypatch: pytest.MonkeyPatch):
    """Stub SpoolmanClient.info — used by the test-connection button."""
    state: dict = {"raise": None, "response": {"version": "0.23.1", "db_type": "sqlite"}}

    async def fake_info(self):  # type: ignore[no-untyped-def]
        if state["raise"] is not None:
            raise state["raise"]
        return state["response"]

    from app.services.spoolman import SpoolmanClient
    monkeypatch.setattr(SpoolmanClient, "info", fake_info)
    return state


async def test_test_connection_success(
    client: TestClient, stub_spoolman_info
) -> None:
    response = client.post(
        "/settings/spoolman/test", data={"spoolman_url": "http://stub"}
    )
    assert response.status_code == 200
    assert "Verbunden" in response.text
    assert "0.23.1" in response.text


async def test_test_connection_error(
    client: TestClient, stub_spoolman_info
) -> None:
    stub_spoolman_info["raise"] = ConnectionError("nope")
    response = client.post(
        "/settings/spoolman/test", data={"spoolman_url": "http://stub"}
    )
    assert response.status_code == 200
    assert "Nicht erreichbar" in response.text
    assert "nope" in response.text


def test_test_connection_without_url(client: TestClient) -> None:
    response = client.post("/settings/spoolman/test", data={"spoolman_url": ""})
    assert response.status_code == 200
    assert "Bitte erst eine URL" in response.text
