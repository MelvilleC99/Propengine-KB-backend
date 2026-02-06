"""Freshdesk Service - Creates support tickets via Freshdesk API"""

import logging
import httpx
from typing import Dict, List, Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)


class FreshdeskService:
    """
    Creates support tickets in Freshdesk
    
    Requires env vars:
    - FRESHDESK_DOMAIN
    - FRESHDESK_API_KEY
    """

    def __init__(self):
        self.domain = getattr(settings, 'FRESHDESK_DOMAIN', None)
        self.api_key = getattr(settings, 'FRESHDESK_API_KEY', None)
        self.responder_id = getattr(settings, 'FRESHDESK_RESPONDER_ID', None)

        if self.domain and self.api_key:
            self.base_url = f"https://{self.domain}/api/v2"
            self.configured = True
            logger.info(f"✅ Freshdesk service configured for domain: {self.domain}")
            if self.responder_id:
                logger.info(f"   Default responder ID: {self.responder_id}")
        else:
            self.base_url = None
            self.configured = False
            logger.warning("⚠️ Freshdesk not configured")

        # Cache for product ID
        self._product_id = None
    
    def _get_auth(self) -> tuple:
        """Basic auth for Freshdesk"""
        return (self.api_key, "X")
    
    async def _get_product_id(self) -> Optional[int]:
        """Fetch PropertyEngine product ID from Freshdesk"""
        if self._product_id:
            return self._product_id
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/products",
                    auth=self._get_auth(),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    products = response.json()
                    # Find PropertyEngine product or use first
                    pe_product = next((p for p in products if p.get('name') == 'PropertyEngine'), None)
                    self._product_id = pe_product['id'] if pe_product else (products[0]['id'] if products else None)
                    logger.info(f"📦 Using product ID: {self._product_id}")
                    return self._product_id
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch products: {e}")
        
        return None
    
    async def create_ticket(
        self,
        subject: str,
        description: str,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        priority: int = 2,
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict] = None
    ) -> Dict:
        """Create a Freshdesk ticket - auto-assigned via Freshdesk automation rules"""
        if not self.configured:
            return {"success": False, "error": "Freshdesk not configured"}

        try:
            # Get product ID
            product_id = await self._get_product_id()

            ticket_data = {
                "subject": subject,
                "description": description,
                "email": email,
                "priority": priority,
                "status": 2,  # Open
                "source": 2,  # Portal
                "tags": tags or ["propertyengine", "ai-escalation"],
            }

            # Add responder_id if configured (required by some Freshdesk accounts)
            if self.responder_id:
                ticket_data["responder_id"] = self.responder_id

            # Add requester name if provided
            if name:
                ticket_data["name"] = name

            if product_id:
                ticket_data["product_id"] = product_id

            if phone:
                ticket_data["phone"] = phone

            if custom_fields:
                ticket_data["custom_fields"] = custom_fields

            logger.info(f"🎫 Creating Freshdesk ticket:")
            logger.info(f"   Subject: {subject[:50]}...")
            logger.info(f"   Requester: {name} <{email}>")
            logger.info(f"   Priority: {priority}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/tickets",
                    json=ticket_data,
                    auth=self._get_auth(),
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    ticket = response.json()
                    logger.info(f"✅ Ticket created: #{ticket['id']}")
                    return {
                        "success": True,
                        "ticket_id": ticket["id"],
                        "ticket_subject": ticket.get("subject"),
                        "ticket_priority": ticket.get("priority")
                    }
                else:
                    error_body = response.text
                    logger.error(f"❌ Freshdesk error: {response.status_code}")
                    logger.error(f"   Response: {error_body}")
                    return {
                        "success": False,
                        "error": f"Freshdesk API error: {response.status_code}",
                        "details": error_body
                    }
                    
        except Exception as e:
            logger.error(f"❌ Freshdesk exception: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_escalation_ticket(
        self,
        query: str,
        agent_response: str,
        confidence_score: float,
        user_email: str,
        user_name: Optional[str] = None,
        user_phone: Optional[str] = None,
        user_agency: Optional[str] = None,
        user_office: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        escalation_reason: str = "low_confidence"
    ) -> Dict:
        """Create an escalation ticket with full context"""
        
        # Build subject
        subject = f"PropertyEngine AI Support: {query[:50]}{'...' if len(query) > 50 else ''}"
        
        # Build description with full user details
        description = self._format_description(
            query=query,
            agent_response=agent_response,
            confidence_score=confidence_score,
            user_name=user_name,
            user_agency=user_agency,
            user_office=user_office,
            conversation_history=conversation_history,
            escalation_reason=escalation_reason
        )
        
        # Determine priority (same logic as original)
        priority = self._determine_priority(query, confidence_score)
        
        # Custom fields - MATCHING ORIGINAL FRONTEND CODE
        custom_fields = {
            "cf_agency": user_agency or "PropertyEngine",
            "cf_office": user_office or "Support",
            "cf_category": "Listing",  # Default
            "cf_sub_category": "Other",  # Default
            "cf_case_ownership": "Support",
            "cf_resolution_process": "Customer Advised",
            "cf_root_cause": "Customer Inquiry",
            "cf_solutionadd_steps": "AI escalation - requires investigation"
        }
        
        logger.info(f"📋 Escalation ticket data:")
        logger.info(f"   Query: {query[:50]}...")
        logger.info(f"   User Email: {user_email}")
        logger.info(f"   User Name: {user_name}")
        logger.info(f"   Agency: {user_agency}")
        logger.info(f"   Office: {user_office}")
        
        return await self.create_ticket(
            subject=subject,
            description=description,
            email=user_email,
            name=user_name,
            phone=user_phone,
            priority=priority,
            tags=["propertyengine", "ai-escalation"],
            custom_fields=custom_fields
        )
    
    def _determine_priority(self, query: str, confidence: float) -> int:
        """Determine priority based on query and confidence (same as original)"""
        urgent_keywords = ['urgent', 'critical', 'down', 'broken', 'error', 'failed', 'stuck', 'help']
        is_urgent = any(keyword in query.lower() for keyword in urgent_keywords)
        
        if confidence < 0.3 or is_urgent:
            return 3  # High
        elif confidence < 0.6:
            return 2  # Medium
        else:
            return 1  # Low
    
    def _format_description(
        self,
        query: str,
        agent_response: str,
        confidence_score: float,
        user_name: Optional[str],
        user_agency: Optional[str],
        user_office: Optional[str],
        conversation_history: Optional[List[Dict]],
        escalation_reason: str
    ) -> str:
        """Format ticket description (similar to original)"""
        lines = [
            "=== PropertyEngine AI Chat Conversation ===",
            "",
            "--- Requester Details ---",
            f"Name: {user_name or 'Unknown'}",
            f"Agency: {user_agency or 'Not specified'}",
            f"Office: {user_office or 'Not specified'}",
            "",
            "--- Escalation Info ---",
            f"Reason: {escalation_reason}",
            f"AI Confidence: {confidence_score:.1%}",
            "",
            "--- Original Question ---",
            query,
            "",
            "--- AI Response ---",
            agent_response,
        ]

        if conversation_history:
            lines.extend([
                "",
                "--- Full Conversation History ---"
            ])
            for msg in conversation_history[-10:]:
                role = "👤 User" if msg.get("role") == "user" else "🤖 AI Assistant"
                lines.append(f"{role}: {msg.get('content', '')[:500]}")

        lines.extend([
            "",
            "=== End of Conversation ===",
            "Note: This ticket was automatically created because the AI couldn't provide a satisfactory answer."
        ])
        
        return "\n".join(lines)


# Singleton
_freshdesk_service = None

def get_freshdesk_service() -> FreshdeskService:
    global _freshdesk_service
    if _freshdesk_service is None:
        _freshdesk_service = FreshdeskService()
    return _freshdesk_service
