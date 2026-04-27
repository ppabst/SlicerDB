from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Filament
from app.templating import templates

router = APIRouter(prefix="/filaments", tags=["filaments"])


def _list_response(request: Request, session: Session) -> HTMLResponse:
    filaments = session.exec(
        select(Filament).order_by(Filament.manufacturer, Filament.name)
    ).all()
    return templates.TemplateResponse(
        request, "filaments/_list.html", {"filaments": filaments}
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
    session.delete(filament)
    session.commit()
    return _list_response(request, session)
