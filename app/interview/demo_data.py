from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Stable UUIDs for Demo Data
# ---------------------------------------------------------------------------
DEMO_ORG_ID = UUID("00000000-0000-0000-0001-000000000001")
DEMO_INTERVIEW_DEF_ID = UUID("00000000-0000-0000-0002-000000000001")
DEMO_JOB_ID = UUID("00000000-0000-0000-0003-000000000001")

COMP_DISTRIBUTED_SYSTEMS_ID = UUID("10000000-0000-0000-0000-000000000001")
COMP_SYSTEM_ARCHITECTURE_ID = UUID("10000000-0000-0000-0000-000000000002")
COMP_INCIDENT_RELIABILITY_ID = UUID("10000000-0000-0000-0000-000000000003")
COMP_PYTHON_PERFORMANCE_ID = UUID("10000000-0000-0000-0000-000000000004")
COMP_DATABASE_ARCHITECTURE_ID = UUID("10000000-0000-0000-0000-000000000005")


@dataclass
class DemoCompetency:
    id: UUID
    name: str
    description: str
    target_level: int = 3
    weight: float = 1.0
    display_order: int = 1


@dataclass
class DemoQuestion:
    id: UUID
    competency_id: UUID
    difficulty_level: int
    question_text: str
    expected_signal: str
    question_type: str = "TECHNICAL"
    display_order: int = 1
    is_active: bool = True
    interview_definition_id: UUID = DEMO_INTERVIEW_DEF_ID
    organization_id: UUID = DEMO_ORG_ID


