"""
Token Usage Model - Pydantic

Tracks token usage for individual LLM calls
"""

from pydantic import BaseModel, Field
from typing import Optional


class TokenUsage(BaseModel):
    """Token usage data for a single LLM call"""
    
    input_tokens: int = Field(ge=0, description="Number of input tokens")
    output_tokens: int = Field(ge=0, description="Number of output tokens")
    total_tokens: int = Field(ge=0, description="Total tokens (input + output)")
    model: str = Field(description="Model name (e.g., 'gpt-4-turbo')")
    timestamp: str = Field(description="ISO timestamp of the call")
    cost: float = Field(ge=0.0, description="Cost in USD")
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier"
    )
    operation: Optional[str] = Field(
        default=None,
        description="Operation name (e.g., 'response_generation', 'query_enhancement')"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "input_tokens": 800,
                "output_tokens": 50,
                "total_tokens": 850,
                "model": "gpt-4-turbo",
                "timestamp": "2026-01-29T14:30:00Z",
                "cost": 0.0005,
                "session_id": "abc123",
                "operation": "response_generation"
            }
        }
    }
