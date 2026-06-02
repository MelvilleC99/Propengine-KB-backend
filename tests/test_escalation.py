"""Tests for the EscalationHandler decision rules (pure logic, no external services)."""

from src.agent.escalation.escalation_handler import EscalationHandler
from src.config.settings import settings

handler = EscalationHandler()
RESULTS = [{"title": "How to create a listing", "similarity_score": 0.8}]


def test_user_requested_escalation():
    v = handler.check_escalation(query_type="escalation", results=RESULTS, confidence=0.9)
    assert v["should_escalate"] is True
    assert v["escalation_reason"] == "user_requested"
    assert v["escalation_type"] == "immediate"


def test_no_results_escalates():
    v = handler.check_escalation(query_type="howto", results=[], confidence=0.0)
    assert v["should_escalate"] is True
    assert v["escalation_reason"] == "no_results"


def test_low_confidence_is_conditional():
    # below the 0.5 threshold -> escalate, but let the user decide (ask_if_helps)
    v = handler.check_escalation(query_type="howto", results=RESULTS, confidence=0.40)
    assert v["should_escalate"] is True
    assert v["escalation_reason"] == "low_confidence"
    assert v["escalation_type"] == "conditional"
    assert v["response_strategy"] == "ask_if_helps"


def test_confident_answer_does_not_escalate():
    v = handler.check_escalation(query_type="howto", results=RESULTS, confidence=0.85)
    assert v["should_escalate"] is False
    assert v["escalation_reason"] == "none"


def test_threshold_is_min_confidence_score():
    # exactly at the threshold should NOT escalate (uses < comparison)
    v = handler.check_escalation(query_type="howto", results=RESULTS, confidence=settings.MIN_CONFIDENCE_SCORE)
    assert v["should_escalate"] is False
