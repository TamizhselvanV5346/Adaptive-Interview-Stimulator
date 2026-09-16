from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.adaptive_decision import AdaptiveAction


class FollowUpReasoning(BaseModel):
    """User-facing structured explanation of why a specific follow-up interview action was chosen."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    action: AdaptiveAction
    reason: str
    evidence_basis: list[str] = Field(default_factory=list)
    competency_name: str | None = None
    difficulty_change: int | None = Field(default=None, ge=-4, le=4)
    user_visible: bool = True

    @field_validator("reason")
    @classmethod
    def validate_reason_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("reason cannot be blank")
        return value.strip()

    @field_validator("evidence_basis")
    @classmethod
    def validate_evidence_basis(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list) or not value:
            raise ValueError("evidence_basis cannot be empty or blank")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("evidence_basis items cannot be blank")
            cleaned.append(item.strip())
        return cleaned

    @field_validator("difficulty_change", mode="before")
    @classmethod
    def validate_difficulty_change_type(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("difficulty_change must be an integer between -4 and 4")
        if value < -4 or value > 4:
            raise ValueError("difficulty_change must be an integer between -4 and 4")
        return value
