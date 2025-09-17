"""Agent orchestrator for intelligent query routing and response generation"""

from typing import Dict, List, Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import logging
import re
from src.config.settings import settings
from src.query.vector_search import VectorSearch
from src.memory.session_manager import SessionManager
from src.utils.failsafe import create_request_tracker, with_failsafe, RequestTracker
from src.prompts.system_prompts import (
    SYSTEM_PROMPT,
    RESPONSE_GENERATION_PROMPT,
    FALLBACK_PROMPT
)

logger = logging.getLogger(__name__)

class QueryClassifier:
    """Classifies user queries to determine routing"""
    
    PATTERNS = {
        "greeting": [
            r"\b(hi|hello|hey|good morning|good afternoon)\b",
            r"^(hi|hello|hey)$"
        ],
        "error": [
            r"\berror\s*\d+\b",  # Match "error 405", "error405", etc. first
            r"\berror\b",
            r"\bissue\b",
            r"\bproblem\b",
            r"\bfail(ed|ing|ure)?\b",
            r"\bnot work(ing)?\b"
        ],
        "definition": [
            r"\bwhat (is|are|does|do)\b(?!.*\berror\b)",  # Include "what does" and "what do"
            r"\bdefine\b",
            r"\bmeaning of\b",
            r"\bmean\b(?!.*\berror\b)",  # Add "mean" pattern
            r"\btell me about\b",  # Add "tell me about" pattern
            r"\bexplain\b(?!.*\berror\b)"  # Exclude if contains "error"
        ],
        "howto": [
            r"\bhow (to|do|can)\b",
            r"\bsteps to\b",
            r"\bprocess for\b",
            r"\bguide\b"
        ],
        "workflow": [
            r"\bworkflow\b",
            r"\bprocess\b",
            r"\bautomation\b",
            r"\bsequence\b"
        ]
    }
    
    @classmethod
    def classify(cls, query: str) -> Tuple[str, float]:
        """Classify query and return (type, confidence)"""
        query_lower = query.lower().strip()
        
        # Check patterns
        for query_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return query_type, 0.8
        
        # Default to definition for unknown queries
        return "definition", 0.5

