# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Print profiles and their versioned settings.

A PrintProfile is the Drucker × Düse × Filament × Slicer × Qualität combination.
Every change to the underlying settings produces a new immutable ProfileVersion
that stores the original slicer file as a blob plus optional metadata.
"""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.config import settings
from app.db import get_session
from app.models import (
    BuildPlate,
    Filament,
    Nozzle,
    Printer,
    PrintProfile,
    ProfileVersion,
    Slicer,
)
from app.services.slicer_parsers import detect_format, parse_settings, parse_user_settings
from app.templating import templates

ALLOWED_RATINGS = {"good", "bad", "untested"}
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

router = APIRouter(prefix="/profiles", tags=["profiles"])


# ---------- helpers ----------


def _safe_filename(name: str) -> str:
    cleaned = SAFE_FILENAME.sub("_", name).strip("._-")
    return cleaned or "file.bin"


def _profile_files_dir(profile_id: int) -> Path:
    p = settings.files_dir / f"profile-{profile_id}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _next_version_no(session: Session, profile_id: int) -> int:
    current = session.exec(
        select(func.max(ProfileVersion.version_no)).where(
            ProfileVersion.profile_id == profile_id
        )
    ).one()
    return (current or 0) + 1


def _load_profile(session: Session, profile_id: int) -> PrintProfile:
    profile = session.get(PrintProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


# ---------- list / create / delete ----------


def _list_response(request: Request, session: Session) -> HTMLResponse:
    profiles = session.exec(
        select(PrintProfile, Printer, Slicer, Filament)
        .join(Printer, PrintProfile.printer_id == Printer.id)
        .join(Slicer, PrintProfile.slicer_id == Slicer.id)
        .join(Filament, PrintProfile.filament_id == Filament.id)
        .order_by(Printer.name, PrintProfile.name)
    ).all()
    return templates.TemplateResponse(
        request, "profiles/_list.html", {"rows": profiles}
    )


@router.get("", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    rows = session.exec(
        select(PrintProfile, Printer, Slicer, Filament)
        .join(Printer, PrintProfile.printer_id == Printer.id)
        .join(Slicer, PrintProfile.slicer_id == Slicer.id)
        .join(Filament, PrintProfile.filament_id == Filament.id)
        .order_by(Printer.name, PrintProfile.name)
    ).all()
    printers = session.exec(select(Printer).order_by(Printer.name)).all()
    nozzles = session.exec(
        select(Nozzle, Printer)
        .join(Printer, Nozzle.printer_id == Printer.id)
        .order_by(Printer.name, Nozzle.diameter_mm)
    ).all()
    filaments = session.exec(
        select(Filament).order_by(Filament.manufacturer, Filament.name)
    ).all()
    slicers = session.exec(select(Slicer).order_by(Slicer.name)).all()
    build_plates = session.exec(
        select(BuildPlate).order_by(BuildPlate.manufacturer, BuildPlate.name)
    ).all()
    return templates.TemplateResponse(
        request,
        "profiles/index.html",
        {
            "rows": rows,
            "printers": printers,
            "nozzles": nozzles,
            "filaments": filaments,
            "slicers": slicers,
            "build_plates": build_plates,
        },
    )


@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    name: str = Form(min_length=1),
    printer_id: int = Form(),
    nozzle_id: int = Form(),
    filament_id: int = Form(),
    slicer_id: int = Form(),
    layer_height_mm: float = Form(gt=0, le=2.0),
    quality_label: str = Form(default="Standard"),
    build_plate_id: int | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    # Validate FK relationships before insert; surface clean errors instead of IntegrityError.
    if session.get(Printer, printer_id) is None:
        raise HTTPException(status_code=400, detail="Unknown printer_id")
    if session.get(Nozzle, nozzle_id) is None:
        raise HTTPException(status_code=400, detail="Unknown nozzle_id")
    if session.get(Filament, filament_id) is None:
        raise HTTPException(status_code=400, detail="Unknown filament_id")
    if session.get(Slicer, slicer_id) is None:
        raise HTTPException(status_code=400, detail="Unknown slicer_id")
    if build_plate_id is not None and session.get(BuildPlate, build_plate_id) is None:
        raise HTTPException(status_code=400, detail="Unknown build_plate_id")

    profile = PrintProfile(
        name=name.strip(),
        printer_id=printer_id,
        nozzle_id=nozzle_id,
        filament_id=filament_id,
        slicer_id=slicer_id,
        build_plate_id=build_plate_id,
        layer_height_mm=layer_height_mm,
        quality_label=quality_label.strip() or "Standard",
        notes=(notes or None),
    )
    session.add(profile)
    session.commit()
    return _list_response(request, session)


@router.delete("/{profile_id}", response_class=HTMLResponse)
def delete(
    profile_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profile = _load_profile(session, profile_id)
    # Drop on-disk blobs along with the row.
    blob_dir = settings.files_dir / f"profile-{profile_id}"
    session.delete(profile)
    session.commit()
    if blob_dir.exists():
        for f in blob_dir.iterdir():
            f.unlink(missing_ok=True)
        blob_dir.rmdir()
    return _list_response(request, session)


# ---------- detail (versions) ----------


@router.get("/{profile_id}", response_class=HTMLResponse)
def detail(
    profile_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profile = _load_profile(session, profile_id)
    printer = session.get(Printer, profile.printer_id)
    nozzle = session.get(Nozzle, profile.nozzle_id)
    filament = session.get(Filament, profile.filament_id)
    slicer = session.get(Slicer, profile.slicer_id)
    build_plate = (
        session.get(BuildPlate, profile.build_plate_id)
        if profile.build_plate_id
        else None
    )
    versions = session.exec(
        select(ProfileVersion)
        .where(ProfileVersion.profile_id == profile_id)
        .order_by(ProfileVersion.version_no.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "profiles/detail.html",
        {
            "profile": profile,
            "printer": printer,
            "nozzle": nozzle,
            "filament": filament,
            "slicer": slicer,
            "build_plate": build_plate,
            "versions": versions,
        },
    )


@router.post("/{profile_id}/versions", response_class=HTMLResponse)
async def upload_version(
    profile_id: int,
    request: Request,
    file: UploadFile = File(),
    change_note: str | None = Form(default=None),
    rating: str | None = Form(default=None),
    rating_note: str | None = Form(default=None),
    settings_text: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    profile = _load_profile(session, profile_id)
    slicer = session.get(Slicer, profile.slicer_id)
    if rating and rating not in ALLOWED_RATINGS:
        raise HTTPException(status_code=400, detail=f"rating must be one of {ALLOWED_RATINGS}")

    version_no = _next_version_no(session, profile_id)
    raw_name = _safe_filename(file.filename or "profile.bin")
    blob_path = _profile_files_dir(profile_id) / f"v{version_no:04d}-{raw_name}"
    contents = await file.read()
    blob_path.write_bytes(contents)

    declared_format = slicer.profile_format if slicer else None
    # Sniff the actual file format. ZIP bundles uploaded under a slicer that
    # claims orca-json, or vice versa, are common — trust the bytes.
    detected_format = detect_format(blob_path)
    raw_format = detected_format or declared_format
    file_settings = parse_settings(raw_format, blob_path)
    user_settings = parse_user_settings(settings_text)
    # User-typed entries win over what we extracted from the file.
    merged_settings = {**file_settings, **user_settings} or None

    version = ProfileVersion(
        profile_id=profile_id,
        version_no=version_no,
        change_note=(change_note or None),
        rating=(rating or None),
        rating_note=(rating_note or None),
        raw_filename=raw_name,
        raw_format=raw_format,
        raw_blob_path=str(blob_path.relative_to(settings.files_dir)),
        settings_json=merged_settings,
    )
    session.add(version)

    # First version becomes active automatically.
    if profile.active_version_id is None:
        session.flush()  # populate version.id
        profile.active_version_id = version.id
        session.add(profile)

    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover - defensive
        session.rollback()
        blob_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not persist version") from exc

    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)


@router.get("/{profile_id}/versions/{version_id}/download")
def download_version(
    profile_id: int,
    version_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    version = session.get(ProfileVersion, version_id)
    if version is None or version.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Version not found")
    if not version.raw_blob_path:
        raise HTTPException(status_code=404, detail="Version has no stored file")
    full_path = settings.files_dir / version.raw_blob_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(
        full_path,
        filename=version.raw_filename or full_path.name,
        media_type="application/octet-stream",
    )


@router.post("/{profile_id}/versions/{version_id}/activate")
def activate_version(
    profile_id: int,
    version_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    profile = _load_profile(session, profile_id)
    version = session.get(ProfileVersion, version_id)
    if version is None or version.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Version not found")
    profile.active_version_id = version.id
    session.add(profile)
    session.commit()
    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)


@router.post("/{profile_id}/versions/{version_id}/rate")
def rate_version(
    profile_id: int,
    version_id: int,
    rating: str = Form(),
    rating_note: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    if rating not in ALLOWED_RATINGS:
        raise HTTPException(status_code=400, detail=f"rating must be one of {ALLOWED_RATINGS}")
    version = session.get(ProfileVersion, version_id)
    if version is None or version.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Version not found")
    version.rating = rating
    version.rating_note = (rating_note or None)
    session.add(version)
    session.commit()
    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)


@router.post("/{profile_id}/versions/{version_id}/reparse")
def reparse_version(
    profile_id: int,
    version_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Re-run the slicer-file parser against this version's stored blob.

    Useful when:
    - the slicer's `profile_format` was wrong at upload time (e.g. orca-json
      set on a slicer that actually produces ZIP bundles), or
    - the parser improved since the original upload.

    The detected format wins over whatever was stored, so changing the slicer
    entry afterwards isn't necessary — we sniff the file's magic bytes.
    """
    version = session.get(ProfileVersion, version_id)
    if version is None or version.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Version not found")
    if not version.raw_blob_path:
        raise HTTPException(status_code=400, detail="Version has no stored file")
    full_path = settings.files_dir / version.raw_blob_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    detected = detect_format(full_path)
    new_settings = parse_settings(detected, full_path) or None
    version.settings_json = new_settings
    if detected:
        version.raw_format = detected
    session.add(version)
    session.commit()
    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)


@router.post("/{profile_id}/versions/{version_id}/settings")
def update_settings(
    profile_id: int,
    version_id: int,
    settings_text: str = Form(default=""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Replace a version's structured settings with whatever the user typed.

    The textarea is the source of truth here — we don't merge with the previous
    settings_json. If the user wants to keep auto-parsed values, they should
    leave them in the textarea.
    """
    version = session.get(ProfileVersion, version_id)
    if version is None or version.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Version not found")
    parsed = parse_user_settings(settings_text)
    version.settings_json = parsed or None
    session.add(version)
    session.commit()
    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)
