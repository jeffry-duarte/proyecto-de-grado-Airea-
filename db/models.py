from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    users: Mapped[list[User]] = relationship(back_populates="role_record")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_salt: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    password_scheme: Mapped[str] = mapped_column(
        String(16), nullable=False, default="bcrypt"
    )
    locality: Mapped[str] = mapped_column(String(100), nullable=False)
    favorite_station_id: Mapped[str] = mapped_column(String(80), nullable=False)
    health_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    legacy_role: Mapped[str] = mapped_column(
        "role", String(80), nullable=False, default="citizen"
    )
    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.id"), nullable=False, default="citizen"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    role_record: Mapped[Role] = relationship(back_populates="users")