class Agent:
    """Main agent orchestrator for handling user queries"""
    
    def __init__(self):
        """Initialize the agent with LLM and vector search"""
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            temperature=0.7
        )
        # Uses singleton connections now - no more recreating connections per query
        self.vector_search = VectorSearch()
        self.session_manager = SessionManager()
        self.classifier = QueryClassifier()
        
        logger.info("Agent orchestrator initialized with singleton connections")
    
    async def process_query(
        self, 
        query: str, 
        session_id: str,
        user_info: Optional[Dict] = None,
        user_type_filter: Optional[str] = None
    ) -> Dict:
        """Process a user query and return a response"""
        try:
            # Add to session history - COMMENTED OUT for performance (use chat summaries instead)
            # self.session_manager.add_message(session_id, "user", query)
            
            # Classify query
            query_type, confidence = self.classifier.classify(query)
            logger.info(f"Query classified as {query_type} with confidence {confidence}")
            logger.info(f"🔍 DEBUG: Classification confidence value = {confidence} (type: {type(confidence)})")
            
            # Handle greetings without search
            if query_type == "greeting":
                response = "Hello! I'm here to help you with PropertyEngine. What would you like to know?"
                # self.session_manager.add_message(session_id, "assistant", response) # COMMENTED OUT for performance
                return {
                    "response": response,
                    "confidence": 1.0,
                    "sources": [],
                    "query_type": query_type
                }
            
            # Determine search parameters based on query type
            # All searches now use the unified collection with metadata filtering
            entry_type = query_type  # Map query_type directly to entry_type
            
            # Clean query for search
            search_query = self.vector_search.clean_query(query)
            
            # Track search attempts for debugging
            search_attempts = []
            cached_embeddings = None  # Cache embeddings between searches
            
            # Search knowledge base with metadata filtering + fallback strategy
            search_attempts.append(f"primary:{entry_type}")
            results, cached_embeddings = await self.vector_search.search(
                query=search_query,
                entry_type=entry_type,
                user_type=user_type_filter,  # Add user type filtering
                k=settings.MAX_SEARCH_RESULTS
            )
            
            # Fallback Strategy 1: If no results, try without entry_type filter (reuse embeddings)
            if not results:
                logger.info(f"No results for {entry_type}, trying without entry_type filter")
                search_attempts.append("fallback:no_filter")
                results, _ = await self.vector_search.search(
                    query=search_query,
                    user_type=user_type_filter,  
                    k=settings.MAX_SEARCH_RESULTS,
                    query_embeddings=cached_embeddings  # Reuse embeddings
                )
            
            # Fallback Strategy 2: If still no results and query was "howto", try "error"
            if not results and query_type == "howto":
                logger.info(f"No results for howto, trying error type")
                search_attempts.append("fallback:error")
                results, _ = await self.vector_search.search(
                    query=search_query,
                    entry_type="error",
                    user_type=user_type_filter,
                    k=settings.MAX_SEARCH_RESULTS,
                    query_embeddings=cached_embeddings  # Reuse embeddings
                )
            
            # Fallback Strategy 3: If query was misclassified as "definition" but contains "error"
            if not results and query_type == "definition" and "error" in search_query.lower():
                logger.info(f"Definition query contains 'error', trying error type")
                search_attempts.append("fallback:error_detected")
                results, _ = await self.vector_search.search(
                    query=search_query,
                    entry_type="error",
                    user_type=user_type_filter,
                    k=settings.MAX_SEARCH_RESULTS,
                    query_embeddings=cached_embeddings  # Reuse embeddings
                )
            
            if results:
                # Extract contexts from results
                contexts = [r["content"] for r in results if r["content"]]
                
                # Calculate best similarity score for overall confidence
                best_similarity = max([r["similarity_score"] for r in results]) if results else 0.0
                
                # Build sources with proper metadata and individual similarity scores
                sources = [{
                    "title": r["metadata"].get("title", "Untitled Entry"),
                    "section": r["entry_type"], 
                    "confidence": r["similarity_score"],  # Use individual similarity score
                    "content_preview": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"],
                    "metadata": r["metadata"],
                    "entry_type": r["entry_type"],
                    "user_type": r["user_type"],
                    "similarity_score": r["similarity_score"]
                } for r in results]
                
                # Get conversation context from session
                conversation_context = ""
                try:
                    session = self.session_manager.get_session(session_id)
                    if session and "messages" in session:
                        # Get last few messages for context
                        recent_messages = session["messages"][-4:]  # Last 4 messages
                        conversation_context = "\n".join([
                            f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
                            for msg in recent_messages
                        ])
                except Exception as e:
                    logger.warning(f"Could not get conversation context: {e}")
                
                # Generate response using LLM
                response = await self.generate_response(query, contexts, conversation_context)
                
                # self.session_manager.add_message(session_id, "assistant", response) # COMMENTED OUT for performance
                
                # Use similarity score for escalation decision (lowered threshold)
                requires_escalation = best_similarity < 0.7  # Use similarity score, not classification!
                
                # DEBUG: Log what we're sending to frontend
                logger.info(f"🔍 SENDING TO FRONTEND - Similarity: {best_similarity}, Classification: {confidence}, Escalation: {requires_escalation}")
                
                return {
                    "response": response,
                    "confidence": best_similarity,  # Use best similarity score
                    "classification_confidence": confidence,  # Keep for debugging
                    "sources": sources,
                    "query_type": query_type,
                    "search_type": "metadata_filtered",
                    "search_attempts": search_attempts,  # Add search attempts
                    "requires_escalation": requires_escalation
                }
            else:
                # No results found - use fallback
                response = await self.generate_fallback_response(query)
                # self.session_manager.add_message(session_id, "assistant", response) # COMMENTED OUT for performance
                
                # Log failed query for analysis
                logger.warning(f"No results found for query: {query} with entry_type: {entry_type}")
                
                return {
                    "response": response,
                    "confidence": 0.3,
                    "sources": [],
                    "query_type": query_type,
                    "search_type": "metadata_filtered", 
                    "note": "No matching content found in knowledge base",
                    "requires_escalation": True
                }
                
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            error_response = "I apologize, but I encountered an error while processing your request. Please try again."
            
            return {
                "response": error_response,
                "confidence": 0.0,
                "sources": [],
                "error": str(e)
            }
    
    async def generate_response(self, query: str, contexts: List[str], conversation_context: str = "") -> str:
        """Generate response using LLM with retrieved context"""
        context_text = "\n\n".join(contexts[:3])  # Use top 3 contexts
        
        prompt = RESPONSE_GENERATION_PROMPT.format(
            conversation_context=conversation_context,
            context=context_text,
            query=query
        )
        
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        return response.content
    
    async def generate_fallback_response(self, query: str) -> str:
        """Generate response when no knowledge base results found"""
        prompt = FALLBACK_PROMPT.format(query=query)
        
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        return response.content
