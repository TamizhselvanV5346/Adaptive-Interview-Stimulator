from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.interview_session import (
    InterviewSession,
    InterviewSessionStatus,
)
from app.domain.assessment_operations import (
    FinalizeAssessmentInput,
    FinalizeAssessmentResult,
)


class AssessmentOperationsMCP:
    """Minimal Model Context Protocol (MCP) assessment operation handler.

    Exposes the authoritative `finalize_assessment` operation to conclude
    interview assessments, enforcing strict organization isolation and
    session lifecycle validation.
    """

    TOOL_NAME = "finalize_assessment"

    @classmethod
    def get_tool_definitions(cls) -> list[dict[str, Any]]:
        """Return the tool metadata schemas compliant with Model Context Protocol (MCP)."""
        return [
            {
                "name": cls.TOOL_NAME,
                "description": (
                    "Authoritatively finalize an interview assessment session, "
                    "transitioning database state to FINALIZED and recording completion."
                ),
                "inputSchema": FinalizeAssessmentInput.model_json_schema(),
            }
        ]

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute an MCP tool request conforming to standard MCP JSON-RPC conventions.

        Parameters
        ----------
        tool_name : str
            Name of the registered tool to invoke.
        arguments : dict
            Input payload matching the tool's JSON schema.
        db : AsyncSession
            Active database session for authoritative persistence.

        Returns
        -------
        dict
            Standard MCP tool execution response containing content blocks and error flags.
        """
        if tool_name != self.TOOL_NAME:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool '{tool_name}' is not recognized or permitted.",
                    }
                ],
                "isError": True,
                "result": None,
            }

        try:
            input_payload = FinalizeAssessmentInput(**arguments)
            result = await self.finalize_assessment(input_payload, db)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result.message,
                    }
                ],
                "isError": not result.success,
                "result": result.model_dump(mode="json"),
            }
        except Exception as exc:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool execution failed: {exc}",
                    }
                ],
                "isError": True,
                "result": None,
            }

    async def finalize_assessment(
        self,
        input_data: FinalizeAssessmentInput | dict[str, Any],
        db: AsyncSession,
    ) -> FinalizeAssessmentResult:
        """Authoritatively transition an interview session to FINALIZED status.

        Parameters
        ----------
        input_data : FinalizeAssessmentInput | dict
            Input parameters specifying session, organization, and finalization rationale.
        db : AsyncSession
            Database session to persist the state transition.

        Returns
        -------
        FinalizeAssessmentResult
            Structured result with previous and new statuses, timestamp, and audit details.
        """
        if isinstance(input_data, dict):
            try:
                input_payload = FinalizeAssessmentInput(**input_data)
            except Exception as exc:
                return FinalizeAssessmentResult(
                    success=False,
                    session_id=input_data.get("session_id", UUID(int=0)),
                    organization_id=input_data.get("organization_id", UUID(int=0)),
                    previous_status="UNKNOWN",
                    new_status="UNKNOWN",
                    message=f"Invalid finalize input schema: {exc}",
                    error_code="INVALID_INPUT",
                    error_detail=str(exc),
                )
        else:
            input_payload = input_data

        try:
            # Query session scoped strictly by organization_id (Tenant Isolation)
            session = await db.scalar(
                select(InterviewSession).where(
                    InterviewSession.id == input_payload.session_id,
                    InterviewSession.organization_id == input_payload.organization_id,
                )
            )

            if session is None:
                return FinalizeAssessmentResult(
                    success=False,
                    session_id=input_payload.session_id,
                    organization_id=input_payload.organization_id,
                    previous_status="NOT_FOUND",
                    new_status="NOT_FOUND",
                    message="Interview session was not found in this organization.",
                    error_code="INTERVIEW_SESSION_NOT_FOUND",
                )

            current_status = session.status

            # Validate state eligibility
            if current_status == InterviewSessionStatus.FINALIZED.value:
                return FinalizeAssessmentResult(
                    success=False,
                    session_id=session.id,
                    organization_id=session.organization_id,
                    previous_status=current_status,
                    new_status=current_status,
                    message="Interview session is already finalized. Repeated finalization is not permitted.",
                    error_code="ALREADY_FINALIZED",
                )

            if current_status == InterviewSessionStatus.CREATED.value:
                return FinalizeAssessmentResult(
                    success=False,
                    session_id=session.id,
                    organization_id=session.organization_id,
                    previous_status=current_status,
                    new_status=current_status,
                    message=f"Cannot finalize session with status '{current_status}'. Only IN_PROGRESS or COMPLETED sessions can be finalized.",
                    error_code="INVALID_SESSION_TRANSITION",
                )

            # Allowed transitions: IN_PROGRESS or COMPLETED -> FINALIZED
            now = datetime.now(timezone.utc)
            if session.completed_at is None:
                session.completed_at = now

            session.status = InterviewSessionStatus.FINALIZED.value
            if input_payload.final_turn > 0:
                session.current_turn = input_payload.final_turn

            await db.commit()
            await db.refresh(session)

            return FinalizeAssessmentResult(
                success=True,
                session_id=session.id,
                organization_id=session.organization_id,
                previous_status=current_status,
                new_status=InterviewSessionStatus.FINALIZED.value,
                finalized_at=now,
                message=f"Interview session {session.id} successfully finalized with status FINALIZED.",
            )

        except Exception as exc:
            await db.rollback()
            return FinalizeAssessmentResult(
                success=False,
                session_id=input_payload.session_id,
                organization_id=input_payload.organization_id,
                previous_status="ERROR",
                new_status="ERROR",
                message=f"Database state transition failed: {exc}",
                error_code="DATABASE_ERROR",
                error_detail=str(exc),
            )
