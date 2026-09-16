import pytest
from streamlit.testing.v1 import AppTest


def test_streamlit_full_app_ui_flow():
    """Programmatically verify complete multi-state Streamlit UI workflow."""
    at = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert not at.exception

    # 1. SETUP Screen
    assert at.session_state.screen == "SETUP"
    start_btn = at.button[0]  # Start Adaptive Interview button
    assert "Start Adaptive Interview" in start_btn.label
    start_btn.click().run()
    assert not at.exception

    # 2. INTERVIEW Screen: Turn 1
    assert at.session_state.screen == "INTERVIEW"
    assert at.session_state.current_turn == 1

    # Turn 1: Strong Answer -> ESCALATE
    at.text_area[0].input(
        "We implemented Raft consensus with leader election, quorum heartbeats, "
        "and idempotent Kafka consumers backed by distributed Redis caches and circuit breakers."
    )
    # Find submit button (Submit Answer)
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()
    assert not at.exception

    assert at.session_state.last_action == "ESCALATE"
    assert at.session_state.current_turn == 2

    # Turn 2: Off-Topic Answer -> REDIRECT
    at.text_area[0].input("I cooked biryani yesterday.")
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()
    assert not at.exception

    assert at.session_state.last_action == "REDIRECT"
    assert at.session_state.redirect_message is not None
    assert at.session_state.current_turn == 2  # Remains on same turn

    # Turn 2 (retry): Weak Answer -> PROBE
    at.text_area[0].input("I am not sure how to handle cluster partitions and I have no experience with Raft.")
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()
    assert not at.exception

    assert at.session_state.last_action == "PROBE"
    assert at.session_state.current_turn == 3

    # Turns 3 to 8+: Continue submitting answers until completion
    strong_response = (
        "We designed a multi-region distributed system with Kafka partitioning, "
        "PostgreSQL read replicas, Redis caching, and Prometheus observability metrics."
    )

    for _ in range(10):
        if at.session_state.screen == "ASSESSMENT":
            break
        at.text_area[0].input(strong_response)
        submit_btn = [b for b in at.button if "Submit" in b.label][0]
        submit_btn.click().run()
        assert not at.exception

    # 3. ASSESSMENT Screen
    assert at.session_state.screen == "ASSESSMENT"
    assert at.session_state.final_assessment is not None
    assert at.session_state.final_assessment.completed is True
    assert at.session_state.final_assessment.overall_score > 0.0
    assert len(at.session_state.final_assessment.competency_scores) >= 3

    # PDF Download Button
    assert at.session_state.pdf_bytes is not None
    assert len(at.session_state.pdf_bytes) > 1000
    assert len(at.download_button) >= 1
    assert "Download Assessment Report (PDF)" in at.download_button[0].label
