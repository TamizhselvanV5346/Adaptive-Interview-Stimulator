from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InterviewCompetency(Base):
    __tablename__ = "interview_competencies"

    __table_args__ = (
        UniqueConstraint(
            "interview_definition_id",
            "competency_id",
            name="uq_interview_competency",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    interview_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_definitions.id"),
        nullable=False,
        index=True,
    )

    competency_id: Mapped[UUID] = mapped_column(
        ForeignKey("competencies.id"),
        nullable=False,
        index=True,
    )

    weight: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=1.0,
    )

    target_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )