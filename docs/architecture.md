# 🏛️ System Architecture

The **Adaptive Interview Simulator (AIS)** is an intelligent, evidence-driven technical assessment platform. Unlike rigid static questionnaire tools, AIS implements a closed-loop adaptive state machine powered by **LangGraph**, **FastAPI**, **SQLAlchemy 2.0 (Async)**, and **Streamlit**.

---

## High-Level Architectural Diagram

```text
+---------------------------------------------------------------------------------------+
|                                    USER INTERFACES                                    |
+---------------------------------------------------------------------------------------+
|   Streamlit Interactive App (Port 8501)    |    REST API Clients / n8n Webhooks       |
+---------------------------------------------------------------------------------------+
                                    |
                                    v
+---------------------------------------------------------------------------------------+
|                               FASTAPI APPLICATION LAYER                               |
+---------------------------------------------------------------------------------------+
|  /api/v1/intake/jobs       | Job & Interview Definition Intake (n8n Webhook)         |
|  /api/v1/sessions          | Session Initialization, Next Turn, Answer Submission     |
|  /api/v1/reporting         | Assessment Summary & ReportLab PDF Export                |
+---------------------------------------------------------------------------------------+
                                    |
                                    v
+---------------------------------------------------------------------------------------+
|                           ADAPTIVE INTERVIEW CORE ENGINE                              |
+---------------------------------------------------------------------------------------+
|  1. LangGraph State Machine (InterviewOrchestrator)                                   |
|     - State Graph: evaluate_response -> make_decision -> generate_reasoning -> route  |
|                                                                                       |
|  2. Response Intelligence Service                                                     |
|     - Multi-dimensional scoring: Accuracy (0-5), Depth (0-5), Relevance (0-5)         |
|     - Proficiency classification (Level 1-5), Strengths, Gaps, Off-Topic Root Cause    |
|                                                                                       |
|  3. Adaptive Decision Engine                                                          |
|     - Mathematically grounded transitions: PROBE, ESCALATE, ADVANCE, REDIRECT, COMPLETE|
|                                                                                       |
|  4. Follow-Up Reasoning Engine ("Why This Follow-Up")                                  |
|     - Generates explainable, evidence-backed rationale for candidate transparency     |
|                                                                                       |
|  5. Conversational Recovery & Anti-Loop Safeguards                                    |
|     - Redirects off-topic answers politely while enforcing retry quotas               |
|                                                                                       |
|  6. Deterministic Question Selector                                                   |
|     - Difficulty-graded (1-5), duplicate-free competency question selection          |
+---------------------------------------------------------------------------------------+
                |                                                   |
                v                                                   v
+-----------------------------------------------+   +-----------------------------------+
|               AI PROVIDERS LAYER              |   |       PERSISTENCE & REPORTING     |
+-----------------------------------------------+   +-----------------------------------+
| - MockProvider (Deterministic, 100% Offline)  |   | - PostgreSQL (Async SQLAlchemy 2) |
| - ClaudeProvider (Anthropic Claude 3.5)       |   | - Alembic Database Migrations     |
| - GeminiProvider / GroqProvider               |   | - ReportLab PDF Generation Engine |
+-----------------------------------------------+   +-----------------------------------+
```

---

## Component Layer Breakdown

### 1. Presentation & Interaction Layer
- **Streamlit Web Application (`streamlit_app.py`)**:
  - **Setup Screen**: Profile selection (e.g. *Senior Staff Backend Engineer*), candidate details, competency previews.
  - **Live Interview Crucible**: Dynamic turn tracker (`Turn X of 8`), single active question display, 1-click test answer presets, transparent *"Why This Follow-Up"* expanders, and collapsible chronological transcripts.
  - **Assessment Screen**: Final weighted score radar, competency breakdowns, diagnosed strengths & gaps, and downloadable PDF report.
- **FastAPI API Layer (`app/api/`)**:
  - REST endpoints adhering to OpenAPI specifications for seamless integration with external ATS platforms or automation workflows (n8n).

### 2. Orchestration Layer (`app/interview/orchestrator.py`)
- Built on **LangGraph**, modeling the interview as a cyclic state machine.
- Each turn represents a pass through evaluation, decision-making, reasoning synthesis, and conditional action routing.
- State is encapsulated in `InterviewGraphState` containing candidate answers, evaluation metrics, turn counters, retry quotas, and competency milestones.

### 3. Intelligence & Decision Layer
- **Response Intelligence (`app/ai/response_intelligence.py`)**:
  - Evaluates candidate submissions against expected competency signals.
  - Calculates accuracy, depth, relevance, confidence, and detects off-topic deviations.
- **Adaptive Decision Engine (`app/interview/adaptive_decision.py`)**:
  - Deterministically maps demonstrated proficiency to five discrete state actions:
    1. `PROBE`: Demonstrated Level < Target Level (drills into identified gap).
    2. `ESCALATE`: Demonstrated Level >= Target Level (escalates difficulty to test boundary conditions).
    3. `ADVANCE`: Current competency target met (transitions to next competency).
    4. `REDIRECT`: Off-topic response detected (triggers supportive recovery prompt).
    5. `COMPLETE`: Minimum turn threshold (>=8 turns) met and all competencies assessed.
- **Explainable Reasoning (`app/interview/follow_up_reasoning.py`)**:
  - Automatically synthesizes plain-language explanations citing specific evidence for every selected follow-up question.

### 4. Persistence & Reporting Layer
- **Relational Models (`app/database/models/`)**:
  - `Job`: Position title, department, seniority level, raw requirements.
  - `InterviewDefinition`: Competency matrix, target proficiency levels (1-5), and evaluation weights.
  - `InterviewSession`: State tracker, current turn, active competency, status.
  - `InterviewTurn`: Immutable log of question, candidate answer, scores, rationale, and decision.
  - `AssessmentReport`: Aggregated competency scores, strengths, gaps, and audit trails.
- **ReportLab PDF Generator (`app/reporting/pdf_report.py`)**:
  - Generates executive, multi-page vector PDF assessment summaries with custom tables, score badges, and structured audit logs.

---

## Technology Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.12 | Modern type hints, high performance, rich AI ecosystem |
| **Orchestration** | LangGraph / LangChain | Stateful, cyclic graph modeling with deterministic branching |
| **Backend API** | FastAPI + Uvicorn | High-throughput asynchronous REST API with automatic OpenAPI docs |
| **Frontend UI** | Streamlit | Rapid, responsive, interactive UI with seamless state management |
| **Database ORM** | SQLAlchemy 2.0 (Async) | Strict type annotations, async connection pooling with asyncpg |
| **Migrations** | Alembic | Version-controlled relational database schema evolutions |
| **Document Generation** | ReportLab | Enterprise-grade, pixel-precise vector PDF report synthesis |
| **Testing** | pytest + pytest-asyncio | Complete automated test coverage across domain contracts and UI |
