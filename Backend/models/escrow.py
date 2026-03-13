import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class EscrowAccount(Base):
    __tablename__ = "escrow_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    total_funds: Mapped[float] = mapped_column(Float, default=0.0)
    locked_funds: Mapped[float] = mapped_column(Float, default=0.0)
    released_funds: Mapped[float] = mapped_column(Float, default=0.0)
    refunded_funds: Mapped[float] = mapped_column(Float, default=0.0)
    state: Mapped[str] = mapped_column(String(50), default="CREATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(
        back_populates="escrow", cascade="all, delete-orphan", lazy="selectin",
        order_by="LedgerEntry.timestamp"
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    escrow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("escrow_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # DEPOSIT, PAYMENT, REFUND, STATE_CHANGE
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tx_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 chain hash
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)

    escrow: Mapped["EscrowAccount"] = relationship(back_populates="ledger_entries")
