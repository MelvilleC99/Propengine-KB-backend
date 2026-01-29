"""
Token Usage and Cost Tracking for LLM API Calls

Tracks token consumption and calculates costs using YAML pricing.
Updated to use Pydantic models.
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
from ..models.token_usage import TokenUsage
from ..models.cost_breakdown import CostBreakdown
from .cost_calculator import cost_calculator

logger = logging.getLogger(__name__)


class TokenTracker:
    """
    Tracks token usage and calculates costs using YAML pricing
    
    Usage:
        from src.analytics.tracking import token_tracker
        
        # After LLM call
        usage = token_tracker.track_chat_usage(
            response=llm_response,
            model="gpt-4-turbo",
            session_id=session_id,
            operation="response_generation"
        )
    """
    
    def __init__(self):
        """Initialize token tracker"""
        self.session_costs: Dict[str, Dict] = {}  # session_id -> cost breakdown
        logger.info("✅ Token tracker initialized (Pydantic)")
    
    def track_chat_usage(
        self,
        response: Any,
        model: str,
        session_id: Optional[str] = None,
        operation: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Track token usage from chat LLM response
        
        Args:
            response: LLM response object (from langchain or direct API)
            model: Model name (e.g., "gpt-4-turbo")
            session_id: Optional session identifier
            operation: Optional operation name (e.g., "response_generation")
            
        Returns:
            Usage dict or None if usage data not available
        """
        try:
            # Extract usage from response
            usage_metadata = self._extract_usage_metadata(response)
            
            if not usage_metadata:
                logger.warning("⚠️ No usage metadata found in LLM response")
                return None
            
            # Extract token counts
            input_tokens = usage_metadata.get('input_tokens', 0) or usage_metadata.get('prompt_tokens', 0)
            output_tokens = usage_metadata.get('output_tokens', 0) or usage_metadata.get('completion_tokens', 0)
            total_tokens = usage_metadata.get('total_tokens', 0) or (input_tokens + output_tokens)
            
            # Calculate cost using YAML pricing
            cost_data = cost_calculator.calculate_chat_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model
            )
            
            # Create Pydantic usage record
            usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                model=model,
                timestamp=datetime.now().isoformat(),
                cost=cost_data["total_cost"],
                session_id=session_id,
                operation=operation
            )
            
            # Update session costs
            if session_id:
                if session_id not in self.session_costs:
                    self.session_costs[session_id] = {}
                
                if operation not in self.session_costs[session_id]:
                    self.session_costs[session_id][operation] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost": 0.0
                    }
                
                self.session_costs[session_id][operation]["input_tokens"] += input_tokens
                self.session_costs[session_id][operation]["output_tokens"] += output_tokens
                self.session_costs[session_id][operation]["cost"] += cost_data["total_cost"]
            
            # Log the usage
            logger.info(
                f"💰 {operation or 'LLM'} | "
                f"Input: {input_tokens} | "
                f"Output: {output_tokens} | "
                f"Cost: ${cost_data['total_cost']:.6f}"
            )
            
            return usage.model_dump()
            
        except Exception as e:
            logger.error(f"❌ Error tracking token usage: {e}")
            return None
    
    def track_embedding_usage(
        self,
        tokens: int,
        model: str,
        session_id: Optional[str] = None,
        operation: str = "embedding"
    ) -> Optional[Dict]:
        """
        Track token usage for embedding generation
        
        Args:
            tokens: Number of tokens used
            model: Model name (e.g., "text-embedding-3-small")
            session_id: Optional session identifier
            operation: Operation name (default: "embedding")
            
        Returns:
            Usage dict
        """
        try:
            # Calculate cost using YAML pricing
            cost = cost_calculator.calculate_embedding_cost(
                tokens=tokens,
                model=model
            )
            
            # Create usage record (for embeddings, input=output=total)
            usage_dict = {
                "tokens": tokens,
                "model": model,
                "cost": cost,
                "operation": operation,
                "timestamp": datetime.now().isoformat()
            }
            
            # Update session costs
            if session_id:
                if session_id not in self.session_costs:
                    self.session_costs[session_id] = {}
                
                if operation not in self.session_costs[session_id]:
                    self.session_costs[session_id][operation] = {
                        "tokens": 0,
                        "cost": 0.0
                    }
                
                self.session_costs[session_id][operation]["tokens"] += tokens
                self.session_costs[session_id][operation]["cost"] += cost
            
            # Log the usage
            logger.info(
                f"💰 {operation} | "
                f"Tokens: {tokens} | "
                f"Cost: ${cost:.6f}"
            )
            
            return usage_dict
            
        except Exception as e:
            logger.error(f"❌ Error tracking embedding usage: {e}")
            return None
    
    def get_cost_breakdown_for_session(self, session_id: str) -> CostBreakdown:
        """
        Get cost breakdown for a session as Pydantic model
        
        Args:
            session_id: Session identifier
            
        Returns:
            CostBreakdown Pydantic model
        """
        if session_id not in self.session_costs:
            return CostBreakdown()
        
        costs = self.session_costs[session_id]
        
        # Extract costs by operation
        embedding_cost = costs.get("embedding", {}).get("cost", 0.0)
        query_building_cost = costs.get("query_enhancement", {}).get("cost", 0.0)
        response_generation_cost = costs.get("response_generation", {}).get("cost", 0.0)
        
        # Extract tokens
        embedding_tokens = costs.get("embedding", {}).get("tokens", 0)
        query_input = costs.get("query_enhancement", {}).get("input_tokens", 0)
        query_output = costs.get("query_enhancement", {}).get("output_tokens", 0)
        response_input = costs.get("response_generation", {}).get("input_tokens", 0)
        response_output = costs.get("response_generation", {}).get("output_tokens", 0)
        
        total_cost = embedding_cost + query_building_cost + response_generation_cost
        total_tokens = embedding_tokens + query_input + query_output + response_input + response_output
        
        return CostBreakdown(
            embedding_cost=embedding_cost,
            query_building_cost=query_building_cost,
            response_generation_cost=response_generation_cost,
            total_cost=total_cost,
            embedding_tokens=embedding_tokens,
            query_building_input_tokens=query_input,
            query_building_output_tokens=query_output,
            response_input_tokens=response_input,
            response_output_tokens=response_output,
            total_tokens=total_tokens
        )
    
    def _extract_usage_metadata(self, response: Any) -> Optional[Dict]:
        """Extract usage metadata from various response formats"""
        try:
            # Try different ways to get usage (depends on LLM library)
            if hasattr(response, 'usage_metadata'):
                return response.usage_metadata
            elif hasattr(response, 'response_metadata'):
                return response.response_metadata.get('token_usage')
            elif hasattr(response, 'usage'):
                return response.usage
            return None
        except:
            return None
    
    def get_session_costs(self, session_id: str) -> Optional[Dict]:
        """
        Get cost breakdown for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict with cost breakdown by operation
        """
        if session_id not in self.session_costs:
            return None
        
        costs = self.session_costs[session_id]
        
        # Calculate totals
        total_cost = sum(op.get("cost", 0.0) for op in costs.values())
        total_tokens = sum(
            op.get("total_tokens", 0) or (op.get("input_tokens", 0) + op.get("output_tokens", 0)) or op.get("tokens", 0)
            for op in costs.values()
        )
        
        return {
            "operations": costs,
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens
        }
    
    def clear_session(self, session_id: str):
        """Clear token tracking for a session"""
        if session_id in self.session_costs:
            del self.session_costs[session_id]
            logger.debug(f"Cleared token tracking for session: {session_id}")


# Global token tracker instance
token_tracker = TokenTracker()
