# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Referential-integrity helpers used by every delete endpoint.

Each function returns a list of `Reference` records describing where the
entity-to-be-deleted is currently in use. An empty list means the delete is
safe; any non-empty list must block the delete and surface the references
to the user.

The DB has FK constraints already, but raising IntegrityError mid-request
gives an ugly experience. These helpers let us refuse cleanly *before*
we touch the DB and ship a banner with clickable links to the call sites.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import (
    BuildPlate,
    Filament,
    Nozzle,
    Printer,
    PrintProfile,
    Slicer,
)


@dataclass(frozen=True)
class Reference:
    kind: str        # "Drucker" / "Düse" / "Profil" — what's referencing
    label: str       # human-friendly name to show
    link: str        # URL the user can click to jump to the call site


def _profile_refs(
    session: Session, *, where_clause
) -> list[Reference]:
    rows = session.exec(
        select(PrintProfile).where(where_clause).order_by(PrintProfile.name)
    ).all()
    return [
        Reference(kind="Profil", label=p.name, link=f"/profiles/{p.id}")
        for p in rows
    ]


def references_to_printer(session: Session, printer_id: int) -> list[Reference]:
    """Nozzles attached to this printer + Profiles using it."""
    nozzle_rows = session.exec(
        select(Nozzle, Printer)
        .join(Printer, Nozzle.printer_id == Printer.id)
        .where(Nozzle.printer_id == printer_id)
        .order_by(Nozzle.diameter_mm)
    ).all()
    refs: list[Reference] = [
        Reference(
            kind="Düse",
            label=f"{p.name} — {n.diameter_mm:.2f} mm {n.material}",
            link="/nozzles",
        )
        for n, p in nozzle_rows
    ]
    refs.extend(_profile_refs(session, where_clause=PrintProfile.printer_id == printer_id))
    return refs


def references_to_nozzle(session: Session, nozzle_id: int) -> list[Reference]:
    return _profile_refs(session, where_clause=PrintProfile.nozzle_id == nozzle_id)


def references_to_filament(session: Session, filament_id: int) -> list[Reference]:
    return _profile_refs(session, where_clause=PrintProfile.filament_id == filament_id)


def references_to_slicer(session: Session, slicer_id: int) -> list[Reference]:
    return _profile_refs(session, where_clause=PrintProfile.slicer_id == slicer_id)


def references_to_build_plate(session: Session, plate_id: int) -> list[Reference]:
    return _profile_refs(session, where_clause=PrintProfile.build_plate_id == plate_id)


# Convenience: keep the silly-typed entities discoverable from one place.
__all__ = [
    "Reference",
    "references_to_build_plate",
    "references_to_filament",
    "references_to_nozzle",
    "references_to_printer",
    "references_to_slicer",
]


# Re-export model names so static type-checking on call sites doesn't need
# extra imports just to read the docstrings.
_ = (BuildPlate, Filament, Slicer)  # silence "imported but unused" without runtime cost
