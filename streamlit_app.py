import asyncio
from datetime import datetime, timezone
import os
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import streamlit as st

# Ensure app package is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app.ai.providers.claude import ClaudeProvider
from app.ai.providers.mock import MockProvider
from app.ai.response_intelligence import ResponseIntelligenceService
from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.assessment_report import AssessmentReport
from app.domain.competency_scoring import FinalAssessment
from app.domain.follow_up_reasoning import FollowUpReasoning
from app.evaluation.competency_scoring import CompetencyScoringService
from app.interview.adaptive_decision import AdaptiveDecisionEngine
from app.interview.conversation_recovery import ConversationRecoveryService
from app.interview.demo_data import (
    COMP_DISTRIBUTED_SYSTEMS_ID,
    COMP_INCIDENT_RELIABILITY_ID,
    COMP_PYTHON_PERFORMANCE_ID,
    COMP_SYSTEM_ARCHITECTURE_ID,
    DEMO_INTERVIEW_PROFILES,
    DEMO_QUESTIONS,
    InMemoryQuestionSelector,
)
from app.interview.follow_up_reasoning import FollowUpReasoningService
from app.interview.graph_state import InterviewGraphState
from app.interview.orchestrator import AdaptiveInterviewOrchestrator
from app.reporting.assessment_report import AssessmentReportService
from app.reporting.pdf_report import PDFReportGenerator

# ---------------------------------------------------------------------------
# Streamlit Page Config & Custom Design System CSS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Adaptive Interview Simulator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Header & Card Containers */
.main-header {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    padding: 24px;
    border-radius: 12px;
    color: white;
    margin-bottom: 24px;
    border: 1px solid #334155;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.question-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.dark-mode .question-card {
    background: #1e293b;
    border-color: #334155;
}

/* Action Badges */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.badge-probe {
    background-color: #fef3c7;
    color: #b45309;
    border: 1px solid #fcd34d;
}

.badge-escalate {
    background-color: #f3e8ff;
    color: #7e22ce;
    border: 1px solid #d8b4fe;
}

.badge-advance {
    background-color: #e0e7ff;
    color: #4338ca;
    border: 1px solid #a5b4fc;
}

.badge-redirect {
    background-color: #ffedd5;
    color: #c2410c;
    border: 1px solid #fdba74;
}

.badge-complete {
    background-color: #dcfce7;
    color: #15803d;
    border: 1px solid #86efac;
}

/* Why This Follow-Up Box */
.why-follow-up-box {
    background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
    border-left: 5px solid #2563eb;
    border-top: 1px solid #dbeafe;
    border-right: 1px solid #dbeafe;
    border-bottom: 1px solid #dbeafe;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 16px 0 24px 0;
}

