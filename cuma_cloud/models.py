from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CloudAccount(Base):
    __tablename__ = "cloud_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    abac_policies: Mapped[list["ABACPolicy"]] = relationship(
        "ABACPolicy", back_populates="account", cascade="all, delete-orphan"
    )
    telemetry_logs: Mapped[list["TelemetrySyncLog"]] = relationship(
        "TelemetrySyncLog", back_populates="account", cascade="all, delete-orphan"
    )


class ABACPolicy(Base):
    __tablename__ = "abac_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["CloudAccount"] = relationship("CloudAccount", back_populates="abac_policies")

    __table_args__ = (
        Index("idx_abac_account_subject", "account_id", "subject"),
        Index("idx_abac_account_resource", "account_id", "resource"),
    )


class TelemetrySyncLog(Base):
    __tablename__ = "telemetry_sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["CloudAccount"] = relationship("CloudAccount", back_populates="telemetry_logs")

    __table_args__ = (
        Index("idx_telemetry_account", "account_id"),
        Index("idx_telemetry_synced_at", "synced_at"),
        Index("idx_telemetry_event_type", "event_type"),
    )
