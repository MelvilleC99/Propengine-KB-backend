"""
Cost Breakdown Model - Pydantic

Tracks costs and token usage for query execution
"""

from pydantic import BaseModel, Field


class CostBreakdown(BaseModel):
    """Cost breakdown for query execution with token counts"""
    
    # Costs (USD)
    embedding_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost for generating embeddings"
    )
    query_building_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost for query enhancement (if LLM used)"
    )
    response_generation_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost for LLM response generation"
    )
    total_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Total cost for query"
    )
    
    # Token counts
    embedding_tokens: int = Field(
        default=0,
        ge=0,
        description="Tokens used for embedding"
    )
    query_building_input_tokens: int = Field(
        default=0,
        ge=0,
        description="Input tokens for query building"
    )
    query_building_output_tokens: int = Field(
        default=0,
        ge=0,
        description="Output tokens for query building"
    )
    response_input_tokens: int = Field(
        default=0,
        ge=0,
        description="Input tokens for response generation"
    )
    response_output_tokens: int = Field(
        default=0,
        ge=0,
        description="Output tokens for response generation"
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total tokens used"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "embedding_cost": 0.0001,
                "query_building_cost": 0.0,
                "response_generation_cost": 0.0005,
                "total_cost": 0.0006,
                "embedding_tokens": 100,
                "response_input_tokens": 800,
                "response_output_tokens": 50,
                "total_tokens": 950
            }
        }
    }
