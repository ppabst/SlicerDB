# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import PrintProfile


class BuildPlateBase(SQLModel):
    name: str = Field(index=True, min_length=1, max_length=120)
    surface_type: str = Field(
        max_length=40,
        description="PEI / Cool Plate / Engineering / High-Temperature / Garolite / Glass / Other",
    )
    finish: str | None = Field(
        default=None,
        max_length=20,
        description="smooth / textured / satin / null",
    )
    manufacturer: str | None = Field(default=None, max_length=80)
    bed_temp_min: int | None = Field(default=None, ge=0, le=200)
    bed_temp_max: int | None = Field(default=None, ge=0, le=200)
    compatible_materials: str | None = Field(
        default=None,
        max_length=200,
        description="Comma-separated material names, e.g. 'PLA, PETG, TPU'",
    )
    notes: str | None = Field(default=None)


class BuildPlate(BuildPlateBase, TimestampMixin, table=True):
    __tablename__ = "build_plate"

    id: int | None = Field(default=None, primary_key=True)

    profiles: list["PrintProfile"] = Relationship(back_populates="build_plate")


class BuildPlateCreate(BuildPlateBase):
    pass


class BuildPlateRead(BuildPlateBase):
    id: int
