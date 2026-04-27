# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import PrintProfile


class FilamentBase(SQLModel):
    name: str = Field(index=True, min_length=1, max_length=120)
    manufacturer: str = Field(min_length=1, max_length=80)
    material: str = Field(max_length=40, description="PLA / PETG / ABS / ASA / TPU / ...")
    color_hex: str | None = Field(default=None, max_length=9, description="#RRGGBB or #RRGGBBAA")
    hotend_temp_min: int | None = Field(default=None, ge=0, le=500)
    hotend_temp_max: int | None = Field(default=None, ge=0, le=500)
    bed_temp: int | None = Field(default=None, ge=0, le=200)
    notes: str | None = Field(default=None)


class Filament(FilamentBase, TimestampMixin, table=True):
    __tablename__ = "filament"

    id: int | None = Field(default=None, primary_key=True)
    spoolman_filament_id: int | None = Field(default=None, unique=True, index=True)
    synced_at: datetime | None = Field(default=None)

    profiles: list["PrintProfile"] = Relationship(back_populates="filament")


class FilamentCreate(FilamentBase):
    spoolman_filament_id: int | None = None


class FilamentUpdate(SQLModel):
    name: str | None = None
    manufacturer: str | None = None
    material: str | None = None
    color_hex: str | None = None
    hotend_temp_min: int | None = None
    hotend_temp_max: int | None = None
    bed_temp: int | None = None
    notes: str | None = None


class FilamentRead(FilamentBase):
    id: int
    spoolman_filament_id: int | None
    synced_at: datetime | None
