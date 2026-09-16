from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FinalizeAssessmentInput(BaseModel):
    """Structured input payload for assessment finalization operation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    session_id: UUID
    organization_id: UUID
    final_turn: int = Field(default=0, ge=0)
    reason: str
    evidence_summary: str | None = None

    @field_validator("reason")
    @classmethod
    def validate_reason_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("reason cannot be blank")
        return value.strip()


class FinalizeAssessmentResult(BaseModel):
    """Authoritative structured output of the assessment finalization operation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    success: bool
    session_id: UUID
    organization_id: UUID
    previous_status: str
    new_status: str
    finalized_at: datetime | None = None
    message: str
    error_code: str | None = None
    error_detail: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("message cannot be blank")
        return value.strip()
