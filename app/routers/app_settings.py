# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings-Seite — DB-backed runtime configuration."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.db import get_session
from app.services.runtime_settings import (
    get_app_settings,
    update_spoolman_settings,
)
from app.services.spoolman import SpoolmanClient
from app.templating import templates

router = APIRouter(prefix="/settings", tags=["settings"])


def _page(
    request: Request,
    session: Session,
    *,
    saved: bool = False,
    test_result: dict | None = None,
) -> HTMLResponse:
    cfg = get_app_settings(session)
    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "cfg": cfg,
            "saved": saved,
            "test_result": test_result,
            "interval_hours": cfg.spoolman_sync_interval_seconds / 3600,
        },
    )


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return _page(request, session)


@router.post("/spoolman", response_class=HTMLResponse)
def save_spoolman(
    request: Request,
    spoolman_url: str = Form(default=""),
    auto_sync: str | None = Form(default=None),
    interval_hours: float = Form(default=6.0, gt=0, le=24),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Persist the Spoolman config. Form posts use minutes-aware hours, we
    store seconds in the DB. The background loop picks this up within a
    minute (its idle pulse)."""
    update_spoolman_settings(
        session,
        url=spoolman_url,
        auto_sync=bool(auto_sync),
        interval_seconds=int(interval_hours * 3600),
    )
    return _page(request, session, saved=True)


@router.post("/spoolman/test", response_class=HTMLResponse)
async def test_spoolman(
    request: Request,
    spoolman_url: str = Form(default=""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Hit /api/v1/info on the given URL without saving — quick reachability
    check before the user commits the config."""
    url = (spoolman_url or "").strip()
    if not url:
        return _page(
            request,
            session,
            test_result={"ok": False, "msg": "Bitte erst eine URL eintragen."},
        )
    client = SpoolmanClient(url, timeout=5.0)
    try:
        info = await client.info()
        version = info.get("version", "?")
        db = info.get("db_type", "?")
        return _page(
            request,
            session,
            test_result={
                "ok": True,
                "msg": f"Verbunden — Spoolman {version} ({db}).",
            },
        )
    except Exception as exc:
        return _page(
            request,
            session,
            test_result={"ok": False, "msg": f"Nicht erreichbar: {exc}"},
        )
