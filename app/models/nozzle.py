# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.printer import Printer
    from app.models.profile import PrintProfile


class NozzleBase(SQLModel):
    diameter_mm: float = Field(gt=0, le=2.0, description="Nozzle diameter in mm (e.g. 0.4)")
    material: str = Field(default="brass", max_length=40, description="brass / hardened / ruby / ...")
    notes: str | None = Field(default=None)


class Nozzle(NozzleBase, TimestampMixin, table=True):
    __tablename__ = "nozzle"

    id: int | None = Field(default=None, primary_key=True)
    printer_id: int = Field(foreign_key="printer.id", index=True)

    printer: "Printer" = Relationship(back_populates="nozzles")
    profiles: list["PrintProfile"] = Relationship(back_populates="nozzle")


class NozzleCreate(NozzleBase):
    printer_id: int


class NozzleUpdate(SQLModel):
    diameter_mm: float | None = None
    material: str | None = None
    notes: str | None = None


class NozzleRead(NozzleBase):
    id: int
    printer_id: int
