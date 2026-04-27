# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Spoolman read-only sync.

We pull filaments (and the embedded vendor info) from a self-hosted Spoolman
instance and mirror them into our `filament` table, identifying them by
`spoolman_filament_id`. New entries get inserted, existing ones get updated
in place. Local-only filaments — those without a `spoolman_filament_id` —
are never touched.

API reference: https://donkie.github.io/Spoolman/

Design notes
- Spoolman's filament JSON exposes a single `settings_extruder_temp` (int).
  Our model has `hotend_temp_min`/`hotend_temp_max` because real-world
  filaments come with ranges. We mirror the single value into both fields;
  the UI renders "X °C" when min == max so it stays compact.
- `color_hex` from Spoolman has no leading `#`, ours does — we normalise.
- A filament that disappears from Spoolman is deliberately *not* deleted
  here: it might still be referenced by a profile, and the user should
  see a warning rather than a silent break. Stale-detection (last
  successful sync timestamp) is on `Filament.synced_at`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import Session, select

from app.models import Filament

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    inserted: int
    updated: int
    unchanged: int
    fetched_at: datetime
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class SpoolmanClient:
    """Thin httpx wrapper. Times out fast — Spoolman is on-LAN."""

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def info(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(f"{self.base_url}/api/v1/info")
            r.raise_for_status()
            return r.json()

    async def filaments(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(f"{self.base_url}/api/v1/filament")
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []


def _normalise_hex(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    return value if value.startswith("#") else f"#{value}"


def _filament_fields_from_spoolman(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the subset of Spoolman fields we mirror locally."""
    vendor = payload.get("vendor") or {}
    extruder_temp = payload.get("settings_extruder_temp")
    return {
        "name": (payload.get("name") or "").strip() or "(unbenannt)",
        "manufacturer": (vendor.get("name") or "Unbekannt").strip(),
        "material": (payload.get("material") or "Unknown").strip(),
        "color_hex": _normalise_hex(payload.get("color_hex")),
        "hotend_temp_min": extruder_temp,
        "hotend_temp_max": extruder_temp,
        "bed_temp": payload.get("settings_bed_temp"),
    }


def _apply_to_filament(target: Filament, fields: dict[str, Any]) -> bool:
    """Returns True if any field actually changed."""
    changed = False
    for key, new_value in fields.items():
        if getattr(target, key) != new_value:
            setattr(target, key, new_value)
            changed = True
    return changed


async def sync_filaments(session: Session, client: SpoolmanClient) -> SyncResult:
    """Pull all filaments from Spoolman and reconcile with our table."""
    now = datetime.now(UTC)
    try:
        payloads = await client.filaments()
    except Exception as exc:  # network, HTTP error, JSON parse — all fail-soft
        log.warning("Spoolman sync failed: %s", exc)
        return SyncResult(0, 0, 0, now, error=str(exc))

    # Build an index of locally-tracked Spoolman filaments by their Spoolman id.
    existing_rows = session.exec(
        select(Filament).where(Filament.spoolman_filament_id.is_not(None))
    ).all()
    by_remote_id: dict[int, Filament] = {
        row.spoolman_filament_id: row for row in existing_rows
    }

    inserted = updated = unchanged = 0
    for payload in payloads:
        remote_id = payload.get("id")
        if not isinstance(remote_id, int):
            continue
        fields = _filament_fields_from_spoolman(payload)

        existing = by_remote_id.get(remote_id)
        if existing is None:
            row = Filament(
                spoolman_filament_id=remote_id,
                synced_at=now,
                **fields,
            )
            session.add(row)
            inserted += 1
        else:
            if _apply_to_filament(existing, fields):
                updated += 1
            else:
                unchanged += 1
            existing.synced_at = now
            session.add(existing)

    session.commit()
    return SyncResult(
        inserted=inserted, updated=updated, unchanged=unchanged, fetched_at=now
    )
