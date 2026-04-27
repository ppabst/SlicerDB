# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read/write the singleton AppSettings row.

The DB is the canonical source of truth. Env vars (SLICERDB_SPOOLMAN_URL,
SLICERDB_SPOOLMAN_AUTO_SYNC, SLICERDB_SPOOLMAN_SYNC_INTERVAL_SECONDS) are
*only* used to bootstrap the row on first start, so existing
compose-driven setups keep working without editing the GUI.

After the row exists, the env vars are ignored — change config in the GUI.
"""

from __future__ import annotations

from sqlmodel import Session

from app.config import settings as env_settings
from app.models import SINGLETON_ID, AppSettings


def get_app_settings(session: Session) -> AppSettings:
    """Return the singleton row, creating it on first call.

    On creation we copy the bootstrap env vars into the row so the user's
    existing SLICERDB_* configuration carries over to the GUI.
    """
    row = session.get(AppSettings, SINGLETON_ID)
    if row is None:
        row = AppSettings(
            id=SINGLETON_ID,
            spoolman_url=env_settings.spoolman_url,
            spoolman_public_url=env_settings.spoolman_public_url,
            spoolman_auto_sync=env_settings.spoolman_auto_sync,
            spoolman_sync_interval_seconds=env_settings.spoolman_sync_interval_seconds,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def update_spoolman_settings(
    session: Session,
    *,
    url: str | None,
    public_url: str | None,
    auto_sync: bool,
    interval_seconds: int,
) -> AppSettings:
    """Persist new Spoolman config; takes effect on next sync iteration."""
    row = get_app_settings(session)
    row.spoolman_url = (url or "").strip() or None
    row.spoolman_public_url = (public_url or "").strip().rstrip("/") or None
    row.spoolman_auto_sync = auto_sync
    row.spoolman_sync_interval_seconds = max(60, min(86400, interval_seconds))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
