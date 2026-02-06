"""Context Analyzer - Analyzes conversation context and follow-up queries

UPDATED: Using LLM instead of regex for followup detection
"""

import logging
from typing import Dict, Optional, List
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.agent.response import ResponseGenerator
from src.memory.session_manager import SessionManager

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """Analyzes conversation context to detect follow-ups and handle context-based responses"""
    
    def __init__(self):
        """Initialize context analyzer with required components"""
        self.response_generator = ResponseGenerator()
        self.session_manager = SessionManager()
        
        # LLM for followup detection
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.3
        )
        
        logger.info("✅ Context analyzer initialized (LLM-powered)")
    
    async def try_answer_from_context(
        self,
        query: str,
        conversation_context: str,
        session_id: str
    ) -> Optional[Dict]:
        """
        Smart follow-up handling with three-tier strategy:
        1. Check if it's a follow-up query
        2. Try to answer from conversation context
        3. Check if query matches a related document from previous KB responses
        4. Fall back to full RAG if none of the above work

        Args:
            query: User's query
            conversation_context: Previous conversation history
            session_id: Session identifier

        Returns:
            Response dict with full analytics if handled, None otherwise (triggers full RAG)
        """
        # Step 1: Is this a follow-up?
        if not await self.is_followup_query(query, conversation_context):
            logger.debug("Not a follow-up query, proceeding to full RAG")
            return None

        logger.info("📝 Detected follow-up query, using smart routing")

        # Step 2: Can we answer from conversation context?
        can_answer = await self._can_answer_from_conversation(query, conversation_context)

        if can_answer:
            logger.info("✅ Answering from conversation context")
            return await self._answer_from_conversation(query, conversation_context, session_id)

        # Step 3: Check if query matches a related document
        related_doc = await self._find_related_document_match(query, session_id)

        if related_doc:
            logger.info(f"✅ Query matches related document: {related_doc}")
            # Fall back to full RAG - orchestrator will do targeted search
            # We could enhance the query here or signal to search for specific doc
            return None

        # Step 4: Can't handle it, fall back to full RAG
        logger.info("⚠️ Follow-up detected but can't answer from context or related docs, falling back to full RAG")
        return None

    async def _can_answer_from_conversation(self, query: str, conversation_context: str) -> bool:
        """
        Use LLM to check if query can be answered from conversation context alone

        Args:
            query: User's query
            conversation_context: Previous conversation history

        Returns:
            True if answerable from context, False otherwise
        """
        prompt = f"""Conversation history:
{conversation_context}

User question: "{query}"

Can this question be answered using ONLY the information in the conversation history above?

Answer "yes" ONLY if:
- The answer is explicitly stated in the conversation
- No additional KB lookup is needed

Answer "no" if:
- The question asks about a different topic or related topic not covered above
- Additional information would be needed to answer properly

Answer with just: yes or no"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            answer = response.content.strip().lower()
            can_answer = answer.startswith("yes")
            logger.debug(f"Can answer from conversation: {can_answer}")
            return can_answer
        except Exception as e:
            logger.error(f"Error checking if answerable from conversation: {e}")
            # Conservative fallback: assume we can't answer
            return False

    async def _answer_from_conversation(
        self,
        query: str,
        conversation_context: str,
        session_id: str
    ) -> Dict:
        """Generate response from conversation context only"""
        try:
            import time
            start_time = time.time()

            response = await self.response_generator.generate_response(
                query,
                [conversation_context],
                conversation_context,
                session_id=session_id
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # Build proper metadata
            metadata = {
                "query_type": "followup",
                "category": "conversation_context",
                "confidence_score": 0.9,
                "sources_found": 1,
                "sources_used": ["Conversation Context"],
                "related_documents": [],
                "response_time_ms": elapsed_ms,
                "escalated": False,
                "user_feedback": None
            }

            await self.session_manager.add_message(session_id, "assistant", response, metadata)

            # Return complete response dict matching orchestrator format
            return {
                "response": response,
                "confidence": 0.9,
                "sources": [{
                    "title": "Conversation Context",
                    "confidence": 0.9,
                    "entry_type": "context",
                    "user_type": "internal",
                    "content_preview": conversation_context[:200] + "..." if len(conversation_context) > 200 else conversation_context,
                    "metadata": {
                        "title": "Conversation Context",
                        "category": "conversation"
                    }
                }],
                "query_type": "followup",
                "classification_confidence": 1.0,
                "requires_escalation": False,
                "search_attempts": ["conversation_context"],
                "enhanced_query": query,
                "query_metadata": {
                    "category": "conversation_context",
                    "intent": "followup",
                    "tags": []
                },
                "debug_metrics": {
                    "from_context": True,
                    "response_time_ms": elapsed_ms
                }
            }
        except Exception as e:
            logger.error(f"Error answering from conversation: {e}")
            return None

    async def _find_related_document_match(self, query: str, session_id: str) -> Optional[str]:
        """
        Check if query matches any related documents from recent KB responses

        Args:
            query: User's query
            session_id: Session identifier

        Returns:
            Matched document title if found, None otherwise
        """
        try:
            # Get recent messages to extract related documents
            messages = self.session_manager.context_cache.get_messages(session_id, limit=5)

            # Extract all related documents from assistant responses
            all_related_docs = []
            for msg in messages:
                if msg.get("role") == "assistant":
                    metadata = msg.get("metadata", {})
                    related_docs = metadata.get("related_documents", [])
                    all_related_docs.extend(related_docs)

            if not all_related_docs:
                logger.debug("No related documents found in conversation history")
                return None

            # Remove duplicates
            unique_docs = list(dict.fromkeys(all_related_docs))
            logger.debug(f"Found {len(unique_docs)} related documents: {unique_docs}")

            # Use LLM to check if query matches any related document
            docs_list = "\n".join([f"- {doc}" for doc in unique_docs])

            prompt = f"""User query: "{query}"

