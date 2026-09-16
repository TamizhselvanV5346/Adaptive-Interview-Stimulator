from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CandidateResponse(Base):
    """Persistent record of a candidate's answer and evaluation for a turn."""

    __tablename__ = "candidate_responses"

    __table_args__ = (
        CheckConstraint(
            "turn_number >= 0",
            name="chk_candidate_response_turn_number_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    interview_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"),
        nullable=False,
        index=True,
    )

    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id"),
        nullable=False,
        index=True,
    )

    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    candidate_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    evaluation_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
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
