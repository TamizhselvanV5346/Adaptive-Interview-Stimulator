from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompetencyReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    competency_id: UUID
    competency_name: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=100.0)
    demonstrated_level: float = Field(..., ge=0.0, le=5.0)
    target_level: int = Field(..., ge=1, le=5)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.0)

    @field_validator("competency_name")
    @classmethod
    def validate_non_blank_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("competency_name cannot be empty or blank")
        return trimmed

    @field_validator("strengths", "gaps")
    @classmethod
    def validate_string_list(cls, items: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in items:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("Evidence entries must be non-empty strings")
            cleaned.append(item.strip())
        return cleaned


class AssessmentReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    overall_score: float = Field(..., ge=0.0, le=100.0)
    completed: bool = True
    competency_reports: list[CompetencyReport] = Field(default_factory=list)
    total_evidence_count: int = Field(default=0, ge=0)
    candidate_id: UUID | None = None
    session_title: str | None = None
