import json
import os
import re
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.ai.providers.base import (
    ResponseEvaluationProvider,
    extract_competency_details,
    extract_question_details,
)
from app.core.config import settings
from app.core.exceptions import ApplicationError
from app.domain.response_evaluation import ResponseEvaluation

CLAUDE_SYSTEM_PROMPT = (
    "You are an evidence-based interview evaluator. Evaluate only information "
    "supported by the candidate's answer. Do not invent experience or facts. "
    "Do not evaluate personality, psychological traits, honesty, or truthfulness. "
    "Do not make hiring decisions. Return only the requested structured evaluation."
)

TOOL_SCHEMA = {
    "name": "submit_response_evaluation",
    "description": "Submit structured evaluation of candidate answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "evidence_summary": {
                "type": "string",
                "description": "Evidence-based summary of what the candidate demonstrated. Must not be blank.",
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Demonstrated strengths observed in the response.",
            },
            "gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Areas of missing knowledge or missing expected signals.",
            },
            "relevance_score": {
                "type": "number",
                "description": "How directly the response addresses question and competency (0.0 to 5.0).",
            },
            "depth_score": {
                "type": "number",
                "description": "Depth of understanding and technical rigor shown (0.0 to 5.0).",
            },
            "technical_accuracy_score": {
                "type": "number",
                "description": "Technical correctness and precision (0.0 to 5.0).",
            },
            "confidence": {
                "type": "number",
                "description": "Evaluator confidence in this assessment (0.0 to 1.0).",
            },
            "demonstrated_level": {
                "type": "integer",
                "description": "Demonstrated proficiency level (integer 1 to 5).",
            },
            "is_off_topic": {
                "type": "boolean",
                "description": "True if the answer fails to address the question.",
            },
            "off_topic_reason": {
                "type": ["string", "null"],
                "description": "Reason why answer was marked off-topic, or null if on-topic.",
            },
        },
        "required": [
            "evidence_summary",
            "strengths",
            "gaps",
            "relevance_score",
            "depth_score",
            "technical_accuracy_score",
            "confidence",
            "demonstrated_level",
            "is_off_topic",
        ],
    },
}


class ClaudeProvider(ResponseEvaluationProvider):
    """Claude API provider for candidate response evaluation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.anthropic.com/v1/messages",
        timeout: float = 30.0,
    ):
        if api_key is not None:
            self._api_key = api_key.strip()
        else:
            raw_key = getattr(settings, "claude_api_key", "") or os.getenv("CLAUDE_API_KEY", "")
            self._api_key = raw_key.strip() if raw_key else ""
        self.model = model
        self._client = client
        self.base_url = base_url
        self.timeout = timeout

    def __repr__(self) -> str:
        # Never leak API key in repr
        return f"<ClaudeProvider(model='{self.model}', configured={bool(self._api_key)})>"

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def evaluate(
        self,
        question: Any,
        answer: str,
        competency: Any,
        *,
        job_context: str | None = None,
    ) -> ResponseEvaluation:
        if not self._api_key:
            raise ApplicationError(
                "Claude API key is not configured. Set CLAUDE_API_KEY in environment or settings.",
                "CLAUDE_AUTH_ERROR",
            )

        competency_id, comp_name, comp_desc = extract_competency_details(competency)
        effective_comp_id = competency_id or uuid4()

        _, q_text, expected_signal = extract_question_details(question)

        user_content_parts = []
        if job_context:
            user_content_parts.append(f"Job / Context: {job_context}")
        user_content_parts.extend([
            f"Competency Name: {comp_name}",
            f"Competency Description: {comp_desc}",
            f"Question Text: {q_text}",
            f"Expected Signal: {expected_signal}",
            f"Candidate Answer: {answer}",
        ])
        user_prompt = "\n\n".join(user_content_parts)

        payload = {
            "model": self.model,
            "max_tokens": 1500,
            "system": CLAUDE_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
            "tools": [TOOL_SCHEMA],
            "tool_choice": {
                "type": "tool",
                "name": "submit_response_evaluation",
            },
        }

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        client_to_use = self._client
        owns_client = False
        if client_to_use is None:
            client_to_use = httpx.AsyncClient(timeout=self.timeout)
            owns_client = True

        try:
            response = await client_to_use.post(
                self.base_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise ApplicationError(
                f"Claude API returned HTTP status {status_code}",
                "CLAUDE_API_ERROR",
            ) from None
        except httpx.RequestError:
            raise ApplicationError(
                "Failed to connect to Claude API endpoint",
                "CLAUDE_CONNECTION_ERROR",
            ) from None
        finally:
            if owns_client:
                await client_to_use.aclose()

        parsed_eval = self._parse_claude_response(data, effective_comp_id)
        return parsed_eval

    def _parse_claude_response(self, data: dict[str, Any], competency_id: UUID) -> ResponseEvaluation:
        """Extract tool use data or structured JSON content from Claude response and validate."""
        evaluation_data: dict[str, Any] | None = None

        content = data.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "submit_response_evaluation":
                    input_data = block.get("input")
                    if isinstance(input_data, dict):
                        evaluation_data = dict(input_data)
                        break

            # Fallback to text blocks with JSON
            if evaluation_data is None:
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_val = block.get("text", "")
                        json_match = re.search(r"\{.*\}", text_val, re.DOTALL)
                        if json_match:
                            try:
                                evaluation_data = json.loads(json_match.group(0))
                                break
                            except json.JSONDecodeError:
                                pass

        if not evaluation_data:
            raise ApplicationError(
                "Claude response did not contain expected structured evaluation tool call or JSON output",
                "MALFORMED_PROVIDER_OUTPUT",
            )

        evaluation_data["competency_id"] = competency_id

        try:
            return ResponseEvaluation.model_validate(evaluation_data)
        except Exception as exc:
            raise ApplicationError(
                f"Malformed evaluation returned by provider: {exc}",
                "MALFORMED_PROVIDER_OUTPUT",
            ) from exc
