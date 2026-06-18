"""Tests for Freshdesk ticket creation — the payload WE send (no real ticket created).

Freshdesk rejects the whole ticket (400) if a required custom field is missing or an
unknown cf_* is sent, so these lock down the exact payload `create_escalation_ticket`
builds. The actual HTTP POST is mocked, so nothing is created in Freshdesk.

This is purely OUR responsibility — the frontend has no say in the Freshdesk payload.
"""

import pytest
from src.services.freshdesk_service import FreshdeskService


def test_priority_mapping():
    """Priority is derived from confidence + urgency (pure logic)."""
    svc = FreshdeskService()
    assert svc._determine_priority("listing is broken", 0.2) == 3   # urgent keyword OR low conf -> High
    assert svc._determine_priority("how do I add a photo", 0.5) == 2  # medium confidence -> Medium
    assert svc._determine_priority("how do I add a photo", 0.8) == 1  # confident -> Low


@pytest.mark.asyncio
async def test_escalation_ticket_payload(monkeypatch):
    """create_escalation_ticket builds the exact, Freshdesk-valid payload and passes it on."""
    svc = FreshdeskService()

    captured = {}
    async def fake_create_ticket(**kwargs):
        captured.update(kwargs)
        return {"success": True, "ticket_id": 123, "ticket_subject": kwargs.get("subject")}

    # Intercept the actual ticket creation (no HTTP / no real ticket).
    monkeypatch.setattr(svc, "create_ticket", fake_create_ticket)

    result = await svc.create_escalation_ticket(
        query="My listing won't sync to Property24",
        agent_response="Here are some steps…",
        confidence_score=0.2,
        user_email="jane@agency.co.za",
        user_name="Jane",
        user_agency="Acme",
        user_office="Sandton",
        conversation_history=[{"role": "user", "content": "hi"}],
        escalation_reason="low_confidence",
    )
    assert result["success"] and result["ticket_id"] == 123

    # Requester identity (Freshdesk needs the email) and a readable subject.
    assert captured["email"] == "jane@agency.co.za"
    assert "PropertyEngine AI Support" in captured["subject"]
    # Low confidence -> High priority.
    assert captured["priority"] == 3

    # The pedantic required custom fields Freshdesk demands — exact names + valid values.
    cf = captured["custom_fields"]
    assert cf["cf_agency_group"] == "Internal"
    assert cf["cf_agency_office"] in ("PropTech", "BetterBond")
    for required in ("cf_category", "cf_sub_category", "cf_case_ownership",
                     "cf_resolution_process", "cf_root_cause", "cf_solutionadd_steps"):
        assert required in cf, f"missing required Freshdesk field: {required}"
