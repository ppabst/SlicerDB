# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Slicer
from app.services.integrity import references_to_slicer
from app.templating import templates

PROFILE_FORMATS = (
    "orca-json",
    "anycubic-bundle",
    "cura-profile",
    "prusa-ini",
    "other",
)

router = APIRouter(prefix="/slicers", tags=["slicers"])


def _list_response(
    request: Request,
    session: Session,
    *,
    delete_error: dict | None = None,
) -> HTMLResponse:
    slicers = session.exec(select(Slicer).order_by(Slicer.name)).all()
    return templates.TemplateResponse(
        request,
        "slicers/_list.html",
        {"slicers": slicers, "delete_error": delete_error},
    )


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    slicers = session.exec(select(Slicer).order_by(Slicer.name)).all()
    return templates.TemplateResponse(
        request,
        "slicers/index.html",
        {"slicers": slicers, "profile_formats": PROFILE_FORMATS},
    )


@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    name: str = Form(min_length=1),
    version: str | None = Form(default=None),
    profile_format: str = Form(default="orca-json"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if profile_format not in PROFILE_FORMATS:
        raise HTTPException(status_code=400, detail="Unknown profile_format")
    slicer = Slicer(
        name=name.strip(),
        version=(version or None),
        profile_format=profile_format,
    )
    session.add(slicer)
    session.commit()
    return _list_response(request, session)


@router.delete("/{slicer_id}", response_class=HTMLResponse)
def delete(
    slicer_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    slicer = session.get(Slicer, slicer_id)
    if slicer is None:
        raise HTTPException(status_code=404, detail="Slicer not found")
    refs = references_to_slicer(session, slicer_id)
    if refs:
        return _list_response(
            request,
            session,
            delete_error={"name": slicer.name, "references": refs},
        )
    session.delete(slicer)
    session.commit()
    return _list_response(request, session)


# ----- Inline edit -----


def _row_response(
    request: Request, slicer: Slicer, *, edit: bool = False
) -> HTMLResponse:
    template = "slicers/_row_edit.html" if edit else "slicers/_row.html"
    ctx: dict = {"s": slicer}
    if edit:
        ctx["profile_formats"] = PROFILE_FORMATS
    return templates.TemplateResponse(request, template, ctx)


@router.get("/{slicer_id}/row", response_class=HTMLResponse)
def row_display(
    slicer_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    slicer = session.get(Slicer, slicer_id)
    if slicer is None:
        raise HTTPException(status_code=404, detail="Slicer not found")
    return _row_response(request, slicer)


@router.get("/{slicer_id}/edit", response_class=HTMLResponse)
def row_edit(
    slicer_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    slicer = session.get(Slicer, slicer_id)
    if slicer is None:
        raise HTTPException(status_code=404, detail="Slicer not found")
    return _row_response(request, slicer, edit=True)


@router.put("/{slicer_id}", response_class=HTMLResponse)
def update(
    slicer_id: int,
    request: Request,
    name: str = Form(min_length=1),
    version: str | None = Form(default=None),
    profile_format: str = Form(default="orca-json"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if profile_format not in PROFILE_FORMATS:
        raise HTTPException(status_code=400, detail="Unknown profile_format")
    slicer = session.get(Slicer, slicer_id)
    if slicer is None:
        raise HTTPException(status_code=404, detail="Slicer not found")
    slicer.name = name.strip()
    slicer.version = (version or None)
    slicer.profile_format = profile_format
    session.add(slicer)
    session.commit()
    session.refresh(slicer)
    return _row_response(request, slicer)
