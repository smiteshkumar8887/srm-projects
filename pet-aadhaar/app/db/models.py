from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    pets: Mapped[list["Pet"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class Pet(Base):
    __tablename__ = "pets"
    __table_args__ = (UniqueConstraint("name", name="uq_pet_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    breed: Mapped[str] = mapped_column(String(120))
    age_years: Mapped[int] = mapped_column(Integer, default=0)
    age_months: Mapped[int] = mapped_column(Integer, default=0)
    species: Mapped[str] = mapped_column(String(64), default="Dog")
    color: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    aadhaar_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    vaccination_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vaccination_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qr_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped["User"] = relationship(back_populates="pets")
