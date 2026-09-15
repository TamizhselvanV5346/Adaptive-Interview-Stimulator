from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class JobIntakeRequest(BaseModel):
    """Payload submitted by the n8n intake workflow."""

    organization_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=255)

    job_title: str = Field(min_length=1, max_length=255)
    job_description: str = Field(min_length=1)
    seniority_level: str = Field(min_length=1, max_length=50)

    interview_name: str = Field(min_length=1, max_length=255)

    @field_validator(
        "idempotency_key",
        "job_title",
        "job_description",
        "seniority_level",
        "interview_name",
    )
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value cannot be blank")

        return value


class JobIntakeResponse(BaseModel):
    """Response returned after successful intake processing."""

    organization_id: UUID
    job_id: UUID
    interview_definition_id: UUID
    status: str
    idempotent: bool = False