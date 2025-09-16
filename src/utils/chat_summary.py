"""Chat summarization utility for PropertyEngine KB"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

class ChatSummarizer:
    """Generates summaries of chat conversations"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",  # Faster and cheaper for summaries
            temperature=0.1,
            max_tokens=200  # Keep summaries concise
        )
        
    def create_summary(self, messages: List[Dict], session_info: Dict) -> Dict:
        """Create a summary of chat messages"""
        
        if len(messages) < 2:
            return {
                "summary": "Brief session with minimal interaction",
                "topics": [],
                "resolution_status": "incomplete",
                "user_satisfaction": "unknown"
            }
        
        # Format messages for summarization
        conversation_text = self._format_messages_for_summary(messages)
        
        # Generate summary using LLM
        summary_prompt = self._create_summary_prompt(conversation_text, session_info)
        
        try:
            response = self.llm([summary_prompt])
            summary_data = self._parse_summary_response(response.content)
            
            # Add metadata
            summary_data.update({
                "message_count": len(messages),
                "session_duration": self._calculate_session_duration(messages),
                "created_at": datetime.now().isoformat(),
                "summary_trigger": self._determine_summary_trigger(messages)
            })
            
            return summary_data
            
        except Exception as e:
            logger.error(f"Failed to generate chat summary: {e}")
            return self._create_fallback_summary(messages, session_info)
    
    def _format_messages_for_summary(self, messages: List[Dict]) -> str:
        """Format messages into readable text for summarization"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:500]  # Limit content length
            timestamp = msg.get("timestamp", "")
            
            formatted.append(f"{role.upper()}: {content}")
        
        return "\n".join(formatted)
    
    def _create_summary_prompt(self, conversation: str, session_info: Dict) -> SystemMessage:
        """Create prompt for conversation summarization"""
        
        user_info = session_info.get("user_email", "unknown user")
        
        prompt_text = f"""Analyze this PropertyEngine support conversation and provide a structured summary:

CONVERSATION:
{conversation}

USER: {user_info}

Provide your response in this exact format:

SUMMARY: [2-3 sentence overview of what happened]
TOPICS: [comma-separated list of main topics discussed]
RESOLUTION: [resolved|partial|escalated|abandoned]
SATISFACTION: [satisfied|neutral|frustrated|unknown]
KEY_ISSUES: [main problems or questions raised]
OUTCOME: [what was achieved or decided]

Keep it concise and factual."""

        return SystemMessage(content=prompt_text)
    
    def _parse_summary_response(self, response: str) -> Dict:
        """Parse LLM response into structured summary"""
        summary_data = {}
        
        # Extract sections using regex
        import re
        
        patterns = {
            "summary": r"SUMMARY:\s*(.+?)(?=\n[A-Z]+:|$)",
            "topics": r"TOPICS:\s*(.+?)(?=\n[A-Z]+:|$)",
            "resolution_status": r"RESOLUTION:\s*(.+?)(?=\n[A-Z]+:|$)",
            "user_satisfaction": r"SATISFACTION:\s*(.+?)(?=\n[A-Z]+:|$)",
            "key_issues": r"KEY_ISSUES:\s*(.+?)(?=\n[A-Z]+:|$)",
            "outcome": r"OUTCOME:\s*(.+?)(?=\n[A-Z]+:|$)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if key == "topics":
                    summary_data[key] = [t.strip() for t in value.split(",")]
                else:
                    summary_data[key] = value
            else:
                summary_data[key] = "unknown" if key != "topics" else []
        
        return summary_data
    
    def _create_fallback_summary(self, messages: List[Dict], session_info: Dict) -> Dict:
        """Create basic summary when LLM fails"""
        topics = []
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        
        # Extract basic topics from user messages
        for msg in user_messages:
            content = msg.get("content", "").lower()
            if "error" in content:
                topics.append("error resolution")
            if "property" in content:
                topics.append("property information")
            if any(word in content for word in ["how", "what", "define"]):
                topics.append("information request")
        
        return {
            "summary": f"Chat session with {len(messages)} messages covering general PropertyEngine topics",
            "topics": list(set(topics)) if topics else ["general inquiry"],
            "resolution_status": "unknown",
            "user_satisfaction": "unknown",
            "key_issues": "Summary generation failed",
            "outcome": "Session completed",
            "message_count": len(messages),
            "session_duration": self._calculate_session_duration(messages),
            "created_at": datetime.now().isoformat(),
            "summary_trigger": "fallback"
        }
    
    def _calculate_session_duration(self, messages: List[Dict]) -> Optional[int]:
        """Calculate session duration in seconds"""
        if len(messages) < 2:
            return None
        
        try:
            first_time = messages[0].get("timestamp")
            last_time = messages[-1].get("timestamp")
            
            if first_time and last_time:
                # Parse ISO format timestamps
                from datetime import datetime
                first_dt = datetime.fromisoformat(first_time.replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
                
                duration = (last_dt - first_dt).total_seconds()
                return int(duration)
                
        except Exception as e:
            logger.error(f"Failed to calculate session duration: {e}")
        
        return None
    
    def _determine_summary_trigger(self, messages: List[Dict]) -> str:
        """Determine why the summary was triggered"""
        message_count = len(messages)
        
        if message_count >= 10:
            return "message_limit"
        elif message_count >= 5:
            return "regular_interval"
        else:
            return "session_end"

# Global summarizer instance
chat_summarizer = ChatSummarizer()