# ---------------------------------------------------------------------------
# Pre-seeded Question Bank across Competencies and Difficulties (1 to 5)
# ---------------------------------------------------------------------------
DEMO_QUESTIONS: list[DemoQuestion] = [
    # --- Distributed Systems & Concurrency ---
    DemoQuestion(
        id=UUID("20000000-0000-0000-0001-000000000001"),
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=1,
        question_text="What is the difference between synchronous and asynchronous communication in distributed systems, and when would you use a message queue?",
        expected_signal="Understands decoupled message queues, buffering, and latency differences.",
        display_order=1,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0001-000000000002"),
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=2,
        question_text="How do you ensure idempotency in payment processing APIs when requests are retried over unreliable networks?",
        expected_signal="Mentions idempotency keys, unique request IDs, transactional state transitions, and distributed caching.",
        display_order=2,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0001-000000000003"),
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=3,
        question_text="Describe how you would design a distributed rate limiter supporting 100,000 requests per second across multiple regional data centers.",
        expected_signal="Discusses token bucket or sliding window algorithms, Redis clusters, clock skew, and local batching.",
        display_order=3,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0001-000000000004"),
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=4,
        question_text="Compare the Raft and Paxos consensus algorithms. How does leader election handle network partitions and split-brain scenarios?",
        expected_signal="Explains term numbers, majority quorums, log matching invariants, and leader lease timeouts.",
        display_order=4,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0001-000000000005"),
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=5,
        question_text="How would you implement a globally distributed multi-region database with strict linearizability and deterministic conflict resolution?",
        expected_signal="Discusses TrueTime or Hybrid Logical Clocks, Spanner 2PC + Paxos architecture, commit wait intervals, and cross-region latencies.",
        display_order=5,
    ),

    # --- System Architecture & Scalability ---
    DemoQuestion(
        id=UUID("20000000-0000-0000-0002-000000000001"),
        competency_id=COMP_SYSTEM_ARCHITECTURE_ID,
        difficulty_level=1,
        question_text="What are horizontal vs vertical scaling strategies, and what bottlenecks occur when scaling a relational database horizontally?",
        expected_signal="Explains CPU/RAM limits, connection pooling, read replicas, and sharding challenges.",
        display_order=1,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0002-000000000002"),
        competency_id=COMP_SYSTEM_ARCHITECTURE_ID,
        difficulty_level=2,
        question_text="How do you handle database caching invalidation using Write-Through vs Cache-Aside strategies in a high-traffic e-commerce system?",
        expected_signal="Contrasts latency vs stale data risks, TTLs, and cache stampede prevention.",
        display_order=2,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0002-000000000003"),
        competency_id=COMP_SYSTEM_ARCHITECTURE_ID,
        difficulty_level=3,
        question_text="Design a scalable URL shortening service (like Bitly) processing 10 billion links per month with sub-20ms lookup latency.",
        expected_signal="Covers Base62 encoding, distributed ID generation (Snowflake), database indexing, CDN, and in-memory caches.",
        display_order=3,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0002-000000000004"),
        competency_id=COMP_SYSTEM_ARCHITECTURE_ID,
        difficulty_level=4,
        question_text="How would you architect an event-driven system to process 500,000 real-time financial telemetry events per second with exactly-once processing guarantees?",
        expected_signal="Discusses Kafka partition keys, transactional producers, consumer offset management, dead letter queues, and deduplication storage.",
        display_order=4,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0002-000000000005"),
        competency_id=COMP_SYSTEM_ARCHITECTURE_ID,
        difficulty_level=5,
        question_text="Architect a real-time collaborative document editing system (like Google Docs) handling simultaneous edits from 10,000 concurrent users per document.",
        expected_signal="Compares Operational Transformation (OT) and CRDTs (Conflict-free Replicated Data Types), vector clocks, and WebSocket fan-out topologies.",
        display_order=5,
    ),

    # --- Incident Management & Reliability ---
    DemoQuestion(
        id=UUID("20000000-0000-0000-0003-000000000001"),
        competency_id=COMP_INCIDENT_RELIABILITY_ID,
        difficulty_level=1,
        question_text="What are SLIs, SLOs, and SLAs, and how do you calculate error budgets for a microservice?",
        expected_signal="Defines indicators, objectives, agreements, and how error budgets dictate deployment velocity.",
        display_order=1,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0003-000000000002"),
        competency_id=COMP_INCIDENT_RELIABILITY_ID,
        difficulty_level=2,
        question_text="Describe how you would investigate a production API outage where response latencies spike from 50ms to 5000ms after a deployment.",
        expected_signal="Systematic triage: checking metrics, APM traces, error logs, database connections, and triggering immediate rollback if needed.",
        display_order=2,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0003-000000000003"),
        competency_id=COMP_INCIDENT_RELIABILITY_ID,
        difficulty_level=3,
        question_text="How do you implement Circuit Breakers and Bulkhead isolation to prevent cascading failures across downstream microservices?",
        expected_signal="Discusses closed/open/half-open state machines, thread pool isolation, fallback responses, and adaptive thresholds.",
        display_order=3,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0003-000000000004"),
        competency_id=COMP_INCIDENT_RELIABILITY_ID,
        difficulty_level=4,
        question_text="Walk through running a blameless post-mortem for a major 2-hour data corruption incident. How do you identify root causes and ensure corrective accountability?",
        expected_signal="Focuses on the 5 Whys, timeline reconstruction, systemic contributing factors, automated verification gates, and blameless engineering culture.",
        display_order=4,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0003-000000000005"),
        competency_id=COMP_INCIDENT_RELIABILITY_ID,
        difficulty_level=5,
        question_text="How would you design an automated Chaos Engineering pipeline to continuously validate high-availability failover in production Kubernetes clusters?",
        expected_signal="Discusses Chaos Mesh / Litmus, steady-state hypothesis definition, automated blast radius containment, canary routing, and rollback heuristics.",
        display_order=5,
    ),

    # --- Python Internals & Performance ---
    DemoQuestion(
        id=UUID("20000000-0000-0000-0004-000000000001"),
        competency_id=COMP_PYTHON_PERFORMANCE_ID,
        difficulty_level=1,
        question_text="Explain the differences between lists, sets, and dictionaries in Python in terms of memory layout and lookup time complexity.",
        expected_signal="Explains array pointers, hash tables, open addressing, hash collisions, and O(1) vs O(N) operations.",
        display_order=1,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0004-000000000002"),
        competency_id=COMP_PYTHON_PERFORMANCE_ID,
        difficulty_level=2,
        question_text="How does the Python Global Interpreter Lock (GIL) affect multithreaded CPU-bound programs vs I/O-bound asyncio applications?",
        expected_signal="Explains bytecode execution locking, multiprocessing vs asyncio event loop, and non-blocking I/O.",
        display_order=2,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0004-000000000003"),
        competency_id=COMP_PYTHON_PERFORMANCE_ID,
        difficulty_level=3,
        question_text="How would you profile and eliminate memory leaks caused by circular references and object retention in a long-running FastAPI/asyncio service?",
        expected_signal="Mentions tracemalloc, objgraph, gc module generations, async task leaks, and weakref usage.",
        display_order=3,
    ),
    DemoQuestion(
        id=UUID("20000000-0000-0000-0004-000000000004"),
        competency_id=COMP_PYTHON_PERFORMANCE_ID,
        difficulty_level=4,
        question_text="Explain Python's memory management internals (PyMalloc, arenas, pools, and small object allocators) and how they impact garbage collection cycles.",
        expected_signal="Details 256KB arenas, 4KB pools, size classes up to 512 bytes, and reference counting with generational cyclic GC.",
        display_order=4,
    ),
]


