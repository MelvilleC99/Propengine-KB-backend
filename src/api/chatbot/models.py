"""Pydantic request models for the /api/chatbot/* endpoints.

These define the request contract only; responses for the chat endpoint are an NDJSON
stream (see interactions.py), and the read/feedback/escalation endpoints return plain
dicts. The interaction/session shapes themselves live in Firestore (see
firebase_interaction_service.py) — they aren't fixed response models because the frontend
reads them as-is.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict


class InteractionRequest(BaseModel):
    """POST /api/chatbot/interactions — ask a question (the answer streams back)."""
    message: str = Field(..., description="The user's question")
    session_id: Optional[str] = Field(
        None, description="Existing conversation to continue; omit to start a new one")
    # PropertyEngine account/office context (sent by the frontend; snapshotted onto the session).
    account_id: Optional[int] = Field(None, description="PE account id")
    account_label: Optional[str] = Field(None, description="PE account name")
    office_id: Optional[int] = Field(None, description="PE office id")
    office_label: Optional[str] = Field(None, description="PE office name")
    user_info: Optional[Dict] = Field(
        default_factory=dict,
        description=("Additional context (e.g. email). Identity is taken from the auth token "
                     "when present; user_info is the migration fallback."))


class FeedbackRequest(BaseModel):
    """POST /api/chatbot/interactions/{id}/feedback — 👍/👎 on a turn."""
    feedback_type: str = Field(..., description="'positive' or 'negative'")
    comment: Optional[str] = Field(None, description="Optional free-text comment")


class EscalationRequest(BaseModel):
    """POST /api/chatbot/interactions/{id}/escalation — record the escalation decision.

    The UI sends ONLY the decision. On 'create-ticket' the backend builds the conversation
    history itself (from Firestore) and raises a Freshdesk ticket; on 'decline' it just
    records the decision. We never accept UI-supplied conversation history (can't trust it).

    Accepts the JSON key `escalationDecision` (per the frontend contract); also tolerates
    the snake_case `escalation_decision` until the casing convention is finalised.
    """
    escalation_decision: str = Field(
        ..., alias="escalationDecision", description="'create-ticket' or 'decline'")

    model_config = {"populate_by_name": True}
