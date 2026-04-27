# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Nozzle, Printer
from app.services.integrity import references_to_nozzle
from app.templating import templates

router = APIRouter(prefix="/nozzles", tags=["nozzles"])


def _list_response(
    request: Request,
    session: Session,
    *,
    delete_error: dict | None = None,
) -> HTMLResponse:
    nozzles = session.exec(
        select(Nozzle, Printer)
        .join(Printer, Nozzle.printer_id == Printer.id)
        .order_by(Printer.name, Nozzle.diameter_mm)
    ).all()
    return templates.TemplateResponse(
        request,
        "nozzles/_list.html",
        {"rows": nozzles, "delete_error": delete_error},
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
    printer = session.get(Printer, nozzle.printer_id)
    refs = references_to_nozzle(session, nozzle_id)
    if refs:
        label = (
            f"{printer.name if printer else '?'} — "
            f"{nozzle.diameter_mm:.2f} mm {nozzle.material}"
        )
        return _list_response(
            request,
            session,
            delete_error={"name": label, "references": refs},
        )
    session.delete(nozzle)
    session.commit()
    return _list_response(request, session)


# ----- Inline edit -----


def _row_response(
    request: Request,
    nozzle: Nozzle,
    session: Session,
    *,
    edit: bool = False,
) -> HTMLResponse:
    printer = session.get(Printer, nozzle.printer_id)
    template = "nozzles/_row_edit.html" if edit else "nozzles/_row.html"
    ctx: dict = {"nozzle": nozzle, "printer": printer}
    if edit:
        ctx["printers"] = session.exec(select(Printer).order_by(Printer.name)).all()
    return templates.TemplateResponse(request, template, ctx)


@router.get("/{nozzle_id}/row", response_class=HTMLResponse)
def row_display(
    nozzle_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    nozzle = session.get(Nozzle, nozzle_id)
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    return _row_response(request, nozzle, session)


@router.get("/{nozzle_id}/edit", response_class=HTMLResponse)
def row_edit(
    nozzle_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    nozzle = session.get(Nozzle, nozzle_id)
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    return _row_response(request, nozzle, session, edit=True)


@router.put("/{nozzle_id}", response_class=HTMLResponse)
def update(
    nozzle_id: int,
    request: Request,
    printer_id: int = Form(),
    diameter_mm: float = Form(gt=0, le=2.0),
    material: str = Form(default="brass"),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    nozzle = session.get(Nozzle, nozzle_id)
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Nozzle not found")
    if session.get(Printer, printer_id) is None:
        raise HTTPException(status_code=400, detail="Unknown printer_id")
    nozzle.printer_id = printer_id
    nozzle.diameter_mm = diameter_mm
    nozzle.material = material.strip() or "brass"
    nozzle.notes = (notes or None)
    session.add(nozzle)
    session.commit()
    session.refresh(nozzle)
    return _row_response(request, nozzle, session)
