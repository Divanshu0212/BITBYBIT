import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, ForeignKey, Integer, Float, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    freelancer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="draft", nullable=False
    )  # draft, decomposed, funded, active, completed
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_estimated_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decomposition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin",
        order_by="Milestone.index"
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    complexity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acceptance_criteria: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False
    )  # PENDING, IN_PROGRESS, WORK_SUBMITTED, AQA_REVIEW, PAID_FULL, PAID_PARTIAL, REFUND_INITIATED
    payment_amount: Mapped[float] = mapped_column(Float, default=0.0)
    payment_released: Mapped[float] = mapped_column(Float, default=0.0)
    submission: Mapped[str | None] = mapped_column(Text, nullable=True)
    submission_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    aqa_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="milestones")
