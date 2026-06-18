"""Firestore persistence for the interaction-centric chatbot model.

This is the durable source of truth for the customer chat: one `chatbot_interactions`
document per turn (question + answer + sources + confidence + escalation + feedback +
ticket), grouped under a `chatbot_sessions` document per conversation.

It consolidates what used to be spread across three collections — feedback and
escalation are now *updates* to the interaction, not separate `response_feedback` /
`agent_failures` documents. Live conversation context still flows through Redis
(session_manager) on the hot path; this layer is the persistent record.

Lifecycle of one interaction (create-then-update):
    create_interaction()    → status "streaming"   (question stored, answer pending)
    complete_interaction()  → status "complete"    (answer + sources + confidence)
    add_feedback()          → feedback field        (👍/👎, later)
    attach_ticket()         → ticket field          (escalation, later)
"""

import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)


class FirebaseInteractionService:
    """CRUD for the chatbot `sessions` + `interactions` collections."""

    def __init__(self):
        self.db = get_firestore_client()
        self.sessions_collection = "chatbot_sessions"
        self.interactions_collection = "chatbot_interactions"

    # ---- sessions -------------------------------------------------------

    def create_or_get_session(
        self,
        created_by: str,
        user_info: Optional[Dict] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Return an existing session id, or create a new session owned by `created_by`.

        Identity (`created_by`) is resolved from the verified token in the route; the
        `user_info` business-context (agency/office/user_type) is snapshotted onto the
        session so every conversation records who/what context it ran under.
        """
        user_info = user_info or {}
        if session_id and self._session_exists(session_id):
            self._touch_session(session_id)
            return session_id

        session_id = session_id or str(uuid.uuid4())
        session_data = {
            "id": session_id,
            "created_by": created_by,
            # business-context snapshot (NOT identity — identity is created_by)
            "user_email": user_info.get("email"),
            "user_name": user_info.get("name"),
            "company": user_info.get("company"),
            "division": user_info.get("division"),
            "agency": user_info.get("agency"),
            "office": user_info.get("office"),
            "user_type": user_info.get("user_type"),
            "created_at": SERVER_TIMESTAMP,
            "last_activity": SERVER_TIMESTAMP,
            "interaction_count": 0,
            "status": "active",
        }
        try:
            if self.db:
                self.db.collection(self.sessions_collection).document(session_id).set(session_data)
                logger.info(f"✅ Created chatbot session: {session_id}")
        except Exception as e:
            logger.error(f"❌ Failed to create chatbot session {session_id}: {e}")
        return session_id

    def _session_exists(self, session_id: str) -> bool:
        try:
            if not self.db:
                return False
            return self.db.collection(self.sessions_collection).document(session_id).get().exists
        except Exception:
            return False

    def _touch_session(self, session_id: str) -> None:
        try:
            if self.db:
                self.db.collection(self.sessions_collection).document(session_id).update(
                    {"last_activity": SERVER_TIMESTAMP})
        except Exception as e:
            logger.warning(f"⚠️ Could not touch session {session_id}: {e}")

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Fetch just the session document (no interactions)."""
        try:
            if not self.db:
                return None
            doc = self.db.collection(self.sessions_collection).document(session_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"❌ Failed to get session {session_id}: {e}")
            return None

    def list_sessions(self, created_by: str, limit: int = 50) -> List[Dict]:
        """List a user's conversations, most recent activity first."""
        try:
            if not self.db:
                return []
            q = (self.db.collection(self.sessions_collection)
                 .where("created_by", "==", created_by)
                 .order_by("last_activity", direction="DESCENDING")
                 .limit(limit))
            return [d.to_dict() for d in q.get()]
        except Exception as e:
            logger.error(f"❌ Failed to list sessions for {created_by}: {e}")
            return []

    def get_session_with_interactions(self, session_id: str) -> Optional[Dict]:
        """One conversation with all its interactions in chronological order."""
        try:
            if not self.db:
                return None
            doc = self.db.collection(self.sessions_collection).document(session_id).get()
            if not doc.exists:
                return None
            session = doc.to_dict()
            q = (self.db.collection(self.interactions_collection)
                 .where("session_id", "==", session_id)
                 .order_by("created_at", direction="ASCENDING"))
            session["interactions"] = [d.to_dict() for d in q.get()]
            return session
        except Exception as e:
            logger.error(f"❌ Failed to load session {session_id}: {e}")
            return None

    # ---- interactions ---------------------------------------------------

    def create_interaction(
        self,
        session_id: str,
        created_by: str,
        question: str,
        user_info: Optional[Dict] = None,
    ) -> str:
        """Create the per-turn record up front (status=streaming) and return its id.

        The answer/sources/confidence land later via complete_interaction once the
        stream finishes — this is the create-then-update lifecycle that lets the
        frontend poll GET /{id} to resume an interrupted stream.
        """
        interaction_id = str(uuid.uuid4())
        data = {
            "id": interaction_id,
            "session_id": session_id,
            "created_by": created_by,
            "question": question,
            "answer": "",
            "status": "streaming",
            "metadata": {},
            "escalation_required": False,
            "escalation_reason": "none",
            "feedback": None,
            "ticket": None,
            "created_at": SERVER_TIMESTAMP,
            "completed_at": None,
        }
        try:
            if self.db:
                self.db.collection(self.interactions_collection).document(interaction_id).set(data)
                self.db.collection(self.sessions_collection).document(session_id).update({
                    "interaction_count": Increment(1),
                    "last_activity": SERVER_TIMESTAMP,
                })
        except Exception as e:
            logger.error(f"❌ Failed to create interaction {interaction_id}: {e}")
        return interaction_id

    def complete_interaction(
        self,
        interaction_id: str,
        answer: str,
        sources: Optional[List[Dict]],
        metadata: Optional[Dict],
    ) -> Dict:
        """Persist the final answer + retrieval metadata when the stream completes."""
        meta = metadata or {}
        update = {
            "answer": answer,
            "status": "complete",
            "completed_at": SERVER_TIMESTAMP,
            "metadata": {
                "confidence": meta.get("confidence"),
                "query_type": meta.get("query_type"),
                "enhanced_query": meta.get("enhanced_query"),
                # per-turn record of "what was pulled" (the kb_stats-style detail)
                "sources_used": [s.get("title") for s in (sources or [])],
                "sources_count": len(sources or []),
            },
            "escalation_required": meta.get("requires_escalation", False),
            "escalation_reason": meta.get("escalation_reason", "none"),
        }
        return self._update(interaction_id, update)

    def fail_interaction(self, interaction_id: str, error: Optional[str] = None) -> Dict:
        """Mark a turn failed (stream errored before completing)."""
        return self._update(interaction_id, {
            "status": "failed",
            "completed_at": SERVER_TIMESTAMP,
            "error": (error or "")[:500],
        })

    def get_interaction(self, interaction_id: str) -> Optional[Dict]:
        try:
            if not self.db:
                return None
            doc = self.db.collection(self.interactions_collection).document(interaction_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"❌ Failed to get interaction {interaction_id}: {e}")
            return None

    def add_feedback(self, interaction_id: str, feedback_type: str, comment: Optional[str] = None) -> Dict:
        """Attach 👍/👎 to a turn (an update to the same interaction record)."""
        return self._update(interaction_id, {
            "feedback": {
                "type": feedback_type,
                "comment": comment,
                "at": datetime.now().isoformat(),
            }
        })

    def attach_ticket(self, interaction_id: str, ticket: Dict) -> Dict:
        """Record (or update) the Freshdesk ticket linked to this interaction."""
        return self._update(interaction_id, {"ticket": ticket})

    def _update(self, interaction_id: str, fields: Dict[str, Any]) -> Dict:
        try:
            if not self.db:
                return {"success": False, "error": "Firestore unavailable"}
            self.db.collection(self.interactions_collection).document(interaction_id).update(fields)
            return {"success": True}
        except Exception as e:
            logger.error(f"❌ Failed to update interaction {interaction_id}: {e}")
            return {"success": False, "error": str(e)}