.why-follow-up-title {
    color: #1e40af;
    font-weight: 700;
    font-size: 1.05rem;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.why-follow-up-text {
    color: #1e293b;
    font-size: 0.95rem;
    line-height: 1.5;
}

/* Redirect Alert Box */
.redirect-box {
    background: #fff7ed;
    border-left: 5px solid #ea580c;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 20px;
    border-top: 1px solid #ffedd5;
    border-right: 1px solid #ffedd5;
    border-bottom: 1px solid #ffedd5;
}

.redirect-title {
    color: #c2410c;
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 4px;
}

/* Score Metric Box */
.score-overview-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: white;
    padding: 24px;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 24px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

.score-number {
    font-size: 3.5rem;
    font-weight: 800;
    color: #38bdf8;
    line-height: 1;
    margin: 12px 0;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
def init_session_state() -> None:
    if "screen" not in st.session_state:
        st.session_state.screen = "SETUP"

    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid4()

    if "candidate_name" not in st.session_state:
        st.session_state.candidate_name = "Alex Mercer"

    if "candidate_id" not in st.session_state:
        st.session_state.candidate_id = uuid4()

    if "selected_profile_name" not in st.session_state:
        st.session_state.selected_profile_name = list(DEMO_INTERVIEW_PROFILES.keys())[0]

    if "provider_choice" not in st.session_state:
        st.session_state.provider_choice = "Demo / Mock"

    if "current_turn" not in st.session_state:
        st.session_state.current_turn = 1

    if "min_turns" not in st.session_state:
        st.session_state.min_turns = 8

    if "max_turns" not in st.session_state:
        st.session_state.max_turns = 12

    if "used_question_ids" not in st.session_state:
        st.session_state.used_question_ids = []

    if "history" not in st.session_state:
        st.session_state.history = []

    if "evaluations_list" not in st.session_state:
        st.session_state.evaluations_list = []

    if "last_action" not in st.session_state:
        st.session_state.last_action = None

    if "last_why_this_follow_up" not in st.session_state:
        st.session_state.last_why_this_follow_up = None

    if "redirect_message" not in st.session_state:
        st.session_state.redirect_message = None

    if "retry_count" not in st.session_state:
        st.session_state.retry_count = 0

    if "final_assessment" not in st.session_state:
        st.session_state.final_assessment = None

    if "assessment_report" not in st.session_state:
        st.session_state.assessment_report = None

    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None

    if "current_answer_draft" not in st.session_state:
        st.session_state.current_answer_draft = ""


init_session_state()


# ---------------------------------------------------------------------------
# Helper: Build Orchestrator
# ---------------------------------------------------------------------------
def build_orchestrator(provider_choice: str) -> AdaptiveInterviewOrchestrator:
    if provider_choice == "Claude":
        claude_provider = ClaudeProvider()
        if not claude_provider.is_configured:
            st.warning("⚠️ Claude API key not configured. Falling back to Demo/Mock provider.")
            provider = MockProvider()
        else:
            provider = claude_provider
    else:
        provider = MockProvider()

    response_service = ResponseIntelligenceService(provider=provider)
    decision_engine = AdaptiveDecisionEngine()
    reasoning_service = FollowUpReasoningService()
    recovery_service = ConversationRecoveryService()
    question_selector = InMemoryQuestionSelector(DEMO_QUESTIONS)

    return AdaptiveInterviewOrchestrator(
        response_service=response_service,
        decision_engine=decision_engine,
        reasoning_service=reasoning_service,
        recovery_service=recovery_service,
        question_selector=question_selector,
    )


# ---------------------------------------------------------------------------
# Sidebar UI
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎯 Adaptive Interview")
    st.caption("AI-Powered Evidence-Based Assessment Engine")

    st.markdown("---")
    st.markdown("#### ⚙️ Evaluation Provider")
    provider_option = st.radio(
        "AI Provider",
        ["Demo / Mock", "Claude"],
        index=0 if st.session_state.provider_choice == "Demo / Mock" else 1,
        help="Demo/Mock runs completely offline with deterministic adaptive logic. Claude uses Anthropic API.",
    )
    st.session_state.provider_choice = provider_option

    if provider_option == "Claude":
        claude_test = ClaudeProvider()
        if not claude_test.is_configured:
            st.info("ℹ️ Claude credentials not detected. Demo mode will be used automatically.")
        else:
            st.success("✅ Claude credentials active")

    st.markdown("---")
    st.markdown("#### 📊 Session Metadata")
    st.text(f"Session ID: {str(st.session_state.session_id)[:8]}...")
    st.text(f"Candidate: {st.session_state.candidate_name}")
    st.text(f"State: {st.session_state.screen}")

    if st.session_state.screen == "INTERVIEW":
        progress_val = min(1.0, (st.session_state.current_turn - 1) / max(1, st.session_state.min_turns))
        st.progress(progress_val)
        st.write(f"**Turn {st.session_state.current_turn} of {st.session_state.min_turns}** (Max: {st.session_state.max_turns})")

    st.markdown("---")
    if st.button("🔄 Reset / New Interview"):
        st.session_state.clear()
        init_session_state()
        st.rerun()


# ---------------------------------------------------------------------------
# SCREEN 1: Interview Setup
# ---------------------------------------------------------------------------
if st.session_state.screen == "SETUP":
    st.markdown(
        """
        <div class="main-header">
            <h1 style="margin:0; font-size:2rem; font-weight:800; color:white;">🎯 Adaptive Interview Simulator</h1>
            <p style="margin:8px 0 0 0; color:#94a3b8; font-size:1.05rem;">
                Evidence-Based Dynamic Interview Engine with Real-Time Adaptation & Competency Scoring
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 2], gap="large")

    with col1:
        st.markdown("### 📋 Interview Configuration")
        profile_names = list(DEMO_INTERVIEW_PROFILES.keys())
        selected_prof = st.selectbox(
            "Select Job & Seniority Profile",
            profile_names,
            index=0,
            help="Choose a pre-configured intake definition or customize below.",
        )
        st.session_state.selected_profile_name = selected_prof
        profile_data = DEMO_INTERVIEW_PROFILES[selected_prof]

        st.text_input("Job Title", value=profile_data["job_title"], disabled=True)
        st.text_input("Seniority Level", value=profile_data["seniority"], disabled=True)
        st.text_area("Job Description", value=profile_data["description"], height=80, disabled=True)

        st.markdown("#### 🎯 Target Competencies")
        for comp in profile_data["competencies"]:
            with st.container():
                st.markdown(
                    f"**{comp.name}**  \n"
                    f"*Target Level:* `{comp.target_level}/5` | *Weight:* `{comp.weight}`  \n"
                    f"<span style='color:#64748b; font-size:0.9rem;'>{comp.description}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("<hr style='margin:8px 0;'/>", unsafe_allow_html=True)

    with col2:
        st.markdown("### 👤 Candidate Details")
        c_name = st.text_input("Candidate Name", value=st.session_state.candidate_name)
        st.session_state.candidate_name = c_name

        st.text_input("Candidate ID", value=str(st.session_state.candidate_id), disabled=True)

        st.markdown("#### ⚙️ Turn Limits")
        min_t = st.number_input("Minimum Turns", min_value=8, max_value=15, value=8, step=1)
        max_t = st.number_input("Maximum Turns", min_value=min_t, max_value=20, value=12, step=1)
        st.session_state.min_turns = min_t
        st.session_state.max_turns = max_t

        st.markdown(
            """
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; margin:20px 0;">
                <h4 style="margin-top:0; color:#1e293b;">🚀 Adaptive Process Features</h4>
                <ul style="margin-bottom:0; padding-left:20px; font-size:0.9rem; color:#475569;">
                    <li>One question presented at a time</li>
                    <li>Real-time response intelligence evaluation</li>
                    <li>Deterministic decision: <b>PROBE</b>, <b>ESCALATE</b>, <b>ADVANCE</b>, <b>REDIRECT</b></li>
                    <li>Transparent <b>Why This Follow-Up</b> rationales</li>
                    <li>Off-topic recovery handling</li>
                    <li>Downloadable PDF assessment report</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🚀 Start Adaptive Interview", type="primary"):
            profile = DEMO_INTERVIEW_PROFILES[st.session_state.selected_profile_name]
            st.session_state.interview_competencies = profile["competencies"]
            first_comp = profile["competencies"][0]
            st.session_state.current_competency = first_comp
            st.session_state.current_difficulty = 2

            # Select initial question
            selector = InMemoryQuestionSelector(DEMO_QUESTIONS)
            q0 = asyncio.run(
                selector(
                    competency_id=first_comp.id,
                    difficulty_level=st.session_state.current_difficulty,
                    used_question_ids=[],
                )
            )
            st.session_state.current_question = q0
            if q0:
                st.session_state.used_question_ids = [q0.id]
            st.session_state.current_turn = 1
            st.session_state.screen = "INTERVIEW"
            st.rerun()


# ---------------------------------------------------------------------------
# SCREEN 2: Active Interview Screen
# ---------------------------------------------------------------------------
elif st.session_state.screen == "INTERVIEW":
    profile_data = DEMO_INTERVIEW_PROFILES.get(
        st.session_state.selected_profile_name,
        list(DEMO_INTERVIEW_PROFILES.values())[0],
    )
    current_q = st.session_state.current_question
    current_comp = st.session_state.current_competency
    current_diff = st.session_state.current_difficulty
    turn_num = st.session_state.current_turn

    # Top Status Bar
    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; background:#0f172a; color:white; padding:14px 20px; border-radius:10px; margin-bottom:16px;">
            <div>
                <span style="font-weight:700; font-size:1.1rem;">{profile_data['job_title']}</span>
                <span style="color:#94a3b8; margin-left:8px; font-size:0.9rem;">({profile_data['seniority']})</span>
            </div>
            <div style="font-weight:700; font-size:1.1rem; color:#38bdf8;">
                Turn {turn_num} of {st.session_state.min_turns}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Action Badge & Why This Follow-Up Banner (from preceding turn)
    if st.session_state.last_action and st.session_state.last_why_this_follow_up:
        act = st.session_state.last_action.upper()
        badge_class = f"badge-{act.lower()}"
        act_icon = {
            "PROBE": "🔍 PROBE",
            "ESCALATE": "🚀 ESCALATE",
            "ADVANCE": "⏩ ADVANCE",
            "REDIRECT": "🔄 REDIRECT",
            "COMPLETE": "🏁 COMPLETE",
        }.get(act, act)

        st.markdown(
            f"""
            <div class="why-follow-up-box">
                <div style="display:flex; align-items:center; justify-content:space-between;">
                    <span class="why-follow-up-title">
                        💡 Why This Follow-Up
                    </span>
                    <span class="badge {badge_class}">{act_icon}</span>
                </div>
                <div class="why-follow-up-text">
                    {st.session_state.last_why_this_follow_up}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2. Redirect Notice if previous answer was off-topic
    if st.session_state.redirect_message:
        st.markdown(
            f"""
            <div class="redirect-box">
                <div class="redirect-title">⚠️ Topic Focus Request</div>
                <div style="color:#7c2d12; font-size:0.95rem;">{st.session_state.redirect_message}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 3. Current Question Card
    comp_name = getattr(current_comp, "name", "Core Engineering")
    diff_stars = "★" * current_diff + "☆" * (5 - current_diff)
    q_text = getattr(current_q, "question_text", "Please describe your technical background.")

    st.markdown(
        f"""
        <div class="question-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <span style="background:#f1f5f9; color:#334155; padding:4px 10px; border-radius:6px; font-size:0.85rem; font-weight:600;">
                    🎯 Competency: {comp_name}
                </span>
                <span style="color:#eab308; font-weight:700; font-size:0.95rem;">
                    Difficulty {current_diff}/5 <span style="font-size:1.1rem;">{diff_stars}</span>
                </span>
            </div>
            <h3 style="margin:0; font-size:1.3rem; font-weight:700; color:#0f172a; line-height:1.4;">
                {q_text}
            </h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4. Candidate Response Area
    st.markdown("#### ✍️ Candidate Response")

    # Interactive sample answers to test adaptive behaviors quickly
    st.markdown("<span style='font-size:0.85rem; color:#64748b;'>Quick-fill sample answers for testing:</span>", unsafe_allow_html=True)
    c_btn1, c_btn2, c_btn3, c_btn4 = st.columns(4)

    with c_btn1:
        if st.button("🟢 Strong Technical Answer"):
            st.session_state.current_answer_draft = (
                f"In our architecture for {comp_name}, we implemented an event-driven consensus pattern using Raft "
                "with partitioned Kafka topics. We guaranteed idempotency via unique UUID transaction keys stored in a distributed "
                "Redis cache with strict TTLs. During node failovers, circuit breakers prevent cascading outages while backpressure "
                "and observability metrics trigger automatic canary rollbacks."
            )
            st.rerun()

    with c_btn2:
        if st.button("🟡 Weak Answer (Gaps)"):
            st.session_state.current_answer_draft = (
                "I am not sure about all the details. We used a standard database, but I haven't worked much with "
                "distributed consensus or handling partition splits directly."
            )
            st.rerun()

    with c_btn3:
        if st.button("🔴 Off-Topic Answer"):
            st.session_state.current_answer_draft = (
                "I cooked biryani yesterday for my family and it tasted really great with chicken and basmati rice."
            )
            st.rerun()

    with c_btn4:
        if st.button("🧹 Clear Input"):
            st.session_state.current_answer_draft = ""
            st.rerun()

    candidate_answer = st.text_area(
        "Candidate Answer",
        value=st.session_state.current_answer_draft,
        placeholder="Type candidate response here...",
        height=140,
        label_visibility="collapsed",
    )

    sub_col1, sub_col2 = st.columns([1, 4])
    with sub_col1:
        submit_clicked = st.button("Submit Answer ➔", type="primary")

    if submit_clicked:
        if not candidate_answer.strip():
            st.error("Please enter a response before submitting.")
        else:
            with st.spinner("Analyzing candidate response & calculating adaptive decision..."):
                orchestrator = build_orchestrator(st.session_state.provider_choice)

                # Prepare graph state
                graph_state: InterviewGraphState = {
                    "session_id": st.session_state.session_id,
                    "organization_id": getattr(current_q, "organization_id", uuid4()),
                    "interview_definition_id": getattr(current_q, "interview_definition_id", uuid4()),
                    "current_turn": turn_num,
                    "min_turns": st.session_state.min_turns,
                    "max_turns": st.session_state.max_turns,
                    "candidate_response": candidate_answer.strip(),
                    "current_question": current_q,
                    "current_competency": current_comp,
                    "current_difficulty": current_diff,
                    "interview_competencies": st.session_state.interview_competencies,
                    "used_question_ids": st.session_state.used_question_ids,
                    "retry_count": st.session_state.retry_count,
                    "remaining_eligible_questions": True,
                }

                # Run LangGraph turn
                result_state = asyncio.run(orchestrator.run_turn(graph_state))

                evaluation = result_state.get("response_evaluation")
                decision = result_state.get("adaptive_decision")
                action_val = result_state.get("action")
                action_str = action_val.value if isinstance(action_val, AdaptiveAction) else str(action_val)
                why_follow_up = result_state.get("why_this_follow_up")
                status = result_state.get("interview_status")

                # Store turn in history
                st.session_state.history.append({
                    "turn": turn_num,
                    "question": q_text,
                    "competency": comp_name,
                    "difficulty": current_diff,
                    "answer": candidate_answer.strip(),
                    "evaluation": evaluation,
                    "decision": decision,
                    "action": action_str,
                    "why_this_follow_up": why_follow_up,
                })

                if evaluation:
                    st.session_state.evaluations_list.append(evaluation)

                st.session_state.last_action = action_str
                st.session_state.last_why_this_follow_up = why_follow_up
                st.session_state.current_answer_draft = ""

                # Handle routing outcome
                if status == "REDIRECTED" or action_str == "REDIRECT":
                    st.session_state.redirect_message = result_state.get("redirect_message")
                    st.session_state.retry_count = result_state.get("retry_count", st.session_state.retry_count + 1)
                    # Stay on same question and turn
                    st.rerun()

                st.session_state.redirect_message = None
                st.session_state.retry_count = 0

                if status == "COMPLETED" or action_str == "COMPLETE" or turn_num >= st.session_state.max_turns:
                    # Finalize interview
                    scoring_svc = CompetencyScoringService()
                    final_assessment = scoring_svc.score_interview(
                        session_id=st.session_state.session_id,
                        interview_competencies=st.session_state.interview_competencies,
                        evaluations=st.session_state.evaluations_list,
                        completed=True,
                    )
                    st.session_state.final_assessment = final_assessment

                    report_svc = AssessmentReportService()
                    assessment_report = report_svc.generate_report(
                        assessment=final_assessment,
                        candidate_id=st.session_state.candidate_id,
                        session_title=profile_data["job_title"],
                    )
                    st.session_state.assessment_report = assessment_report

                    pdf_gen = PDFReportGenerator()
                    pdf_bytes = pdf_gen.generate(assessment_report)
                    st.session_state.pdf_bytes = pdf_bytes

                    st.session_state.screen = "ASSESSMENT"
                    st.rerun()
                else:
                    # Advance to next question & increment turn
                    next_q = result_state.get("next_question")
                    next_comp = result_state.get("next_competency")
                    next_diff = result_state.get("next_difficulty") or current_diff

                    st.session_state.current_turn = turn_num + 1
                    if next_q:
                        st.session_state.current_question = next_q
                        if hasattr(next_q, "id") and next_q.id not in st.session_state.used_question_ids:
                            st.session_state.used_question_ids.append(next_q.id)

                    if next_comp:
                        st.session_state.current_competency = next_comp
                    if next_diff:
                        st.session_state.current_difficulty = next_diff

                    st.rerun()

    # 5. Collapsible Transcript & Adaptation Journey
    if st.session_state.history:
        with st.expander("📜 Interview Transcript & Adaptation Journey", expanded=False):
            for item in reversed(st.session_state.history):
                st.markdown(
                    f"**Turn {item['turn']}** &mdash; *Competency:* `{item['competency']}` (Diff: `{item['difficulty']}`)  \n"
                    f"**Q:** {item['question']}  \n"
                    f"**A:** *{item['answer']}*  \n"
                    f"**Action:** `{item['action']}` | **Why This Follow-Up:** {item['why_this_follow_up']}"
                )
                st.markdown("<hr style='margin:8px 0;'/>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SCREEN 3: Final Assessment & PDF Report
# ---------------------------------------------------------------------------
elif st.session_state.screen == "ASSESSMENT":
    assessment: FinalAssessment = st.session_state.final_assessment
    report: AssessmentReport = st.session_state.assessment_report
    pdf_bytes: bytes = st.session_state.pdf_bytes

    st.markdown(
        """
        <div class="main-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 style="margin:0; font-size:2rem; font-weight:800; color:white;">🏁 Interview Complete</h1>
                    <p style="margin:6px 0 0 0; color:#94a3b8; font-size:1rem;">
                        Objective Evidence-Based Competency Assessment Report
                    </p>
                </div>
                <span class="badge badge-complete" style="font-size:1rem; padding:8px 16px;">COMPLETED</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Score Overview Box
    score_col, summary_col = st.columns([1, 2], gap="large")

    with score_col:
        st.markdown(
            f"""
            <div class="score-overview-card">
                <div style="color:#94a3b8; font-size:0.95rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;">
                    Overall Weighted Score
                </div>
                <div class="score-number">{assessment.overall_score:.1f}</div>
                <div style="color:#cbd5e1; font-size:0.9rem;">out of 100.0</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if pdf_bytes:
            st.download_button(
                label="📄 Download Assessment Report (PDF)",
                data=pdf_bytes,
                file_name="adaptive_interview_assessment.pdf",
                mime="application/pdf",
                type="primary",
            )

    with summary_col:
        st.markdown("### 📊 Assessment Summary")
        st.markdown(
            f"- **Candidate:** {st.session_state.candidate_name}  \n"
            f"- **Job Profile:** {st.session_state.selected_profile_name}  \n"
            f"- **Total Evidence Turns:** {assessment.total_evidence_count}  \n"
            f"- **Competencies Evaluated:** {len(assessment.competency_scores)}  \n"
            f"- **Session ID:** `{str(st.session_state.session_id)}`"
        )
        st.info(
            "ℹ️ **Assessment Methodology Note:** Scores are mathematically aggregated from deterministic response "
            "evaluations across interview turns. This report provides objective competency signal based strictly on "
            "demonstrated evidence and does not make automated hiring or placement decisions."
        )

    st.markdown("---")
    st.markdown("### 📋 Competency Score Breakdown")

    # Table breakdown
    table_data = []
    for cs in assessment.competency_scores:
        table_data.append({
            "Competency": cs.competency_name,
            "Score": f"{cs.score:.1f} / 100",
            "Demonstrated Level": f"{cs.demonstrated_level:.1f} / 5",
            "Target Level": f"{cs.target_level} / 5",
            "Confidence": f"{cs.confidence * 100:.0f}%",
            "Weight": f"{cs.weight:.1f}",
            "Evidence Count": cs.evidence_count,
        })
    st.dataframe(table_data)

    # Detailed Strengths & Gaps per Competency
    st.markdown("### 🔍 Detailed Competency Evidence & Analysis")
    for cs in assessment.competency_scores:
        with st.container():
            st.markdown(
                f"#### **{cs.competency_name}** &mdash; `{cs.score:.1f}/100` "
                f"<span style='font-size:0.9rem; color:#64748b;'>(Demonstrated Level {cs.demonstrated_level:.1f} vs Target {cs.target_level})</span>",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Demonstrated Strengths:**")
                if cs.strengths:
                    for s in cs.strengths:
                        st.markdown(f"- {s}")
                else:
                    st.caption("No specific strengths recorded.")

            with c2:
                st.markdown("**Identified Gaps:**")
                if cs.gaps:
                    for g in cs.gaps:
                        st.markdown(f"- {g}")
                else:
                    st.caption("No specific gaps recorded.")

            st.markdown(f"<span style='color:#64748b; font-size:0.85rem;'>Evidence Turns Evaluated: {cs.evidence_count}</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:12px 0;'/>", unsafe_allow_html=True)

    # Transcript Review
    with st.expander("📜 Full Interview Transcript History", expanded=False):
        for item in st.session_state.history:
            st.markdown(
                f"**Turn {item['turn']}** &mdash; *Competency:* `{item['competency']}` (Diff: `{item['difficulty']}`)  \n"
                f"**Question:** {item['question']}  \n"
                f"**Candidate Answer:** {item['answer']}  \n"
                f"**Adaptive Action:** `{item['action']}`  \n"
                f"**Why This Follow-Up:** {item['why_this_follow_up']}"
            )
            st.markdown("<hr style='margin:8px 0;'/>", unsafe_allow_html=True)

    if st.button("🔄 Start Another Interview"):
        st.session_state.clear()
        init_session_state()
        st.rerun()
