"""
Escalation Handler - Decides when (and how) to escalate a query to a human.

This is the single home for the escalation rules, so the orchestrator doesn't carry
them inline. It is PURE decision logic — no LLM call, no I/O — which keeps it fast and
trivially testable. "User explicitly asked for a human" is detected upstream by the fast
regex classifier (query_type == "escalation") and passed in here; we do NOT make a
separate LLM call for it.

Escalation scenarios:
1. User explicitly requested human help  -> immediate, offer a ticket
2. No results found                      -> immediate, offer a ticket
3. Low confidence (< MIN_CONFIDENCE_SCORE) -> conditional: give the answer, let the USER
                                             decide whether they want a ticket
4. Confident answer                      -> no escalation
"""

import logging
from typing import Dict, List
from src.config.settings import settings

logger = logging.getLogger(__name__)


class EscalationHandler:
    """Decides whether/why/how to escalate. Pure rules — no LLM, no network."""

    # Phrases that mean the LLM declined to answer from the retrieved context. Retrieval
    # confidence can be high on topically-near-but-wrong docs, so the score alone misses
    # these — we also scan the generated answer for these markers and escalate if found.
    NON_ANSWER_MARKERS = (
        "i don't have", "i do not have", "don't have specific", "do not have specific",
        "couldn't find", "could not find", "i'm not able to", "i am not able to",
        "no specific information", "don't have enough information", "i don't know",
        "not in the knowledge base", "no information on",
    )

    def is_non_answer(self, response_text: str) -> bool:
        """True if the generated answer is really a 'can't answer' response.

        Catches the case where retrieval looked confident (good rerank score) but the
        LLM still couldn't answer from the context — those should still offer a ticket.
        """
        text = (response_text or "").lower()
        return any(marker in text for marker in self.NON_ANSWER_MARKERS)

    def check_escalation(
        self,
        query_type: str,
        results: List[Dict],
        confidence: float,
    ) -> Dict:
        """
        Decide whether a query should be escalated.

        Args:
            query_type: classified query type. "escalation" means the user explicitly
                        asked for a human (detected upstream by the regex classifier).
            results: search results found (empty list = no results).
            confidence: best similarity/confidence score for the results.

        Returns:
            {should_escalate, escalation_reason, escalation_type, response_strategy}
        """
        # 1. User explicitly requested a human (classifier already detected this — no LLM)
        if query_type == "escalation":
            return self._verdict(True, "user_requested", "immediate", "offer_ticket")

        # 2. No results found at all
        if not results:
            return self._verdict(True, "no_results", "immediate", "offer_ticket")

        # 3. Low confidence — give the answer, then let the USER decide if they want a ticket
        if confidence < settings.MIN_CONFIDENCE_SCORE:
            return self._verdict(True, "low_confidence", "conditional", "ask_if_helps")

        # 4. Confident enough — no escalation
        return self._verdict(False, "none", "none", "none")

    @staticmethod
    def _verdict(should: bool, reason: str, etype: str, strategy: str) -> Dict:
        return {
            "should_escalate": should,
            "escalation_reason": reason,
            "escalation_type": etype,
            "response_strategy": strategy,
        }

    def format_escalation_response(self, base_response: str, escalation_info: Dict) -> str:
        """Append the appropriate escalation message to a base response."""
        etype = escalation_info.get("escalation_type")
        strategy = escalation_info.get("response_strategy")

        if etype == "immediate" and strategy == "offer_ticket":
            if escalation_info.get("escalation_reason") == "user_requested":
                return ("I'll help you raise a support ticket right away. Our team will get "
                        "back to you shortly. Would you like to proceed?")
            return (f"{base_response}\n\nI don't have enough information to fully answer this. "
                    "Would you like me to create a support ticket so our team can help you directly?")

        if etype == "conditional" and strategy == "ask_if_helps":
            return (f"{base_response}\n\nDoes this help answer your question, or would you like "
                    "me to create a support ticket for more detailed assistance?")

        return base_response

    def get_escalation_metadata(self, escalation_info: Dict) -> Dict:
        """Escalation fields for analytics/metadata."""
        return {
            "escalated": escalation_info.get("should_escalate", False),
            "escalation_reason": escalation_info.get("escalation_reason", "none"),
            "escalation_type": escalation_info.get("escalation_type", "none"),
            "response_strategy": escalation_info.get("response_strategy", "none"),
        }
