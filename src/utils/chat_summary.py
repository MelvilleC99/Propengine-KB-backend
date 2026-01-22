"""Chat summarization utility for PropertyEngine KB

Handles both rolling summaries (active sessions) and final summaries (session end).
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.prompts.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)


class ChatSummarizer:
    """Generates summaries of chat conversations"""
    
    def __init__(self):
        """Initialize with LLM and system prompt"""
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.1,  # Low temperature for consistent summaries
            max_tokens=300
        )
        
        # Load system prompt once
        self.system_prompt = prompt_loader.load('system')
        
        logger.info("✅ ChatSummarizer initialized")
    
    async def generate_rolling_summary(
        self,
        previous_summary: Optional[str],
        new_messages: List[Dict],
        session_id: str
    ) -> Dict:
        """
        Generate rolling summary for active session (stored in Redis)
        
        Args:
            previous_summary: Previous rolling summary (or None)
            new_messages: New messages since last summary (2-5 messages)
            session_id: Session identifier for logging
            
        Returns:
            {
                "summary": "Brief overview (max 100 words)",
                "current_topic": "listings_photos",
                "conversation_state": "troubleshooting",
                "key_facts": ["file size 10MB", "needs resize"]
            }
        """
        if not new_messages:
            logger.warning(f"No new messages for rolling summary: {session_id}")
            return self._empty_summary()
        
        try:
            # Format messages for summary
            messages_text = self._format_messages_for_summary(new_messages)
            
            # Build prompt
            prompt = f"""
{self.system_prompt}

TASK: Update the conversation summary for this ongoing support session.

PREVIOUS SUMMARY:
{previous_summary or "None - this is the first summary of the conversation"}

NEW MESSAGES SINCE LAST SUMMARY:
{messages_text}

Generate an updated rolling summary that:
1. Incorporates previous summary if it exists
2. Adds key information from new messages
3. Tracks what the user is currently focused on
4. Notes the conversation state
5. Preserves important facts mentioned

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "summary": "concise overview in 2-3 sentences (max 100 words)",
  "current_topic": "specific topic user is focused on (e.g., listing_photos, api_keys, error_405)",
  "conversation_state": "exploring OR troubleshooting OR resolved",
  "key_facts": ["important fact 1", "important fact 2"]
}}
"""
            
            logger.debug(f"Generating rolling summary for session: {session_id}")
            
            # Generate summary
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # Parse JSON
            summary_data = self._parse_json_response(response.content)
            
            # Add metadata
            summary_data["updated_at"] = datetime.now().isoformat()
            summary_data["message_count"] = len(new_messages)
            
            logger.info(f"✅ Rolling summary generated for {session_id}: topic={summary_data.get('current_topic')}")
            
            return summary_data
            
        except Exception as e:
            logger.error(f"Failed to generate rolling summary for {session_id}: {e}")
            return self._empty_summary()
    
    async def generate_final_summary(
        self,
        all_messages: List[Dict],
        session_info: Dict
    ) -> Dict:
        """
        Generate final summary at session end (stored in Firebase)
        
        More detailed than rolling summary, includes analytics.
        
        Args:
            all_messages: All messages from the session
            session_info: Session metadata (user_id, start_time, etc.)
            
        Returns:
            {
                "summary": "Detailed overview",
                "topics": ["topic1", "topic2"],
                "resolution_status": "resolved",
                "user_satisfaction": "satisfied",
                "key_issues": "Main problems discussed",
                "outcome": "What was achieved"
            }
        """
        if len(all_messages) < 2:
            return self._minimal_final_summary(all_messages, session_info)
        
        try:
            # Format all messages
            conversation_text = self._format_messages_for_summary(all_messages)
            user_email = session_info.get("user_email", "unknown")
            
            # Build prompt
            prompt = f"""
{self.system_prompt}

TASK: Create a final summary of this completed support session for analytics and record-keeping.

SESSION INFO:
User: {user_email}
Messages: {len(all_messages)}

FULL CONVERSATION:
{conversation_text}

Analyze the conversation and provide a structured summary.

Respond ONLY with valid JSON:
{{
  "summary": "2-3 sentence overview of what happened",
  "topics": ["main topic 1", "main topic 2"],
  "resolution_status": "resolved OR partial OR escalated OR abandoned",
  "user_satisfaction": "satisfied OR neutral OR frustrated OR unknown",
  "key_issues": "Main problems or questions raised",
  "outcome": "What was achieved or decided"
}}
"""
            
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            summary_data = self._parse_json_response(response.content)
            
            # Add session metrics
            summary_data.update({
                "message_count": len(all_messages),
                "session_duration": self._calculate_session_duration(all_messages),
                "created_at": datetime.now().isoformat(),
                "session_id": session_info.get("session_id")
            })
            
            logger.info(f"✅ Final summary generated: {summary_data.get('resolution_status')}")
            
            return summary_data
            
        except Exception as e:
            logger.error(f"Failed to generate final summary: {e}")
            return self._minimal_final_summary(all_messages, session_info)
    
    # === HELPER METHODS ===
    
    def _format_messages_for_summary(self, messages: List[Dict]) -> str:
        """Format messages into readable text"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")[:500]  # Limit length
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)
    
    def _parse_json_response(self, response: str) -> Dict:
        """Parse LLM JSON response, handling markdown formatting"""
        try:
            # Remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.replace("```json", "").replace("```", "").strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned.replace("```", "").strip()
            
            return json.loads(cleaned)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response}")
            return self._empty_summary()
    
    def _calculate_session_duration(self, messages: List[Dict]) -> Optional[int]:
        """Calculate session duration in seconds"""
        if len(messages) < 2:
            return None
        
        try:
            first_time = messages[0].get("timestamp")
            last_time = messages[-1].get("timestamp")
            
            if first_time and last_time:
                first_dt = datetime.fromisoformat(first_time.replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
                duration = (last_dt - first_dt).total_seconds()
                return int(duration)
                
        except Exception as e:
            logger.error(f"Failed to calculate duration: {e}")
        
        return None
    
    def _empty_summary(self) -> Dict:
        """Return empty summary structure"""
        return {
            "summary": "",
            "current_topic": "unknown",
            "conversation_state": "unknown",
            "key_facts": []
        }
    
    def _minimal_final_summary(self, messages: List[Dict], session_info: Dict) -> Dict:
        """Create minimal final summary when generation fails"""
        return {
            "summary": f"Chat session with {len(messages)} messages",
            "topics": ["general inquiry"],
            "resolution_status": "unknown",
            "user_satisfaction": "unknown",
            "key_issues": "Insufficient data for analysis",
            "outcome": "Session completed",
            "message_count": len(messages),
            "session_duration": self._calculate_session_duration(messages),
            "created_at": datetime.now().isoformat()
        }


# Global summarizer instance
chat_summarizer = ChatSummarizer()
