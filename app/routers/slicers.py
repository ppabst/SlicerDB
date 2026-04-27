from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Slicer
from app.templating import templates

PROFILE_FORMATS = (
    "orca-json",
    "anycubic-bundle",
    "cura-profile",
    "prusa-ini",
    "other",
)

router = APIRouter(prefix="/slicers", tags=["slicers"])


def _list_response(request: Request, session: Session) -> HTMLResponse:
    slicers = session.exec(select(Slicer).order_by(Slicer.name)).all()
    return templates.TemplateResponse(
        request, "slicers/_list.html", {"slicers": slicers}
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
    session.delete(slicer)
    session.commit()
    return _list_response(request, session)
