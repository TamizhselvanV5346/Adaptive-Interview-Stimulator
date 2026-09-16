from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.adaptive_decision import AdaptiveAction


class ConversationRecovery(BaseModel):
    """Domain model capturing conversational recovery for off-topic candidate responses."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
    )

    action: AdaptiveAction = AdaptiveAction.REDIRECT
    redirect_message: str
    original_question: Any = None
    original_question_text: str
    off_topic_reason: str | None = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=2, ge=1)
    should_re_evaluate: bool = True
    is_max_retries_exceeded: bool = False

    @field_validator("redirect_message")
    @classmethod
    def validate_redirect_message_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("redirect_message cannot be blank")
        return value.strip()

    @field_validator("original_question_text")
    @classmethod
    def validate_original_question_text_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("original_question_text cannot be blank")
        return value.strip()

    @field_validator("retry_count", mode="before")
    @classmethod
    def validate_retry_count_type(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("retry_count must be a non-negative integer")
        if value < 0:
            raise ValueError("retry_count must be non-negative")
        return value

    @field_validator("max_retries", mode="before")
    @classmethod
    def validate_max_retries_type(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("max_retries must be an integer >= 1")
        if value < 1:
            raise ValueError("max_retries must be at least 1")
        return value
