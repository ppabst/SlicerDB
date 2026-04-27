from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.nozzle import Nozzle
    from app.models.profile import PrintProfile


class PrinterBase(SQLModel):
    name: str = Field(index=True, min_length=1, max_length=120)
    manufacturer: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    build_volume: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None)


class Printer(PrinterBase, TimestampMixin, table=True):
    __tablename__ = "printer"

    id: int | None = Field(default=None, primary_key=True)

    nozzles: list["Nozzle"] = Relationship(
        back_populates="printer",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    profiles: list["PrintProfile"] = Relationship(back_populates="printer")


class PrinterCreate(PrinterBase):
    pass


class PrinterUpdate(SQLModel):
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    build_volume: str | None = None
    notes: str | None = None


class PrinterRead(PrinterBase):
    id: int
