from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompetencyScore(BaseModel):
    """Deterministic score and aggregated evidence for a specific competency."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    competency_id: UUID
    competency_name: str
    target_level: int = Field(..., ge=1, le=5)
    demonstrated_level: float = Field(..., ge=0.0, le=5.0)
    score: float = Field(..., ge=0.0, le=100.0)
    weight: float = Field(default=1.0, ge=0.0)
    evidence_count: int = Field(default=0, ge=0)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("competency_name")
    @classmethod
    def validate_competency_name_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("competency_name cannot be blank")
        return value.strip()

    @field_validator("strengths", "gaps")
    @classmethod
    def validate_string_list(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Must be a list of strings")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("evidence items cannot be blank")
            cleaned.append(item.strip())
        return cleaned


class FinalAssessment(BaseModel):
    """Authoritative aggregated assessment report across all competencies evaluated."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    session_id: UUID
    competency_scores: list[CompetencyScore]
    overall_score: float = Field(..., ge=0.0, le=100.0)
    total_evidence_count: int = Field(default=0, ge=0)
    completed: bool = True
