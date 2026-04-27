# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Nozzle, Printer
from app.templating import templates

router = APIRouter(prefix="/nozzles", tags=["nozzles"])


def _list_response(request: Request, session: Session) -> HTMLResponse:
    nozzles = session.exec(
        select(Nozzle, Printer)
        .join(Printer, Nozzle.printer_id == Printer.id)
        .order_by(Printer.name, Nozzle.diameter_mm)
    ).all()
    return templates.TemplateResponse(
        request, "nozzles/_list.html", {"rows": nozzles}
    )


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    nozzles = session.exec(
        select(Nozzle, Printer)
        .join(Printer, Nozzle.printer_id == Printer.id)
        .order_by(Printer.name, Nozzle.diameter_mm)
    ).all()
    printers = session.exec(select(Printer).order_by(Printer.name)).all()
    return templates.TemplateResponse(
        request,
        "nozzles/index.html",
        {"rows": nozzles, "printers": printers},
    )


@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    printer_id: int = Form(),
    diameter_mm: float = Form(gt=0, le=2.0),
    material: str = Form(default="brass"),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if session.get(Printer, printer_id) is None:
        raise HTTPException(status_code=400, detail="Unknown printer_id")
    nozzle = Nozzle(
        printer_id=printer_id,
        diameter_mm=diameter_mm,
        material=material.strip() or "brass",
        notes=(notes or None),
    )
    session.add(nozzle)
    session.commit()
    return _list_response(request, session)


@router.delete("/{nozzle_id}", response_class=HTMLResponse)
def delete(
    nozzle_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    nozzle = session.get(Nozzle, nozzle_id)
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    session.delete(nozzle)
    session.commit()
    return _list_response(request, session)
