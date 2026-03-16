from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CloudAccount(Base):
    __tablename__ = "cloud_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
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
    """
    ABAC policy for Local-First authorization.
    Cloud defines and distributes rules; clients enforce them offline.
    """

    __tablename__ = "abac_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False)
    institution_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    policy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["CloudAccount"] = relationship("CloudAccount", back_populates="abac_policies")

    __table_args__ = (
        Index("idx_abac_institution", "institution_id"),
        Index("idx_abac_account_resource", "account_id", "resource_type"),
    )


class TelemetrySyncLog(Base):
    """
    High-throughput telemetry receiver for Local-First clients.
    Clients batch logs (FSRS reviews, usage metrics) and sync when online.
    Cloud stores as raw JSONB for future stream processing or federated learning.
    """

    __tablename__ = "telemetry_sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False)
    client_device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["CloudAccount"] = relationship("CloudAccount", back_populates="telemetry_logs")

    __table_args__ = (
        Index("idx_telemetry_account", "account_id"),
        Index("idx_telemetry_synced_at", "synced_at"),
        Index("idx_telemetry_event_type", "event_type"),
        Index("idx_telemetry_client_device", "client_device_id"),
    )
