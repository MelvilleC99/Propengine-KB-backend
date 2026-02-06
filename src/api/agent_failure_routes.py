"""Agent Failure Routes - Track failures and create tickets"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import logging
from datetime import datetime
from src.database.firebase_agent_failure_service import FirebaseAgentFailureService
from src.services.freshdesk_service import get_freshdesk_service
from src.utils.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-failure", tags=["agent-failure"])

# Lazy load services
_failure_service = None


def get_failure_service():
    global _failure_service
    if _failure_service is None:
        _failure_service = FirebaseAgentFailureService()
    return _failure_service


# === Request Models ===

class CreateFailureRequest(BaseModel):
    """Create agent failure record"""
    session_id: str
    agent_id: str
    query: str
    agent_response: str
    confidence_score: float
    escalation_reason: str  # low_confidence | no_results
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    user_agency: Optional[str] = None
    user_office: Optional[str] = None
    agent_type: Optional[str] = None


class CreateTicketRequest(BaseModel):
    """Create ticket for existing failure"""
    user_phone: Optional[str] = None
    conversation_history: Optional[List[Dict]] = None


# === Endpoints ===

@router.post("/")
async def create_failure(request: CreateFailureRequest, http_request: Request):
    """
    Create agent failure record
    
    Called when agent can't answer and escalation is offered
    Rate limited to 10 failures per day (prevents abuse)
    """
    try:
        # ============ RATE LIMITING ============
        # Rate limit failure reporting to prevent spam
        check_rate_limit(
            request=http_request,
            endpoint_type="ticket",
            agent_id=request.agent_id,
            user_email=request.user_email
        )
        # =======================================
        
        logger.info(f"📝 Recording failure: {request.query[:50]}...")
        
        service = get_failure_service()
        result = service.create_failure(
            session_id=request.session_id,
            agent_id=request.agent_id,
            query=request.query,
            agent_response=request.agent_response,
            confidence_score=request.confidence_score,
            escalation_reason=request.escalation_reason,
            user_email=request.user_email,
            user_name=request.user_name,
            user_agency=request.user_agency,
            user_office=request.user_office,
            agent_type=request.agent_type
        )
        
        if result["success"]:
            return {
                "success": True,
                "failure_id": result["failure_id"],
                "message": "Failure recorded"
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Create failure error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{failure_id}/create-ticket")
async def create_ticket(failure_id: str, request: CreateTicketRequest, http_request: Request):
    """
    Create Freshdesk ticket for an existing failure
    
    Updates failure record with ticket details
    Rate limited to 10 tickets per day
    """
    try:
        logger.info(f"🎫 Creating ticket for: {failure_id}")
        
        # Get failure record first (to get user info for rate limiting)
        service = get_failure_service()
        failure = service.get_failure(failure_id)
        
        if not failure:
            raise HTTPException(status_code=404, detail="Failure not found")
        
        # ============ RATE LIMITING ============
        # Also rate limit ticket creation
        check_rate_limit(
            request=http_request,
            endpoint_type="ticket",
            agent_id=failure.get("agent_id"),
            user_email=failure.get("user_email")
        )
        # =======================================
        
        if failure.get("ticket_created"):
            return {
                "success": True,
                "ticket_id": failure.get("ticket_id"),
                "message": "Ticket already exists"
            }
        
        # Create Freshdesk ticket with all user info
        # Use fallback email if user_email is empty or None
        user_email = failure.get("user_email") or "support@propertyengine.co.za"

        freshdesk = get_freshdesk_service()
        ticket_result = await freshdesk.create_escalation_ticket(
            query=failure.get("query", ""),
            agent_response=failure.get("agent_response", ""),
            confidence_score=failure.get("confidence_score", 0),
            user_email=user_email,
            user_name=failure.get("user_name"),
            user_phone=request.user_phone,
            user_agency=failure.get("user_agency"),
            user_office=failure.get("user_office"),
            conversation_history=request.conversation_history,
            escalation_reason=failure.get("escalation_reason", "low_confidence")
        )
        
        if not ticket_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Freshdesk error: {ticket_result.get('error')}"
            )
        
        # Update failure with ticket info
        service.update_ticket_created(
            failure_id=failure_id,
            ticket_id=ticket_result["ticket_id"],
            ticket_subject=ticket_result.get("ticket_subject"),
            ticket_priority=ticket_result.get("ticket_priority")
        )
        
        logger.info(f"✅ Ticket #{ticket_result['ticket_id']} created")
        
        return {
            "success": True,
            "ticket_id": ticket_result["ticket_id"],
            "message": f"Ticket #{ticket_result['ticket_id']} created"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Create ticket error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{failure_id}/decline")
async def decline_ticket(failure_id: str):
    """Mark failure as declined (user didn't want ticket)"""
    try:
        logger.info(f"📝 Declining: {failure_id}")
        
        service = get_failure_service()
        result = service.update_declined(failure_id)
        
        if result["success"]:
            return {"success": True, "message": "Marked as declined"}
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Decline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get failure statistics"""
    try:
        service = get_failure_service()
        stats = service.get_failure_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/needs-kb")
async def get_needs_kb(limit: int = 20):
    """Get failures needing KB entries"""
    try:
        service = get_failure_service()
        failures = service.get_failures_needing_kb(limit)
        return {"success": True, "failures": failures, "count": len(failures)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Freshdesk Webhook ===

@router.post("/webhook/fd-ticket-closed")
async def fd_ticket_closed(request: Request):
    """
    Freshdesk Webhook - Ticket Closed

    Configure in Freshdesk:
    - URL: https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app/api/agent-failure/webhook/fd-ticket-closed
    - Method: POST
    - Content-Type: JSON

    Expected payload (use these placeholders in Freshdesk):
    {
        "ticket_id": {{ticket.id}},
        "subject": "{{ticket.subject}}",
        "description": "{{ticket.description}}",
        "agent_name": "{{ticket.agent.name}}",
        "status": "{{ticket.status}}",
        "root_cause": "{{ticket.cf_root_cause}}",
        "solution_steps": "{{ticket.cf_solutionadd_steps}}"
    }
    """
    try:
        payload = await request.json()

        # Extract fields from Freshdesk payload
        ticket_id = payload.get("ticket_id")
        status = payload.get("status")
        agent_name = payload.get("agent_name")
        root_cause = payload.get("root_cause")
        solution_steps = payload.get("solution_steps")

        logger.info(f"🎫 Freshdesk webhook: ticket #{ticket_id}, status: {status}, agent: {agent_name}")

        if not ticket_id:
            logger.warning("⚠️ Webhook missing ticket_id")
            return {"success": False, "error": "Missing ticket_id"}

        # Update Firebase record with resolution details
        service = get_failure_service()
        result = service.update_ticket_closed(
            ticket_id=int(ticket_id),
            agent_name=agent_name,
            root_cause=root_cause,
            solution_steps=solution_steps
        )

        if result["success"]:
            logger.info(f"✅ Ticket #{ticket_id} closed, failure record updated")
            return {"success": True, "message": f"Ticket #{ticket_id} marked as closed"}
        else:
            logger.warning(f"⚠️ Could not update failure for ticket #{ticket_id}: {result.get('error')}")
            return {"success": True, "message": "Webhook received", "note": result.get("error")}

    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return {"success": False, "error": str(e)}
