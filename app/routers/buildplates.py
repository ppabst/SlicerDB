# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import BuildPlate
from app.templating import templates

SURFACE_TYPES = (
    "PEI",
    "Cool Plate",
    "Engineering",
    "High-Temperature",
    "Garolite",
    "Glass",
    "Other",
)
FINISHES = ("smooth", "textured", "satin")

router = APIRouter(prefix="/buildplates", tags=["buildplates"])


def _list_response(request: Request, session: Session) -> HTMLResponse:
    plates = session.exec(
        select(BuildPlate).order_by(BuildPlate.manufacturer, BuildPlate.name)
    ).all()
    return templates.TemplateResponse(
        request, "buildplates/_list.html", {"plates": plates}
    )


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    plates = session.exec(
        select(BuildPlate).order_by(BuildPlate.manufacturer, BuildPlate.name)
    ).all()
    return templates.TemplateResponse(
        request,
        "buildplates/index.html",
        {
            "plates": plates,
            "surface_types": SURFACE_TYPES,
            "finishes": FINISHES,
        },
    )


@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    name: str = Form(min_length=1),
    surface_type: str = Form(),
    finish: str | None = Form(default=None),
    manufacturer: str | None = Form(default=None),
    bed_temp_min: int | None = Form(default=None),
    bed_temp_max: int | None = Form(default=None),
    compatible_materials: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if surface_type not in SURFACE_TYPES:
        raise HTTPException(status_code=400, detail="Unknown surface_type")
    if finish and finish not in FINISHES:
        raise HTTPException(status_code=400, detail="Unknown finish")

    plate = BuildPlate(
        name=name.strip(),
        surface_type=surface_type,
        finish=(finish or None),
        manufacturer=(manufacturer or None),
        bed_temp_min=bed_temp_min,
        bed_temp_max=bed_temp_max,
        compatible_materials=(compatible_materials or None),
        notes=(notes or None),
    )
    session.add(plate)
    session.commit()
    return _list_response(request, session)


@router.delete("/{plate_id}", response_class=HTMLResponse)
def delete(
    plate_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    plate = session.get(BuildPlate, plate_id)
    if plate is None:
        raise HTTPException(status_code=404, detail="Build plate not found")
    session.delete(plate)
    session.commit()
    return _list_response(request, session)
