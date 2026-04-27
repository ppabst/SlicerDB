# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Printer
from app.services.integrity import references_to_printer
from app.templating import templates

router = APIRouter(prefix="/printers", tags=["printers"])


def _list_response(
    request: Request,
    session: Session,
    *,
    delete_error: dict | None = None,
) -> HTMLResponse:
    printers = session.exec(select(Printer).order_by(Printer.name)).all()
    return templates.TemplateResponse(
        request,
        "printers/_list.html",
        {"printers": printers, "delete_error": delete_error},
    )


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    printers = session.exec(select(Printer).order_by(Printer.name)).all()
    return templates.TemplateResponse(
        request, "printers/index.html", {"printers": printers}
    )


@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    name: str = Form(min_length=1),
    manufacturer: str = Form(min_length=1),
    model: str = Form(min_length=1),
    build_volume: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    printer = Printer(
        name=name.strip(),
        manufacturer=manufacturer.strip(),
        model=model.strip(),
        build_volume=(build_volume or None),
        notes=(notes or None),
    )
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return _list_response(request, session)


@router.delete("/{printer_id}", response_class=HTMLResponse)
def delete(
    printer_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    printer = session.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    refs = references_to_printer(session, printer_id)
    if refs:
        return _list_response(
            request,
            session,
            delete_error={"name": printer.name, "references": refs},
        )
    session.delete(printer)
    session.commit()
    return _list_response(request, session)


# ----- Inline edit (mirrors filaments) -----


def _row_response(
    request: Request, printer: Printer, *, edit: bool = False
) -> HTMLResponse:
    template = "printers/_row_edit.html" if edit else "printers/_row.html"
    return templates.TemplateResponse(request, template, {"p": printer})


@router.get("/{printer_id}/row", response_class=HTMLResponse)
def row_display(
    printer_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    printer = session.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    return _row_response(request, printer)


@router.get("/{printer_id}/edit", response_class=HTMLResponse)
def row_edit(
    printer_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    printer = session.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    return _row_response(request, printer, edit=True)


@router.put("/{printer_id}", response_class=HTMLResponse)
def update(
    printer_id: int,
    request: Request,
    name: str = Form(min_length=1),
    manufacturer: str = Form(min_length=1),
    model: str = Form(min_length=1),
    build_volume: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    printer = session.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    printer.name = name.strip()
    printer.manufacturer = manufacturer.strip()
    printer.model = model.strip()
    printer.build_volume = (build_volume or None)
    printer.notes = (notes or None)
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return _row_response(request, printer)
