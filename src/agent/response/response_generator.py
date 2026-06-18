"""Response Generation Module

Generates LLM responses using retrieved context and conversation history.
"""

import logging
import json
import httpx
from typing import List, Optional, Dict
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.prompts.prompt_loader import prompt_loader
from src.analytics.tracking import token_tracker  # Updated import

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates responses using LLM with context"""
    
    def __init__(self):
        """Initialize LLM and load prompts"""
        # Pick the ANSWER-generation model once. Default = OpenAI proxy (gpt-4o-mini), which
        # buffers streamed responses (PII de-anon). With RESPONSE_USE_QWEN=true we generate
        # via the Qwen gateway instead — it streams token-by-token (verified). Both the
        # streaming and non-streaming paths use these, so the model stays consistent.
        # Embeddings are a separate call and are NOT affected by this switch.
        if settings.RESPONSE_USE_QWEN:
            self.response_api_key = settings.QWEN_API_KEY
            self.response_base_url = settings.QWEN_BASE_URL
            self.response_model = settings.QWEN_MODEL
            logger.info(f"🟣 Response model: Qwen ({self.response_model}) — token streaming enabled")
        else:
            self.response_api_key = settings.OPENAI_API_KEY
            self.response_base_url = settings.OPENAI_BASE_URL
            self.response_model = settings.OPENAI_MODEL

        self.llm = ChatOpenAI(
            api_key=self.response_api_key,
            base_url=self.response_base_url,
            model=self.response_model,
            temperature=0.7,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
        
        # Load prompts from YAML
        self.system_prompt = prompt_loader.load('system')
        self.response_prompt = prompt_loader.load('response_generator')
        
        logger.info("✅ ResponseGenerator initialized with YAML prompts")
    
    def _build_response_prompt(
        self,
        query: str,
        contexts: List[str],
        conversation_context: str = "",
        search_results: Optional[List[Dict]] = None,
        clarification_type: Optional[str] = None,
    ) -> str:
        """Build the full LLM prompt (system + context + query). Shared by the
        streaming and non-streaming response paths so they stay identical."""
        # Use formatted context with source attribution if search_results provided
        if search_results is not None:
            from src.agent.context import ContextBuilder
            if search_results:  # If not empty
                context_text = ContextBuilder.format_contexts_with_sources(search_results, max_contexts=3)
                logger.info(f"🔍 KB Context with source attribution ({len(search_results)} results):")
                for i, r in enumerate(search_results[:3], 1):
                    metadata = r.get("metadata", {})
                    title = metadata.get("parent_title") or metadata.get("title") or "Untitled"
                    logger.info(f"  Source {i}: {title} (confidence: {r.get('similarity_score', 0.0):.2f})")
            else:
                context_text = "\n\n".join(contexts[:3]) if contexts else "No relevant information found."
                logger.debug("📝 No search results (context-based response)")
        else:
            context_text = "\n\n".join(contexts[:3]) if contexts else "No relevant information found."
            logger.warning("⚠️ Using legacy context format without source attribution")

        full_prompt = (
            self.system_prompt + "\n\n" +
            self.response_prompt.format(
                conversation_context=conversation_context or "No previous conversation",
                context=context_text,
                query=query
            )
        )

        if clarification_type == "error_specifics":
            full_prompt += (
                "\n\nIMPORTANT: The search results contain multiple possible causes for this issue. "
                "Give a brief, helpful overview of the most common causes (top 2-3 only), then ask "
                "the user if they are seeing a specific reason code, error code, or error message on "
                "screen, or ask them to describe exactly what happens when the issue occurs. "
                "Keep your response concise — this helps narrow down the right solution."
            )
        return full_prompt

    async def generate_response(
        self,
        query: str,
        contexts: List[str],
        conversation_context: str = "",
        session_id: Optional[str] = None,  # For cost tracking
        search_results: Optional[List[Dict]] = None,  # For source attribution
        clarification_type: Optional[str] = None  # "error_specifics" or None
    ) -> str:
        """
        Generate response using LLM with retrieved context (non-streaming).

        Returns:
            Generated response string
        """
        full_prompt = self._build_response_prompt(
            query, contexts, conversation_context, search_results, clarification_type
        )

        logger.debug(f"Generating response for: {query[:50]}...")

        response = await self.llm.ainvoke([HumanMessage(content=full_prompt)])

        # Track token usage and cost (best-effort — never let cost accounting break a reply,
        # e.g. if the response model isn't in the cost table).
        try:
            token_tracker.track_chat_usage(
                response=response,
                model=self.response_model,
                session_id=session_id,
                operation="response_generation"
            )
        except Exception as e:
            logger.debug(f"Cost tracking skipped: {e}")

        logger.info(f"✅ Response generated ({len(response.content)} chars)")

        return response.content

    async def generate_response_stream(
        self,
        query: str,
        contexts: List[str],
        conversation_context: str = "",
        session_id: Optional[str] = None,
        search_results: Optional[List[Dict]] = None,
        clarification_type: Optional[str] = None,
    ):
        """
        Streaming version of generate_response. Yields answer text chunks as the
        LLM produces them, then records token/cost usage once the stream completes.

        Yields:
            str: incremental text chunks (tokens)
        """
        full_prompt = self._build_response_prompt(
            query, contexts, conversation_context, search_results, clarification_type
        )

        logger.debug(f"Streaming response for: {query[:50]}...")

        # Raw httpx SSE request (not the langchain/openai-SDK client) so we yield each token
        # AS IT ARRIVES. Target is the configured response model (see __init__):
        #   - OpenAI proxy (default): BUFFERS prompts >~100 chars — its PII de-anonymisation
        #     collects the full response first, so real RAG answers arrive as one chunk
        #     (see docs/LIMITATIONS.md). Correct, but not truly incremental.
        #   - Qwen gateway (RESPONSE_USE_QWEN=true): streams token-by-token for real (verified).
        # stream_usage is intentionally not requested; cost is estimated below.
        full_text_parts = []
        url = self.response_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.response_model,
            "stream": True,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": full_prompt}],
        }
        headers = {
            "Authorization": f"Bearer {self.response_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = json.loads(data)["choices"][0]["delta"].get("content")
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                        if delta:
                            full_text_parts.append(delta)
                            yield delta
        except Exception as e:
            # Safety net: if the raw stream fails AND we haven't emitted anything yet, fall back
            # to the non-streaming path so the chat never breaks (user gets the whole answer once).
            logger.warning(f"httpx streaming failed ({e}); falling back to non-streaming")
            if not full_text_parts:
                full = await self.generate_response(
                    query, contexts, conversation_context,
                    session_id=session_id, search_results=search_results,
                    clarification_type=clarification_type,
                )
                full_text_parts.append(full)
                yield full

        # Best-effort cost estimate (no usage metadata on streamed responses).
        # Never let cost accounting break the stream.
        try:
            full_text = "".join(full_text_parts)
            token_tracker.track_estimated_usage(
                input_text=full_prompt,
                output_text=full_text,
                model=self.response_model,
                session_id=session_id,
                operation="response_generation",
            )
        except Exception as e:
            logger.debug(f"Streaming cost estimate skipped: {e}")

        logger.info("✅ Streaming response complete")
    
    async def generate_fallback_response(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Generate response when no knowledge base results found.
        Returns a fixed message — no LLM call to prevent hallucination.

        Args:
            query: User's query
            session_id: Session ID for token tracking

        Returns:
            Fallback response string
        """
        logger.info(f"⚠️ No KB results (session={session_id}) — returning fixed fallback (no LLM call)")

        return (
            "I couldn't find an exact match for that. Do you have a specific reason code or "
            "error message, or can you describe exactly what you're seeing? That might help me "
            "find the right article. Otherwise, I can escalate this to our support team."
        )
    
    async def generate_greeting_response(self) -> str:
        """Generate friendly greeting response"""
        return "Hello! I'm here to help you with PropertyEngine. What would you like to know?"

    async def generate_farewell_response(self) -> str:
        """Generate friendly farewell response"""
        return "You're welcome! If you need anything else, feel free to ask anytime."

    async def generate_escalation_response(self) -> str:
        """Generate escalation confirmation response"""
        return (
            "I'd be happy to connect you with our support team. "
            "I'll create a support ticket for you now so that a team member can assist you directly."
        )
