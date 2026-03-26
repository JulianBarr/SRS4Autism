import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from cuma_cloud.core.database import Base


# ---------------------------------------------------------------------------
# 4A 架构 - ABAC 权限核心实体
# ---------------------------------------------------------------------------


class RoleEnum(str, enum.Enum):
    """ABAC 角色枚举：机构管理员、教师、家长、代理。"""

    QCQ_ADMIN = "qcq_admin"
    TEACHER = "teacher"
    PARENT = "parent"
    AGENT = "agent"


class InstitutionStatusEnum(str, enum.Enum):
    """租户/机构审批状态"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"


class Institution(Base):
    """机构：学校/康复中心，用于隔离多租户数据。"""

    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list["User"]] = relationship(
        "User", back_populates="institution", foreign_keys="User.institution_id"
    )
    children: Mapped[list["ChildProfile"]] = relationship(
        "ChildProfile", back_populates="institution", foreign_keys="ChildProfile.institution_id"
    )


class User(Base):
    """用户：ABAC 鉴权主体，关联机构与角色。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False, server_default="mock_hash")
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)
    institution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    institution_status: Mapped[Optional[InstitutionStatusEnum]] = mapped_column(
        Enum(InstitutionStatusEnum), nullable=True
    )

    institution: Mapped[Optional["Institution"]] = relationship(
        "Institution", back_populates="users", foreign_keys=[institution_id]
    )
    # 作为教师被分配的儿童
    assigned_children: Mapped[list["ChildProfile"]] = relationship(
        "ChildProfile", back_populates="assigned_teacher", foreign_keys="ChildProfile.assigned_teacher_id"
    )
    # 作为家长的儿童
    parent_children: Mapped[list["ChildProfile"]] = relationship(
        "ChildProfile", back_populates="parent", foreign_keys="ChildProfile.parent_id"
    )
    
    sent_iep_logs: Mapped[list["IepCommunicationLog"]] = relationship(
        "IepCommunicationLog", back_populates="sender", foreign_keys="IepCommunicationLog.sender_id"
    )
    # Administrative links to children (e.g., assignment links)
    child_links: Mapped[list["UserChildLink"]] = relationship(
        "UserChildLink", back_populates="user", cascade="all, delete-orphan", foreign_keys="UserChildLink.user_id"
    )


class UserChildLink(Base):
    """
    Mapping between User (Teacher) and Profile (Child).
    Used for administrative assignment of children to teachers.
    """
    __tablename__ = 'user_child_link'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    child_id: Mapped[int] = mapped_column(ForeignKey('child_profiles.id', ondelete='CASCADE'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="child_links", foreign_keys=[user_id])
    child: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="teacher_links", foreign_keys=[child_id])

class ChildProfile(Base):
    """
    儿童档案：ABAC 权限判定的资源实体。
    通过 institution_id、assigned_teacher_id、parent_id 三个外键判定访问权限。
    """

    __tablename__ = "child_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_teacher_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    institution: Mapped[Optional["Institution"]] = relationship(
        "Institution", back_populates="children", foreign_keys=[institution_id]
    )
    assigned_teacher: Mapped[Optional["User"]] = relationship(
        "User", back_populates="assigned_children", foreign_keys=[assigned_teacher_id]
    )
    parent: Mapped[Optional["User"]] = relationship(
        "User", back_populates="parent_children", foreign_keys=[parent_id]
    )

    iep_logs: Mapped[list["IepCommunicationLog"]] = relationship(
        "IepCommunicationLog", back_populates="child", foreign_keys="IepCommunicationLog.child_id"
    )
    ai_drafts: Mapped[list["IepAiDraft"]] = relationship(
        "IepAiDraft", back_populates="child", foreign_keys="IepAiDraft.child_id"
    )
    # Administrative links to teachers (e.g., assignment links)
    teacher_links: Mapped[list["UserChildLink"]] = relationship(
        "UserChildLink", back_populates="child", cascade="all, delete-orphan", foreign_keys="UserChildLink.child_id"
    )

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


class IepCommunicationLog(Base):
    """
    IEP 沟通与记录模块。
    用于记录老师、家长、AI围绕特定儿童的干预记录。
    """

    __tablename__ = "iep_communication_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    child: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="iep_logs", foreign_keys=[child_id])
    sender: Mapped["User"] = relationship("User", back_populates="sent_iep_logs", foreign_keys=[sender_id])

    ai_drafts: Mapped[list["IepAiDraft"]] = relationship(
        "IepAiDraft", back_populates="parent_log", cascade="all, delete-orphan", foreign_keys="IepAiDraft.parent_log_id"
    )


class IepAiDraft(Base):
    """
    AI 暂存的建议草稿，用于老师审核 (Human-in-the-loop)。
    """

    __tablename__ = "iep_ai_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_log_id: Mapped[int] = mapped_column(
        ForeignKey("iep_communication_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_content: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    child: Mapped["ChildProfile"] = relationship(
        "ChildProfile", back_populates="ai_drafts", foreign_keys=[child_id]
    )
    parent_log: Mapped["IepCommunicationLog"] = relationship(
        "IepCommunicationLog", back_populates="ai_drafts", foreign_keys=[parent_log_id]
    )