Related documents from previous responses:
{docs_list}

Does the user's query seem to be asking about one of these related documents?

Look for:
- Keywords that match document titles
- Topics that align with document names
- Requests for "other", "more", "additional" info that matches a related topic

If there's a clear match, respond with just the document title.
If no clear match, respond with: none

Response:"""

            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            match = response.content.strip()

            if match.lower() == "none" or not match:
                logger.debug("No related document match found")
                return None

            # Verify the match is in our list (LLM might hallucinate)
            if match in unique_docs:
                logger.info(f"✅ Matched related document: {match}")
                return match

            logger.debug(f"LLM suggested '{match}' but not in our list")
            return None

        except Exception as e:
            logger.error(f"Error finding related document match: {e}")
            return None
    
    async def is_followup_query(self, query: str, conversation_context: str) -> bool:
        """
        Detect if query is a follow-up question using LLM
        
        Args:
            query: User's query
            conversation_context: Previous conversation history
            
        Returns:
            True if follow-up, False otherwise
        """
        if not conversation_context.strip():
            return False
        
        # Check if context has meaningful content (not just errors)
        if "encountered an error" in conversation_context.lower() and len(conversation_context) < 300:
            logger.debug("Context contains only errors, treating as new query")
            return False
        
        # Use LLM to detect followup
        prompt = f"""Previous conversation:
{conversation_context}

New user query: "{query}"

Is this a follow-up question about the same topic as the conversation above?

IMPORTANT:
- If the conversation above only has errors or apologies, answer "no"
- If this seems like a brand new question unrelated to conversation, answer "no"  
- Only answer "yes" if the user is clearly continuing the same topic

Consider these as follow-ups:
- Requests for "more", "other", "additional" information about SAME topic
- Questions about specific parts mentioned before ("what about step 3?")
- Clarifications about something already discussed ("why is that?")
- Short questions that reference the previous topic ("how?", "when?")

Answer with just: yes or no"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            answer = response.content.strip().lower()
            
            is_followup = answer.startswith("yes")
            logger.debug(f"Followup detection: query='{query[:50]}', context_len={len(conversation_context)}, result={is_followup}")
            
            return is_followup
            
        except Exception as e:
            logger.error(f"Error in followup detection: {e}")
            # Fallback to simple heuristic
            return self._simple_followup_check(query, conversation_context)
    
    def _simple_followup_check(self, query: str, context: str) -> bool:
        """Simple fallback for followup detection if LLM fails"""
        query_lower = query.lower()
        
        # Simple keywords that usually indicate followup
        followup_words = ['other', 'more', 'another', 'else', 'also', 'what about', 'how about']
        
        # Short questions with followup words
        if len(query.split()) <= 8:
            if any(word in query_lower for word in followup_words):
                return True
        
        return False
