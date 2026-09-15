from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class QuestionType(str, Enum):
    BEHAVIORAL = "BEHAVIORAL"
    TECHNICAL = "TECHNICAL"
    SCENARIO = "SCENARIO"
    FOLLOW_UP = "FOLLOW_UP"


class Question(Base):
    __tablename__ = "questions"

    __table_args__ = (
        CheckConstraint(
            "difficulty_level >= 1 AND difficulty_level <= 5",
            name="chk_question_difficulty_level",
        ),
        CheckConstraint(
            "display_order >= 1",
            name="chk_question_display_order",
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

    interview_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_definitions.id"),
        nullable=False,
        index=True,
    )

    competency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("competencies.id"),
        nullable=True,
        index=True,
        default=None,
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    question_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=QuestionType.TECHNICAL.value,
    )

    difficulty_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    expected_signal: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
