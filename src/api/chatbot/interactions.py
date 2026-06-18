"""Chatbot interaction endpoints — the customer chat surface (interaction-centric model).

    POST   /api/chatbot/interactions                ask a question (NDJSON stream)
    GET    /api/chatbot/interactions/{id}           read one turn (or poll an unfinished stream)
    POST   /api/chatbot/interactions/{id}/feedback  👍/👎 on a turn
    POST   /api/chatbot/interactions/{id}/escalation raise a Freshdesk ticket for a turn

Each turn is persisted as one durable `chatbot_interactions` record (create-then-update):
created when the question arrives, updated with the answer/sources/confidence when the
stream finishes, and updated again when feedback or a ticket lands. The heavy lifting
(retrieval, escalation decision, Freshdesk) stays in the existing engine — these routes
just wrap it and persist the result.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse

from src.agent.orchestrator import Agent
from src.api.auth import verify_user_optional
from src.api.streaming_utils import ndjson_stream, STREAM_HEADERS
from src.database.firebase_interaction_service import FirebaseInteractionService
from src.services.freshdesk_service import get_freshdesk_service
from src.utils.rate_limiter import check_rate_limit
from .models import InteractionRequest, FeedbackRequest, EscalationRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot/interactions", tags=["chatbot"])

# Heavy singleton, same pattern as the existing agent routers.
agent = Agent()
_service = None


def get_service() -> FirebaseInteractionService:
    """Lazy-load the Firestore persistence layer."""
    global _service
    if _service is None:
        _service = FirebaseInteractionService()
    return _service


def _resolve_identity(user, user_info) -> str:
    """Trusted identity from the token if present, else fall back to user_info.

    During the open-testing window verify_user returns None (auth off), so we fall back
    to the body. Once the frontend sends Firebase tokens, `user` is the decoded token and
    its uid is authoritative (a client can't forge it).
    """
    if user:
        return user.get("uid") or user.get("email") or "authenticated"
    info = user_info or {}
    return info.get("agent_id") or info.get("email") or "anonymous"


async def _interaction_stream(svc, interaction_id, session_id, request):
    """Wrap the engine's stream: emit our opening frame (with the interaction id), pass
    every frame through to the client, accumulate the answer/sources/metadata, and persist
    the final state when the stream finishes (or mark it failed)."""
    yield {"type": "session", "session_id": session_id, "interaction_id": interaction_id}

    answer_parts, sources, final_meta, failed = [], [], {}, False
    try:
        async for frame in agent.process_query_stream(
            query=request.message, session_id=session_id,
            user_info=request.user_info, user_type_filter="external",
        ):
            ftype = frame.get("type")
            if ftype == "session":
                continue  # we already emitted our own opening frame (with interaction_id)
            if ftype == "token":
                answer_parts.append(frame.get("text", ""))
            elif ftype == "sources":
                sources = frame.get("sources", [])
            elif ftype == "metadata":
                final_meta = frame
            elif ftype == "error":
                failed = True
            yield frame
    except Exception as e:
        logger.error(f"❌ Chatbot stream failed (interaction={interaction_id}): {e}", exc_info=True)
        failed = True
        yield {"type": "error", "message": "I apologize, but I encountered an error. Please try again."}

    # Persist the durable record once the stream is done.
    if failed:
        svc.fail_interaction(interaction_id)
    else:
        svc.complete_interaction(interaction_id, "".join(answer_parts), sources, final_meta)


@router.post("")
async def create_interaction(
    request: InteractionRequest,
    http_request: Request,
    user=Depends(verify_user_optional),
):
    """Ask a question. Creates (or continues) a session, creates the interaction record,
    then streams the answer as NDJSON frames (session → sources → token* → metadata → done).
    Identity comes from the auth token when present, else from user_info (migration)."""
    check_rate_limit(
        request=http_request, endpoint_type="query",
        agent_id=request.user_info.get("agent_id"),
        user_email=request.user_info.get("email") or (user or {}).get("email"),
    )

    svc = get_service()
    created_by = _resolve_identity(user, request.user_info)
    session_id = svc.create_or_get_session(created_by, request.user_info, request.session_id)
    interaction_id = svc.create_interaction(session_id, created_by, request.message, request.user_info)

    return StreamingResponse(
        ndjson_stream(_interaction_stream(svc, interaction_id, session_id, request)),
        media_type="application/x-ndjson", headers=STREAM_HEADERS,
    )


@router.get("/{interaction_id}")
async def get_interaction(interaction_id: str, user=Depends(verify_user_optional)):
    """Read one interaction. The frontend polls this after a refresh to resume a stream
    that was cut off (status will be 'streaming', 'complete', or 'failed')."""
    interaction = get_service().get_interaction(interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return {"success": True, "interaction": interaction}


@router.post("/{interaction_id}/feedback")
async def submit_feedback(interaction_id: str, request: FeedbackRequest, user=Depends(verify_user_optional)):
    """Record 👍/👎 on a turn — an update to the same interaction record."""
    if request.feedback_type not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="feedback_type must be 'positive' or 'negative'")

    svc = get_service()
    if not svc.get_interaction(interaction_id):
        raise HTTPException(status_code=404, detail="Interaction not found")

    result = svc.add_feedback(interaction_id, request.feedback_type, request.comment)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to save feedback"))
    return {"success": True, "message": "Feedback saved"}


@router.post("/{interaction_id}/escalation")
async def create_escalation(
    interaction_id: str,
    request: EscalationRequest,
    http_request: Request,
    user=Depends(verify_user_optional),
):
    """Raise a Freshdesk ticket for this turn and link it back to the interaction.

    Reached by BOTH escalation flows — the user explicitly asking for a ticket and the
    agent offering one after it couldn't answer. Uses the question/answer/confidence
    already stored on the interaction, plus the business context on the session.
    """
    svc = get_service()
    interaction = svc.get_interaction(interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # Idempotent: don't double-create a ticket for the same turn.
    if interaction.get("ticket"):
        return {"success": True, "ticket_id": interaction["ticket"].get("ticket_id"),
                "message": "Ticket already exists"}

    session = svc.get_session(interaction.get("session_id")) or {}

    check_rate_limit(
        request=http_request, endpoint_type="ticket",
        agent_id=interaction.get("created_by"), user_email=session.get("user_email"),
    )

    meta = interaction.get("metadata", {}) or {}
    user_email = session.get("user_email") or "support@propertyengine.co.za"

    freshdesk = get_freshdesk_service()
    ticket_result = await freshdesk.create_escalation_ticket(
        query=interaction.get("question", ""),
        agent_response=interaction.get("answer", ""),
        confidence_score=meta.get("confidence") or 0,
        user_email=user_email,
        user_name=session.get("user_name"),
        user_phone=request.user_phone,
        user_agency=session.get("agency"),
        user_office=session.get("office"),
        conversation_history=request.conversation_history,
        escalation_reason=interaction.get("escalation_reason", "user_requested"),
    )
    if not ticket_result["success"]:
        raise HTTPException(status_code=500, detail=f"Freshdesk error: {ticket_result.get('error')}")

    ticket = {
        "ticket_id": ticket_result["ticket_id"],
        "subject": ticket_result.get("ticket_subject"),
        "priority": ticket_result.get("ticket_priority"),
        "status": "open",
        "created_at": datetime.now().isoformat(),
    }
    svc.attach_ticket(interaction_id, ticket)
    logger.info(f"✅ Ticket #{ticket_result['ticket_id']} created for interaction {interaction_id}")
    return {"success": True, "ticket_id": ticket_result["ticket_id"],
            "message": f"Ticket #{ticket_result['ticket_id']} created"}
