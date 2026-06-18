"""Tests for the /api/chatbot/* endpoints (routing + wiring, no external services).

Uses FastAPI's TestClient with the engine, persistence, Freshdesk, auth and rate-limiter
all replaced by in-memory fakes — so these run fast and never touch Firestore / Astra /
the LLM proxy, matching the rest of the suite's "pure, no external services" style. They
verify OUR code: request validation, the create→stream→persist lifecycle, feedback, the
escalation→ticket flow, and the history endpoints.
"""

import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# --- Fakes ---------------------------------------------------------------

class FakeAgent:
    """Stands in for the orchestrator: yields the canonical frame sequence."""
    async def process_query_stream(self, query, session_id, user_info=None, user_type_filter=None):
        yield {"type": "session", "session_id": session_id}
        yield {"type": "sources", "sources": [{"title": "Syncing listings to portals"}]}
        yield {"type": "token", "text": "To sync "}
        yield {"type": "token", "text": "your listing…"}
        yield {"type": "metadata", "confidence": 0.78, "requires_escalation": False,
               "escalation_reason": "none", "query_type": "howto"}
        yield {"type": "done"}


class FakeFreshdesk:
    async def create_escalation_ticket(self, **kwargs):
        return {"success": True, "ticket_id": 18500, "ticket_subject": "Test", "ticket_priority": 2}


class FakeService:
    """In-memory stand-in for FirebaseInteractionService."""
    def __init__(self):
        self.sessions = {}
        self.interactions = {}

    def create_or_get_session(self, created_by, user_info=None, session_id=None):
        sid = session_id or "sess-1"
        self.sessions.setdefault(sid, {"id": sid, "created_by": created_by, **(user_info or {})})
        return sid

    def create_interaction(self, session_id, created_by, question, user_info=None):
        iid = f"int-{len(self.interactions) + 1}"
        self.interactions[iid] = {"id": iid, "session_id": session_id, "created_by": created_by,
                                  "question": question, "answer": None, "status": "streaming",
                                  "feedback": None, "ticket": None,
                                  "escalation_decision": None, "escalation_decided_at": None}
        return iid

    def set_escalation_decision(self, interaction_id, decision):
        self.interactions[interaction_id]["escalation_decision"] = decision
        self.interactions[interaction_id]["escalation_decided_at"] = "2026-01-01T00:00:00"
        return {"success": True}

    def build_conversation_history(self, session_id):
        hist = []
        for i in self.interactions.values():
            if i["session_id"] != session_id:
                continue
            if i.get("question"):
                hist.append({"role": "user", "content": i["question"]})
            if i.get("answer"):
                hist.append({"role": "assistant", "content": i["answer"]})
        return hist

    def complete_interaction(self, interaction_id, answer, sources, metadata):
        meta = metadata or {}
        self.interactions[interaction_id].update({
            "answer": answer, "status": "complete",
            "metadata": {"sources_used": [s.get("title") for s in (sources or [])],
                         "confidence": meta.get("confidence")},
            "escalation_required": meta.get("requires_escalation", False),
            "escalation_reason": meta.get("escalation_reason", "none"),
        })
        return {"success": True}

    def fail_interaction(self, interaction_id, error=None):
        self.interactions[interaction_id]["status"] = "failed"
        return {"success": True}

    def get_interaction(self, interaction_id):
        return self.interactions.get(interaction_id)

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def add_feedback(self, interaction_id, feedback_type, comment=None):
        self.interactions[interaction_id]["feedback"] = {"type": feedback_type, "comment": comment}
        return {"success": True}

    def attach_ticket(self, interaction_id, ticket):
        self.interactions[interaction_id]["ticket"] = ticket
        return {"success": True}

    def list_sessions(self, created_by, limit=50):
        return [s for s in self.sessions.values() if s.get("created_by") == created_by]

    def get_session_with_interactions(self, session_id):
        s = self.sessions.get(session_id)
        if not s:
            return None
        s = dict(s)
        s["interactions"] = [i for i in self.interactions.values() if i["session_id"] == session_id]
        return s


# --- Fixture: app wired to fakes -----------------------------------------

@pytest.fixture
def chat(monkeypatch):
    """Return (client, fake_service) with all external deps replaced by fakes."""
    from src.api import chatbot
    from src.api.chatbot import interactions as ix
    from src.api.chatbot import sessions as sx
    from src.api.auth import verify_user_optional

    svc = FakeService()
    monkeypatch.setattr(ix, "agent", FakeAgent())
    monkeypatch.setattr(ix, "_service", svc)
    monkeypatch.setattr(sx, "_service", svc)
    monkeypatch.setattr(ix, "check_rate_limit", lambda **kw: None)
    monkeypatch.setattr(ix, "get_freshdesk_service", lambda: FakeFreshdesk())

    app = FastAPI()
    app.include_router(chatbot.router)
    # Pretend the caller is an authenticated user (token already verified).
    app.dependency_overrides[verify_user_optional] = lambda: {"uid": "user-1", "email": "test@x.co"}
    return TestClient(app), svc


