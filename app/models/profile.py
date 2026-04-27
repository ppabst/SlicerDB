from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.filament import Filament
    from app.models.nozzle import Nozzle
    from app.models.printer import Printer
    from app.models.slicer import Slicer


# ---------- PrintProfile ----------

class PrintProfileBase(SQLModel):
    name: str = Field(index=True, min_length=1, max_length=160)
    layer_height_mm: float = Field(gt=0, le=2.0, description="e.g. 0.2")
    quality_label: str = Field(
        default="Standard",
        max_length=40,
        description="Draft / Standard / Fine / Custom",
    )
    notes: str | None = Field(default=None)


class PrintProfile(PrintProfileBase, TimestampMixin, table=True):
    __tablename__ = "print_profile"

    id: int | None = Field(default=None, primary_key=True)
    printer_id: int = Field(foreign_key="printer.id", index=True)
    nozzle_id: int = Field(foreign_key="nozzle.id", index=True)
    filament_id: int = Field(foreign_key="filament.id", index=True)
    slicer_id: int = Field(foreign_key="slicer.id", index=True)
    # Soft pointer to the currently active version; FK is intentionally not
    # declared at the DB level to avoid a circular constraint with
    # profile_version.profile_id. App code maintains referential integrity.
    active_version_id: int | None = Field(default=None, index=True)

    printer: "Printer" = Relationship(back_populates="profiles")
    nozzle: "Nozzle" = Relationship(back_populates="profiles")
    filament: "Filament" = Relationship(back_populates="profiles")
    slicer: "Slicer" = Relationship(back_populates="profiles")
    versions: list["ProfileVersion"] = Relationship(
        back_populates="profile",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[ProfileVersion.profile_id]",
            "order_by": "ProfileVersion.version_no.desc()",
        },
    )


class PrintProfileCreate(PrintProfileBase):
    printer_id: int
    nozzle_id: int
    filament_id: int
    slicer_id: int


class PrintProfileUpdate(SQLModel):
    name: str | None = None
    layer_height_mm: float | None = None
    quality_label: str | None = None
    notes: str | None = None
    nozzle_id: int | None = None
    filament_id: int | None = None
    slicer_id: int | None = None


class PrintProfileRead(PrintProfileBase):
    id: int
    printer_id: int
    nozzle_id: int
    filament_id: int
    slicer_id: int
    active_version_id: int | None


# ---------- ProfileVersion ----------

class ProfileVersionBase(SQLModel):
    change_note: str | None = Field(default=None, description="What changed vs. previous version")
    rating: str | None = Field(
        default=None,
        max_length=20,
        description="good / bad / untested / null",
    )
    rating_note: str | None = Field(default=None)


class ProfileVersion(ProfileVersionBase, table=True):
    __tablename__ = "profile_version"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="print_profile.id", index=True)
    version_no: int = Field(index=True, ge=1)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    settings_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Parsed slicer settings (Phase 3+); opaque blob until then",
    )

    raw_filename: str | None = Field(default=None, max_length=255)
    raw_format: str | None = Field(default=None, max_length=40)
    raw_blob_path: str | None = Field(
        default=None,
        max_length=500,
        description="Relative path under settings.files_dir",
    )

    profile: PrintProfile = Relationship(
        back_populates="versions",
        sa_relationship_kwargs={"foreign_keys": "[ProfileVersion.profile_id]"},
    )


class ProfileVersionRead(ProfileVersionBase):
    id: int
    profile_id: int
    version_no: int
    created_at: datetime
    raw_filename: str | None
    raw_format: str | None