# ---------------------------------------------------------------------------
# Predefined Interview Profiles
# ---------------------------------------------------------------------------
DEMO_INTERVIEW_PROFILES: dict[str, dict[str, Any]] = {
    "Senior Staff Backend Engineer (Distributed Systems)": {
        "job_title": "Senior Staff Backend Engineer",
        "seniority": "Senior / Staff (Level 4+)",
        "description": "Lead design and implementation of mission-critical distributed services, event pipelines, and high-concurrency APIs.",
        "competencies": [
            DemoCompetency(
                id=COMP_DISTRIBUTED_SYSTEMS_ID,
                name="Distributed Systems & Concurrency",
                description="Consensus, idempotency, partitioned messaging, and fault-tolerant communication.",
                target_level=4,
                weight=1.5,
                display_order=1,
            ),
            DemoCompetency(
                id=COMP_SYSTEM_ARCHITECTURE_ID,
                name="System Architecture & Scalability",
                description="High-throughput architectural patterns, caching invalidation, and data partitioning.",
                target_level=4,
                weight=1.2,
                display_order=2,
            ),
            DemoCompetency(
                id=COMP_INCIDENT_RELIABILITY_ID,
                name="Incident Management & Reliability",
                description="Root cause investigation, SLI/SLO management, circuit breakers, and blameless post-mortems.",
                target_level=3,
                weight=1.0,
                display_order=3,
            ),
        ],
    },
    "Principal Site Reliability Engineer (Observability & Resilience)": {
        "job_title": "Principal Site Reliability Engineer",
        "seniority": "Principal (Level 5)",
        "description": "Architect cloud-native infrastructure, resilience engineering, chaos testing, and production incident response.",
        "competencies": [
            DemoCompetency(
                id=COMP_INCIDENT_RELIABILITY_ID,
                name="Incident Management & Reliability",
                description="SLO error budgets, automated failover, chaos engineering, and blameless incident reviews.",
                target_level=5,
                weight=1.5,
                display_order=1,
            ),
            DemoCompetency(
                id=COMP_DISTRIBUTED_SYSTEMS_ID,
                name="Distributed Systems & Concurrency",
                description="Multi-region consensus, network partitions, split-brain protection, and RPC resilience.",
                target_level=4,
                weight=1.2,
                display_order=2,
            ),
            DemoCompetency(
                id=COMP_SYSTEM_ARCHITECTURE_ID,
                name="System Architecture & Scalability",
                description="Microservice isolation, bulkhead patterns, and high-throughput telemetry pipelines.",
                target_level=4,
                weight=1.0,
                display_order=3,
            ),
        ],
    },
    "Senior Python Systems Engineer (Core Platform)": {
        "job_title": "Senior Python Systems Engineer",
        "seniority": "Senior (Level 3-4)",
        "description": "Design high-performance Python services, asyncio concurrency backends, and low-latency database integrations.",
        "competencies": [
            DemoCompetency(
                id=COMP_PYTHON_PERFORMANCE_ID,
                name="Python Internals & Performance",
                description="Asyncio event loop, memory management, CPython internals, and performance profiling.",
                target_level=4,
                weight=1.5,
                display_order=1,
            ),
            DemoCompetency(
                id=COMP_DISTRIBUTED_SYSTEMS_ID,
                name="Distributed Systems & Concurrency",
                description="Distributed task queues, idempotency, and asynchronous messaging architectures.",
                target_level=3,
                weight=1.2,
                display_order=2,
            ),
            DemoCompetency(
                id=COMP_SYSTEM_ARCHITECTURE_ID,
                name="System Architecture & Scalability",
                description="API caching, rate limiting, and relational database query optimization.",
                target_level=3,
                weight=1.0,
                display_order=3,
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# In-Memory Question Selector for Self-Contained Execution
# ---------------------------------------------------------------------------
class InMemoryQuestionSelector:
    """Deterministic question selector for zero-dependency demo runs."""

    def __init__(self, questions: list[DemoQuestion] | None = None):
        self.questions = list(questions or DEMO_QUESTIONS)

    async def __call__(
        self,
        interview_definition_id: UUID | None = None,
        organization_id: UUID | None = None,
        competency_id: UUID | None = None,
        difficulty_level: int | None = None,
        used_question_ids: list[UUID] | None = None,
    ) -> Any | None:
        used_set = set(used_question_ids or [])

        # Filter out used questions
        available = [q for q in self.questions if q.id not in used_set and q.is_active]

        if not available:
            return None

        # 1. Exact match on competency and difficulty
        if competency_id is not None and difficulty_level is not None:
            exact = [q for q in available if q.competency_id == competency_id and q.difficulty_level == difficulty_level]
            if exact:
                return exact[0]

        # 2. Match on competency with closest difficulty
        if competency_id is not None:
            comp_matches = [q for q in available if q.competency_id == competency_id]
            if comp_matches:
                target_diff = difficulty_level or 3
                comp_matches.sort(key=lambda q: (abs(q.difficulty_level - target_diff), q.display_order))
                return comp_matches[0]

        # 3. Match on difficulty across any competency
        if difficulty_level is not None:
            diff_matches = [q for q in available if q.difficulty_level == difficulty_level]
            if diff_matches:
                return diff_matches[0]

        # 4. Fallback to first available question
        return available[0]