def _frames(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


# --- Tests ---------------------------------------------------------------

def test_create_interaction_streams_and_persists(chat):
    client, svc = chat
    resp = client.post("/api/chatbot/interactions",
                       json={"message": "How do I sync a listing?", "user_info": {}})
    assert resp.status_code == 200

    frames = _frames(resp)
    types = [f["type"] for f in frames]
    assert types[0] == "session" and types[-1] == "done"
    assert "token" in types and "metadata" in types

    # Opening frame carries both ids so the frontend can act on this turn.
    opening = frames[0]
    assert opening["session_id"] and opening["interaction_id"]

    # The final answer + sources were persisted with status "complete".
    stored = svc.interactions[opening["interaction_id"]]
    assert stored["status"] == "complete"
    assert stored["answer"] == "To sync your listing…"
    assert stored["metadata"]["sources_used"] == ["Syncing listings to portals"]


def test_get_interaction_404_then_200(chat):
    client, svc = chat
    assert client.get("/api/chatbot/interactions/nope").status_code == 404

    sid = svc.create_or_get_session("user-1", {})
    iid = svc.create_interaction(sid, "user-1", "q?")
    resp = client.get(f"/api/chatbot/interactions/{iid}")
    assert resp.status_code == 200
    assert resp.json()["interaction"]["id"] == iid


def test_feedback_rejects_bad_type(chat):
    client, svc = chat
    iid = svc.create_interaction(svc.create_or_get_session("user-1", {}), "user-1", "q?")
    assert client.post(f"/api/chatbot/interactions/{iid}/feedback",
                       json={"feedback_type": "maybe"}).status_code == 400


def test_feedback_accepts_and_stores(chat):
    client, svc = chat
    iid = svc.create_interaction(svc.create_or_get_session("user-1", {}), "user-1", "q?")
    resp = client.post(f"/api/chatbot/interactions/{iid}/feedback",
                       json={"feedback_type": "positive", "comment": "great"})
    assert resp.status_code == 200
    assert svc.interactions[iid]["feedback"]["type"] == "positive"


def test_escalation_create_ticket(chat):
    client, svc = chat
    sid = svc.create_or_get_session("user-1", {"email": "j@x.co"})
    iid = svc.create_interaction(sid, "user-1", "help me")
    resp = client.post(f"/api/chatbot/interactions/{iid}/escalation",
                       json={"escalationDecision": "create-ticket"})
    assert resp.status_code == 200
    assert resp.json()["ticket_id"] == 18500
    assert svc.interactions[iid]["ticket"]["ticket_id"] == 18500
    assert svc.interactions[iid]["escalation_decision"] == "create-ticket"


def test_escalation_decline_records_no_ticket(chat):
    client, svc = chat
    iid = svc.create_interaction(svc.create_or_get_session("user-1", {}), "user-1", "help")
    resp = client.post(f"/api/chatbot/interactions/{iid}/escalation",
                       json={"escalationDecision": "decline"})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "decline"
    assert svc.interactions[iid]["escalation_decision"] == "decline"
    assert svc.interactions[iid]["ticket"] is None  # no ticket on decline


def test_escalation_rejects_bad_decision(chat):
    client, svc = chat
    iid = svc.create_interaction(svc.create_or_get_session("user-1", {}), "user-1", "q")
    assert client.post(f"/api/chatbot/interactions/{iid}/escalation",
                       json={"escalationDecision": "maybe"}).status_code == 400


def test_escalation_is_idempotent(chat):
    client, svc = chat
    iid = svc.create_interaction(svc.create_or_get_session("user-1", {}), "user-1", "help")
    svc.interactions[iid]["ticket"] = {"ticket_id": 999}
    resp = client.post(f"/api/chatbot/interactions/{iid}/escalation",
                       json={"escalationDecision": "create-ticket"})
    assert resp.status_code == 200
    assert resp.json()["ticket_id"] == 999  # existing ticket returned, not a new one


def test_list_and_get_sessions(chat):
    client, svc = chat
    sid = svc.create_or_get_session("user-1", {})
    svc.create_interaction(sid, "user-1", "q?")

    listed = client.get("/api/chatbot/sessions")
    assert listed.status_code == 200 and listed.json()["count"] >= 1

    one = client.get(f"/api/chatbot/sessions/{sid}")
    assert one.status_code == 200
    assert len(one.json()["session"]["interactions"]) == 1
