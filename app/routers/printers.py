from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Printer
from app.templating import templates

router = APIRouter(prefix="/printers", tags=["printers"])


def _list_response(request: Request, session: Session) -> HTMLResponse:
    printers = session.exec(select(Printer).order_by(Printer.name)).all()
    return templates.TemplateResponse(
        request, "printers/_list.html", {"printers": printers}
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
    session.delete(printer)
    session.commit()
    return _list_response(request, session)
