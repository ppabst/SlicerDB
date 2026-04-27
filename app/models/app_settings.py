# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Mutable runtime configuration, persisted in the DB.

There is exactly one row (id=1). Env vars `SLICERDB_SPOOLMAN_URL` etc. are
*only* read at first start to seed this row — after that the GUI is the
source of truth, so changes survive container restarts and don't require
editing compose.yml.
"""

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin

SINGLETON_ID = 1


class AppSettings(TimestampMixin, SQLModel, table=True):
    __tablename__ = "app_settings"

    id: int = Field(default=SINGLETON_ID, primary_key=True)

    # ----- Spoolman -----
    spoolman_url: str | None = Field(default=None, max_length=300)
    # Browser-reachable URL — different from spoolman_url when the container
    # talks to Spoolman over a loopback (e.g. http://localhost:7912 via
    # network_mode: host) but the user's browser needs http://<host>:7912.
    # When set, synced filament rows expose a "→ Spoolman" link button that
    # opens <public_url>/filament/show/<id> in a new tab.
    spoolman_public_url: str | None = Field(default=None, max_length=300)
    spoolman_auto_sync: bool = Field(default=True)
    spoolman_sync_interval_seconds: int = Field(default=21600, ge=60, le=86400)
