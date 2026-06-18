"""Chatbot API package — the interaction-centric customer chat surface.

Two resources, all under /api/chatbot:
  - interactions: the workhorse — ask, read, feedback, escalation (everything that writes)
  - sessions:     read-only conversation history

These wrap the existing engine (orchestrator, escalation, Freshdesk) and persist each turn
to the durable `chatbot_interactions` / `chatbot_sessions` collections. Intended to
supersede the scattered customer_agent / feedback / agent_failure / session endpoints once
the frontend switches over (strangler-fig migration — both run in parallel until then).
"""

from fastapi import APIRouter

from .interactions import router as interactions_router
from .sessions import router as sessions_router

# Combined router for all chatbot endpoints.
router = APIRouter()
router.include_router(interactions_router)
router.include_router(sessions_router)

__all__ = ["router", "interactions_router", "sessions_router"]
