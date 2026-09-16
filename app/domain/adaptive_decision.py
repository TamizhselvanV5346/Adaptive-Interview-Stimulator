from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AdaptiveAction(str, Enum):
    """Actions the interview engine can take next."""

    PROBE = "PROBE"
    ESCALATE = "ESCALATE"
    ADVANCE = "ADVANCE"
    REDIRECT = "REDIRECT"
    COMPLETE = "COMPLETE"


class AdaptiveDecision(BaseModel):
    """Strongly typed decision contract indicating the next interview action."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    action: AdaptiveAction
    reason: str
    target_competency_id: UUID | None = None
    target_difficulty: int | None = Field(default=None, ge=1, le=5)
    confidence: float = Field(..., ge=0.0, le=1.0)
    based_on_turn: int = Field(..., ge=1)

    @field_validator("reason")
    @classmethod
    def validate_reason_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("reason cannot be blank")
        return value.strip()

    @field_validator("target_difficulty", mode="before")
    @classmethod
    def validate_target_difficulty_type(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("target_difficulty must be an integer between 1 and 5")
        if value < 1 or value > 5:
            raise ValueError("target_difficulty must be an integer between 1 and 5")
        return value

    @model_validator(mode="after")
    def validate_action_requirements(self) -> "AdaptiveDecision":
        if self.action == AdaptiveAction.ESCALATE:
            if self.target_difficulty is None:
                raise ValueError("target_difficulty is required for ESCALATE action")
            if self.target_competency_id is None:
                raise ValueError("target_competency_id is required for ESCALATE action")

        elif self.action in (AdaptiveAction.PROBE, AdaptiveAction.ADVANCE):
            if self.target_competency_id is None:
                raise ValueError(f"target_competency_id is required for {self.action.value} action")

        elif self.action == AdaptiveAction.COMPLETE:
            if self.target_difficulty is not None:
                raise ValueError("target_difficulty must be None for COMPLETE action")

        return self
