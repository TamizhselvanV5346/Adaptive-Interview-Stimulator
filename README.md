# Adaptive Interview Simulator

> **An intelligent, evidence-based technical assessment engine that dynamically reacts to candidate responses in real time.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6F00.svg)](https://langchain-ai.github.io/langgraph/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy%202.0-D71F00.svg?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![ReportLab](https://img.shields.io/badge/PDF-ReportLab-00599C.svg)](https://www.reportlab.com/)
[![Tests](https://img.shields.io/badge/Tests-244%20Passing-success.svg?logo=pytest&logoColor=white)](https://docs.pytest.org/)

---

## Overview

Traditional technical screening systems operate on **static, predetermined question lists**. Every candidate is asked the exact same sequence of questions regardless of whether their answers are deeply insightful, fundamentally flawed, or completely off-topic.

**Adaptive Interview Simulator** transforms hiring assessments into a **stateful, evidence-driven conversation**. Powered by **LangGraph**, **FastAPI**, and **Streamlit**, the system evaluates each answer, deterministically selects the optimal next action (probing gaps, escalating difficulty, advancing competencies, or recovering from off-topic deviations), provides transparent **"Why This Follow-Up"** rationales, and generates a structured, audit-ready PDF assessment report.

---

## Problem Statement

Static automated interviews suffer from fundamental evaluation failures:
- **Blind Progression:** If a candidate gives a shallow answer to a basic question, static systems blindly advance to unrelated topics without probing technical depth.
- **No Difficulty Calibration:** Senior candidates capable of expert-level architectural tradeoff analysis are constrained to elementary trivia questions.
- **Off-Topic Derailment:** When a candidate misunderstands a question or goes off on a tangent, naive systems fail or penalize arbitrarily instead of politely redirecting.
- **Opaque Follow-Up Decisions:** Candidates and hiring managers receive arbitrary score outputs without clear, evidence-based explanations of *why* specific follow-up questions were asked.
- **Biased Decisions:** Many automated tools produce high-risk "Hire/Reject" verdicts rather than objective competency signal reports grounded strictly in demonstrated evidence.

---

## Solution: The Adaptive Interview Loop

The simulator operates on a closed-loop adaptive state machine:

```text
========================================================================================
                          STATIC vs ADAPTIVE INTERVIEW
========================================================================================

  STATIC INTERVIEW (Rigid, Pre-Scripted):
  Q1 (Diff 2) --> Answer --> Q2 (Diff 2) --> Answer --> Q3 (Diff 2) --> Final Score

  ADAPTIVE INTERVIEW SIMULATOR (Dynamic & Evidence-Driven):

         [ Question (Diff 2) ]
                  |
                  v
         [ Candidate Answer ]
                  |
                  v
    +---------------------------+
    | Response Intelligence     |  --> Evaluates relevance, depth, accuracy & off-topic
    +---------------------------+
                  |
                  v
    +---------------------------+
    | Adaptive Decision Engine  |  --> Evaluates target vs demonstrated level & turns
    +---------------------------+
                  |
                  v
    +---------------------------+
    | Follow-Up Reasoning       |  --> Generates transparent "Why This Follow-Up" rationale
    +---------------------------+
                  |
                  v
    +---------------------------+
    | LangGraph Workflow Router |
    +---------------------------+
                  |
      +-----------+-----------+-----------+-----------+
      |           |           |           |           |
      v           v           v           v           v
   [ PROBE ]  [ ESCALATE ] [ ADVANCE ] [ REDIRECT ] [ COMPLETE ]
   (Same comp, (Diff +1,   (Next comp,  (Graceful   (Min 8+ turns met,
    probe gap)  higher bar) target lvl)  recovery)   generate PDF)
```

---

## Core Features & Architectural Modules

### 1. n8n Job Intake & Definition Engine
- Intake requests submitted via web forms (e.g. n8n webhook triggers) send job descriptions and target seniority levels to `POST /api/v1/intake/jobs`.
- Idempotently creates the **Job** record and initializes the corresponding **Interview Definition** with target competencies.

### 2. Multi-Dimensional Competency Framework
- Configurable competency matrices with defined `target_level` (1 to 5), `weight`, and `display_order`.
- Accommodates multiple engineering disciplines (Distributed Systems, System Architecture, Incident Management, Python Internals, Database Reliability).

### 3. Difficulty-Graded Deterministic Question Bank
- Questions classified by `competency_id`, `difficulty_level` (1-5), `question_type` (Technical, Scenario, Behavioral), and `expected_signal`.
- Deterministic selection engine prioritizes target competency and difficulty level while preventing duplicate question delivery.

### 4. Candidate Response Intelligence
- Deeply evaluates candidate answers across:
  - **Relevance Score (0.0-5.0)** & **Depth Score (0.0-5.0)**
  - **Technical Accuracy Score (0.0-5.0)** & **Confidence (0.0-1.0)**
  - **Demonstrated Proficiency Level (1-5)**
  - **Key Strengths** & **Identified Knowledge Gaps**
  - **Off-Topic Detection** and categorized root cause

### 5. Adaptive Decision Engine
Determines the next interview action based on mathematically grounded rules:
- **`PROBE`**: Demonstrated level < Target level -> Probes the identified technical gap on the same competency.
- **`ESCALATE`**: Demonstrated level >= Target level -> Increases question difficulty (e.g. Level 2 -> Level 3) to test edge-case complexity.
- **`ADVANCE`**: Target competency satisfied at current difficulty -> Transitions forward to the next configured competency.
- **`REDIRECT`**: Off-topic response detected -> Triggers conversational recovery.
- **`COMPLETE`**: Minimum turn threshold (>=8 turns) met and all competencies evaluated.

### 6. Transparent "Why This Follow-Up" Rationale
- Explains to candidates and interviewers precisely why a specific follow-up question was chosen.
- Explicitly cites demonstrated evidence and identified gaps (e.g., *"Your answer demonstrated level 3 for Distributed Systems, so the interview is escalating difficulty to 4 to test higher complexity"*).

### 7. Conversational Recovery & Anti-Loop Safeguards
- Handles off-topic deviations (e.g., candidate answering *"I cooked biryani yesterday"* to a production outage prompt) with polite, supportive redirect messages.
- Preserves original question context and enforces retry limits to prevent infinite loops.

### 8. LangGraph State Machine Orchestration
- Encapsulates the entire adaptive lifecycle in a compiled, cyclic state graph (`evaluate_response` -> `make_adaptive_decision` -> `generate_follow_up_reasoning` -> conditional action branch -> next turn state).

### 9. Model Context Protocol (MCP) Assessment Finalization
- Enforces strict operational boundaries to validate state transitions and record assessment completion.

### 10. Objective Competency Scoring & PDF Report
- Aggregates multi-turn evidence into weighted competency scores (0.0-100.0) without subjective or discriminatory "Hire/Reject" labels.
- Generates an executive, downloadable PDF assessment report with session metrics, competency tables, and itemized strengths/gaps using **ReportLab**.

### 11. Interactive Streamlit Web Application
- Provides an intuitive multi-state interface:
  - **Setup Screen:** Profile selection, competency previews, turn configuration.
  - **Live Interview Screen:** Single question display, live turn progress (`Turn X of 8`), 1-click test answer presets, Why This Follow-Up panel, and collapsible transcript history.
  - **Assessment Screen:** Score overview, competency breakdown table, and direct PDF download.

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Language & Runtime** | Python 3.12 |
| **Backend Framework** | FastAPI, Uvicorn, Starlette |
| **Frontend UI** | Streamlit |
| **Agentic Orchestration** | LangGraph, LangChain Core |
| **Database & Persistence** | PostgreSQL, asyncpg, psycopg2-binary, SQLAlchemy 2.0 (Async) |
| **Database Migrations** | Alembic |
| **Document Generation** | ReportLab, PyPDF, Pillow |
| **Data Validation** | Pydantic v2, Pydantic-Settings |
| **Testing & Verification** | pytest, pytest-asyncio, Streamlit AppTest |
| **Workflow Automation** | n8n Webhook / Form Integration |

---

## Project Structure

```text
AIS_Backend/
├── app/
│   ├── ai/
│   │   ├── providers/
│   │   │   ├── base.py                    # Provider abstraction interface
│   │   │   ├── mock.py                    # Deterministic Mock Provider (Demo Mode)
│   │   │   └── claude.py                  # Anthropic Claude Provider integration
│   │   └── response_intelligence.py       # Response Intelligence Service
│   ├── api/
│   │   ├── routes/                        # FastAPI REST API endpoints
│   │   └── schemas/                       # Pydantic request/response schemas
│   ├── core/                              # App configuration, security, exceptions
│   ├── database/
│   │   ├── models/                        # SQLAlchemy relational models
│   │   └── session.py                     # Async database session management
│   ├── domain/                            # Domain contracts & data models
│   ├── evaluation/
│   │   └── competency_scoring.py          # Deterministic evidence scoring engine
│   ├── interview/
│   │   ├── adaptive_decision.py           # Adaptive Decision Engine
│   │   ├── conversation_recovery.py       # Conversational recovery & redirect service
│   │   ├── demo_data.py                   # Pre-seeded profiles, question banks & selector
│   │   ├── follow_up_reasoning.py         # Why This Follow-Up generator
│   │   ├── graph_state.py                 # LangGraph state schema
│   │   ├── orchestrator.py                # LangGraph stateful interview orchestrator
│   │   └── question_selector.py           # Deterministic database question selector
│   ├── mcp/
│   │   └── assessment_operations.py       # MCP assessment finalization boundary
│   ├── reporting/
│   │   ├── assessment_report.py           # Assessment report service
│   │   └── pdf_report.py                  # ReportLab PDF report generator
│   └── services/                          # Business logic service layer
├── tests/                                 # Complete test suite (244 tests passing)
│   ├── test_adaptive_decision.py
│   ├── test_assessment_report.py
│   ├── test_conversation_recovery.py
│   ├── test_follow_up_reasoning.py
│   ├── test_langgraph_orchestration.py
│   ├── test_response_intelligence.py
│   ├── test_streamlit_integration.py
│   └── test_streamlit_app_ui.py
├── alembic/                               # Database migration scripts
├── requirements.txt                       # Python dependencies
├── server.py                              # FastAPI backend entry point
└── streamlit_app.py                       # Main Streamlit web application
```

---

## Getting Started & How to Run

### Prerequisites
- **Python 3.12+**
- **Git**
- *(Optional)* **PostgreSQL** (Not required when running in self-contained Demo Mode)

---

### Step 1: Clone the Repository
```powershell
git clone https://github.com/selvanathan30/Adaptive-Interview-Stimulator.git
cd Adaptive-Interview-Stimulator
```

---

### Step 2: Environment Setup
```powershell
cd AIS_Backend

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 3: Run the Streamlit Application (Recommended Demo Mode)

Launch the interactive UI directly:

```powershell
# From AIS_Backend directory:
.\venv\Scripts\streamlit run streamlit_app.py

# Or from workspace root:
.\AIS_Backend\venv\Scripts\streamlit run streamlit_app.py
```

The web application will open at: **`http://localhost:8501`**

#### Demo Walkthrough Guide:
1. **Interview Setup:** Select a job profile (e.g. *Senior Staff Backend Engineer*), configure candidate details, and click **Start Adaptive Interview**.
2. **Turn 1 (Difficulty 2):** Click **Strong Technical Answer** and click **Submit Answer ->**. Notice the decision escalates difficulty to 3.
3. **Turn 2 (Difficulty 3):** Click **Off-Topic Answer** (*"I cooked biryani yesterday"*). Notice the polite **Topic Focus Request** redirect.
4. **Turn 2 (Retry):** Click **Weak Answer (Gaps)**. Notice the decision triggers **`PROBE`** to explore the knowledge gap.
5. **Turns 3-8+:** Continue submitting answers to observe competency advancement (**`ADVANCE`**) until **`COMPLETE`**.
6. **Assessment & PDF:** Review the final weighted overall score, competency breakdown, strengths, gaps, and click **Download Assessment Report (PDF)**.

---

### Step 4: Run the FastAPI Backend (Optional)
```powershell
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```
- API Documentation (Swagger): `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

---

## Environment Variables Configuration

Create a `.env` file in `AIS_Backend/` for database and provider settings:

```env
# Application Settings
APP_NAME="Adaptive Interview Simulator"
ENVIRONMENT="development"
API_PREFIX="/api/v1"

# Interview Limits
MIN_INTERVIEW_TURNS=8
MAX_INTERVIEW_TURNS=12

# PostgreSQL Database (Optional for Demo Mode)
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/adaptive_interview"

# AI Evaluation Providers
CLAUDE_API_KEY=""
GEMINI_API_KEY=""
GROQ_API_KEY=""
```

---

## Testing & Verification

The repository maintains an automated test suite with **244 passing tests**:

```powershell
cd AIS_Backend
.\venv\Scripts\pytest -q
```

### Verification Highlights:
- **Unit & Domain Contracts:** Validated boundary constraints for scoring, reasoning, recovery, and decisions.
- **LangGraph Routing:** Verified state machine conditional transitions for `PROBE`, `ESCALATE`, `ADVANCE`, `REDIRECT`, and `COMPLETE`.
- **End-to-End Simulation:** Verified complete 8+ turn adaptive flows with ReportLab PDF validation.
- **Streamlit AppTest:** Programmatically tested multi-state UI transitions without browser dependencies.

---

## Known Boundaries & Technical Limitations

In accordance with strict verification standards, the following boundaries are documented:
- **Claude API Credit Limitation:** The `ClaudeProvider` integration code is complete and typed; however, live Claude API evaluations could not be verified due to lack of Anthropic API credits. The application defaults to the offline, deterministic `MockProvider` in **Demo Mode**.
- **MCP Network Boundary:** The Model Context Protocol assessment finalization logic is implemented and verified locally; external networked MCP server hosting has not been deployed.
- **Objective Signal, Not Automated Hiring:** The system produces strictly evidence-based competency evaluations and does not generate automated "Hire/Reject" verdicts.

---

## Future Roadmap

- [ ] **Multi-Modal Audio/Video Input:** Integrate real-time speech-to-text with conversational turn management.
- [ ] **Interactive Coding Canvas:** Embedded code execution sandbox for real-time algorithmic problem solving.
- [ ] **Custom Rubric Builder:** Web-based rubric authoring tool for talent acquisition teams.
- [ ] **ATS Integration:** Automated export of assessment summaries to Greenhouse, Lever, and Ashby via webhooks.
