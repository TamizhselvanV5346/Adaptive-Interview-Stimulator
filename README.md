# 🎙️ Adaptive Interview Simulator

> **Autonomous, stateful technical assessment engine powered by LangGraph that dynamically evaluates candidate answers, probes knowledge gaps, escalates difficulty in real time, and generates institutional-grade PDF assessment reports.**

[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6F00.svg)](https://langchain-ai.github.io/langgraph/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![ReportLab](https://img.shields.io/badge/PDF-ReportLab-00599C.svg)](https://www.reportlab.com/)
[![Tests](https://img.shields.io/badge/Tests-244%20Passing-success.svg?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🌐 Live Web Application

Experience the live adaptive technical interview simulator:

👉 **[https://adaptive-interview-simulator.onrender.com](https://adaptive-interview-simulator.onrender.com)** *(or run locally at `http://localhost:8501`)*

---

## ❓ What it does ?

**Adaptive Interview Simulator** transforms rigid, static screening interviews into an intelligent, evidence-driven conversational crucible that adapts to candidate performance in real time:

1. **Intake Job Specification & Target Seniority**: Ingests job descriptions (via n8n webhooks or built-in role profiles like *Senior Staff Backend Engineer*) and initializes an interview matrix across core engineering competencies (*Distributed Systems, System Architecture, Incident Management, Python Internals, Database Reliability*).
2. **Deterministic & Difficulty-Graded Question Delivery**: Delivers difficulty-calibrated questions (Levels 1 to 5) tailored to the active competency, preventing duplicate question delivery across turns.
3. **Multi-Dimensional Response Intelligence**: Evaluates candidate answers across technical accuracy (0–5), depth (0–5), relevance (0–5), confidence score (0–1.0), and classifies demonstrated proficiency level while diagnosing key strengths and knowledge gaps.
4. **Adaptive 5-Way LangGraph State Machine**: Dynamically chooses the next stateful interview action in real time:
   - **`PROBE`**: Detects knowledge gaps and asks targeted technical follow-ups on the same competency.
   - **`ESCALATE`**: Detects mastery at current level and ramps question difficulty (e.g., Level 2 ➔ Level 3/4) to test complex edge cases.
   - **`ADVANCE`**: Satisfies target competency thresholds and seamlessly transitions forward to the next competency.
   - **`REDIRECT`**: Detects off-topic tangents (e.g., answering cooking recipes during a production outage prompt) and politely recovers the dialogue with anti-loop safeguards.
   - **`COMPLETE`**: Finalizes the session once minimum turn thresholds (8+ turns) and all competencies are evaluated.
5. **Transparent "Why This Follow-Up" Rationale**: Discloses real-time, explainable rationale for why each follow-up question was selected based on demonstrated evidence.
6. **Model Context Protocol (MCP) Finalization**: Executes assessment boundaries and saves immutable evaluation logs.
7. **Audit-Ready PDF Assessment Report**: Generates an executive, styled PDF report (via ReportLab) with weighted competency radar scores (0–100), itemized strengths, identified gaps, and complete interview audit trails.

---

## 💥 Problem Statement

Traditional automated hiring assessments suffer from fatal flaws in technical screening:
- **Blind Progression**: Static tests force every candidate down the exact same rigid question list regardless of whether their answer was genius, flawed, or completely off-topic.
- **No Difficulty Calibration**: Elite senior candidates capable of high-scale architectural tradeoff analysis are constrained to elementary trivia questions.
- **Off-Topic Derailment**: Naive chatbots fail or penalize candidates arbitrarily when they misunderstand a question or deviate from the prompt.
- **Opaque Scoring**: Candidates and hiring managers receive arbitrary score outputs without explainable evidence or follow-up rationale.
- **Subjective "Hire/Reject" Bias**: Black-box AI tools output risky binary verdicts rather than objective, audit-ready competency signal matrices grounded strictly in demonstrated evidence.

---

## 💡 Solution

**Adaptive Interview Simulator** replaces rigid screening with a 24/7, high-fidelity adaptive interview engine:
- **Stateful Dynamic Crucible**: Powered by LangGraph cyclic state machines that react to candidate depth in real time.
- **Evidence-Based Evaluation**: Deterministically scores technical accuracy, depth, and relevance with calibrated difficulty scaling.
- **Graceful Conversational Recovery**: Automatically identifies off-topic deviations and guides candidates back to the core evaluation prompt with anti-loop safeguards.
- **Explainable "Why This Follow-Up"**: Full transparency showing candidates and interviewers exactly how their answers drove the follow-up strategy.
- **Executive PDF Assessment Reports**: Generates institutional-grade PDF reports with weighted competency breakdowns (0–100%) and itemized strengths/gaps without discriminatory bias.

---

## 🚀 How to Run it

### Prerequisites
- **Python 3.11+** or **Python 3.12+**
- **Git**
- Optional API Keys & Database:
  - **Claude API Key** (Anthropic), **Gemini API Key** (Google), or **Groq API Key**
  - **PostgreSQL Database** *(optional – built-in deterministic Mock Provider and demo database runs 100% offline out-of-the-box!)*

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/TamizhselvanV5346/Adaptive-Interview-Stimulator.git
cd Adaptive-Interview-Stimulator
```

---

### Step 2: Backend Setup & Execution

```bash
# Navigate to backend directory
cd AIS_Backend

# Create and activate Python virtual environment
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env
```

*Fill in your configuration in `AIS_Backend/.env` (see the Environment Variables section below).*

---

### Step 3: Run the Streamlit Web Application (Recommended Demo Mode)

Launch the interactive adaptive interview UI directly:

```bash
# From AIS_Backend directory:
streamlit run streamlit_app.py
```
*Web Application runs locally at: `http://localhost:8501`*

#### 🎮 Interactive Demo Walkthrough:
1. **Setup Screen**: Select a candidate profile (e.g., *Senior Staff Backend Engineer*) and click **Start Adaptive Interview**.
2. **Turn 1 (Difficulty 2)**: Select **Strong Technical Answer** and click **Submit Answer ➔**. Observe difficulty escalate to 3.
3. **Turn 2 (Difficulty 3)**: Select **Off-Topic Answer** (*"I cooked biryani yesterday"*). Observe graceful **Topic Focus Request** redirection.
4. **Turn 2 (Retry)**: Select **Weak Answer (Gaps)**. Observe the state machine trigger **`PROBE`** to explore knowledge gaps.
5. **Turns 3–8+**: Continue advancing through competencies (**`ADVANCE`**) until **`COMPLETE`**.
6. **Assessment & PDF**: Review the final weighted competency score breakdown and click **Download Assessment Report (PDF)**.

---

### Step 4: Run the FastAPI Backend (Optional API Mode)

```bash
# Start the FastAPI Backend Server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```
*Backend runs locally at: `http://localhost:8000` (Interactive Swagger docs at `http://localhost:8000/docs`)*

---

## 🔑 What the ENV variables

Create your `.env` file in `AIS_Backend/` (or use `.env.example` as a template):

```env
# ==========================================
# 1. Application Settings
# ==========================================
APP_NAME="Adaptive Interview Simulator"
ENVIRONMENT="development"
API_PREFIX="/api/v1"

# ==========================================
# 2. Adaptive Interview Limits
# ==========================================
MIN_INTERVIEW_TURNS=8
MAX_INTERVIEW_TURNS=12

# ==========================================
# 3. Database Connection (Optional for Demo Mode)
# ==========================================
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/adaptive_interview_stimulator"

# ==========================================
# 4. LLM Providers (Claude, Gemini, Groq - Optional for Mock Demo)
# ==========================================
CLAUDE_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

---

## 🧪 Testing & Verification

The project includes an automated test suite covering state transitions, scoring, recovery, and UI:

```bash
cd AIS_Backend
pytest -q
```

---

## 🛡️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
