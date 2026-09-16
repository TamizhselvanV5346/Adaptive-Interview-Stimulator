from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResponseEvaluation(BaseModel):
    """Strongly typed evaluation of a candidate's answer against a competency."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    competency_id: UUID
    evidence_summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    relevance_score: float = Field(..., ge=0.0, le=5.0)
    depth_score: float = Field(..., ge=0.0, le=5.0)
    technical_accuracy_score: float = Field(..., ge=0.0, le=5.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    demonstrated_level: int = Field(..., ge=1, le=5)
    is_off_topic: bool = False
    off_topic_reason: str | None = None

    @field_validator("evidence_summary")
    @classmethod
    def validate_evidence_summary(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("evidence_summary cannot be blank")
        return value.strip()

    @field_validator("strengths", "gaps")
    @classmethod
    def validate_non_blank_strings(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Must be a list of strings")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("strength/gap strings cannot be blank")
            cleaned.append(item.strip())
        return cleaned

    @field_validator("demonstrated_level", mode="before")
    @classmethod
    def validate_demonstrated_level(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("demonstrated_level must be an integer between 1 and 5")
        if value < 1 or value > 5:
            raise ValueError("demonstrated_level must be between 1 and 5")
        return value
