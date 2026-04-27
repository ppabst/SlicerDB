from typing import TYPE_CHECKING, Literal

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import PrintProfile

ProfileFormat = Literal["orca-json", "prusa-ini", "cura-profile", "other"]


class SlicerBase(SQLModel):
    name: str = Field(index=True, min_length=1, max_length=80)
    version: str | None = Field(default=None, max_length=40)
    profile_format: str = Field(
        default="orca-json",
        max_length=40,
        description="orca-json | prusa-ini | cura-profile | other",
    )


class Slicer(SlicerBase, TimestampMixin, table=True):
    __tablename__ = "slicer"

    id: int | None = Field(default=None, primary_key=True)

    profiles: list["PrintProfile"] = Relationship(back_populates="slicer")


class SlicerCreate(SlicerBase):
    pass


class SlicerUpdate(SQLModel):
    name: str | None = None
    version: str | None = None
    profile_format: str | None = None


class SlicerRead(SlicerBase):
    id: int
