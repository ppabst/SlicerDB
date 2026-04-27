# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Filament
from app.services.integrity import references_to_filament
from app.templating import templates

router = APIRouter(prefix="/filaments", tags=["filaments"])


def _list_response(
    request: Request,
    session: Session,
    *,
    delete_error: dict | None = None,
) -> HTMLResponse:
    filaments = session.exec(
        select(Filament).order_by(Filament.manufacturer, Filament.name)
    ).all()
    return templates.TemplateResponse(
        request,
        "filaments/_list.html",
        {"filaments": filaments, "delete_error": delete_error},
    )


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    filaments = session.exec(
        select(Filament).order_by(Filament.manufacturer, Filament.name)
    ).all()
    return templates.TemplateResponse(
        request, "filaments/index.html", {"filaments": filaments}
    )


@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    name: str = Form(min_length=1),
    manufacturer: str = Form(min_length=1),
    material: str = Form(default="PLA"),
    color_hex: str | None = Form(default=None),
    hotend_temp_min: int | None = Form(default=None),
    hotend_temp_max: int | None = Form(default=None),
    bed_temp: int | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    color = (color_hex or "").strip() or None
    if color and not color.startswith("#"):
        color = f"#{color}"
    filament = Filament(
        name=name.strip(),
        manufacturer=manufacturer.strip(),
        material=material.strip() or "PLA",
        color_hex=color,
        hotend_temp_min=hotend_temp_min,
        hotend_temp_max=hotend_temp_max,
        bed_temp=bed_temp,
        notes=(notes or None),
    )
    session.add(filament)
    session.commit()
    return _list_response(request, session)


@router.delete("/{filament_id}", response_class=HTMLResponse)
def delete(
    filament_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    filament = session.get(Filament, filament_id)
    if filament is None:
        raise HTTPException(status_code=404, detail="Filament not found")
    refs = references_to_filament(session, filament_id)
    if refs:
        return _list_response(
            request,
            session,
            delete_error={
                "name": f"{filament.manufacturer} {filament.name}",
                "references": refs,
            },
        )
    session.delete(filament)
    session.commit()
    return _list_response(request, session)


# ----- Inline edit: row → form → updated row, all via HTMX outerHTML swaps -----


def _row_response(
    request: Request, filament: Filament, *, edit: bool = False
) -> HTMLResponse:
    """Render a single filament row, either in display or edit mode."""
    template = "filaments/_row_edit.html" if edit else "filaments/_row.html"
    return templates.TemplateResponse(request, template, {"f": filament})


@router.get("/{filament_id}/row", response_class=HTMLResponse)
def row_display(
    filament_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Used by the Cancel button to swing the edit form back to a display row."""
    filament = session.get(Filament, filament_id)
    if filament is None:
        raise HTTPException(status_code=404, detail="Filament not found")
    return _row_response(request, filament)


@router.get("/{filament_id}/edit", response_class=HTMLResponse)
def row_edit(
    filament_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Returns the edit-form fragment that replaces the display row."""
    filament = session.get(Filament, filament_id)
    if filament is None:
        raise HTTPException(status_code=404, detail="Filament not found")
    return _row_response(request, filament, edit=True)


@router.put("/{filament_id}", response_class=HTMLResponse)
def update(
    filament_id: int,
    request: Request,
    name: str = Form(min_length=1),
    manufacturer: str = Form(min_length=1),
    material: str = Form(default="PLA"),
    color_hex: str | None = Form(default=None),
    hotend_temp_min: int | None = Form(default=None),
    hotend_temp_max: int | None = Form(default=None),
    bed_temp: int | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    filament = session.get(Filament, filament_id)
    if filament is None:
        raise HTTPException(status_code=404, detail="Filament not found")

    color = (color_hex or "").strip() or None
    if color and not color.startswith("#"):
        color = f"#{color}"

    filament.name = name.strip()
    filament.manufacturer = manufacturer.strip()
    filament.material = material.strip() or "PLA"
    filament.color_hex = color
    filament.hotend_temp_min = hotend_temp_min
    filament.hotend_temp_max = hotend_temp_max
    filament.bed_temp = bed_temp
    filament.notes = (notes or None)
    session.add(filament)
    session.commit()
    session.refresh(filament)
    return _row_response(request, filament)
