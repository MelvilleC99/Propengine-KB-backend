"""
Cost Calculator for LLM Token Usage

Calculates costs based on YAML pricing configuration.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculate costs from token usage using YAML pricing"""
    
    def __init__(self):
        """Load pricing from YAML file"""
        self.pricing = self._load_pricing()
        logger.info("✅ Cost calculator initialized with YAML pricing")
    
    def _load_pricing(self) -> Dict:
        """Load pricing configuration from YAML"""
        try:
            # Path adjusted for new location
            config_path = Path(__file__).parent.parent.parent / "config" / "model_pricing.yaml"
            
            with open(config_path, 'r') as f:
                pricing = yaml.safe_load(f)
            
            logger.info(f"📊 Loaded pricing for {len(pricing.get('chat_models', {}))} chat models and {len(pricing.get('embedding_models', {}))} embedding models")
            return pricing
            
        except Exception as e:
            logger.error(f"❌ Failed to load pricing YAML: {e}")
            # Return default pricing
            return {
                "default": {
                    "embedding_cost_per_1m": 0.02,
                    "chat_input_cost_per_1m": 0.50,
                    "chat_output_cost_per_1m": 1.50
                }
            }
    
    def calculate_embedding_cost(self, tokens: int, model: str) -> float:
        """
        Calculate cost for embedding tokens
        
        Args:
            tokens: Number of tokens
            model: Model name (e.g., "text-embedding-3-small")
            
        Returns:
            Cost in USD
        """
        try:
            # Get pricing for specific model
            embedding_models = self.pricing.get("embedding_models", {})
            model_pricing = embedding_models.get(model)
            
            if not model_pricing:
                logger.warning(f"⚠️ No pricing found for embedding model: {model}, using default")
                cost_per_1m = self.pricing.get("default", {}).get("embedding_cost_per_1m", 0.02)
            else:
                cost_per_1m = model_pricing.get("cost_per_1m_tokens", 0.02)
            
            # Calculate cost (tokens / 1M * cost_per_1M)
            cost = (tokens / 1_000_000) * cost_per_1m
            
            return round(cost, 8)  # Round to 8 decimal places
            
        except Exception as e:
            logger.error(f"❌ Error calculating embedding cost: {e}")
            return 0.0
    
    def calculate_chat_cost(
        self, 
        input_tokens: int, 
        output_tokens: int, 
        model: str
    ) -> Dict[str, float]:
        """
        Calculate cost for chat model tokens
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name (e.g., "gpt-4-turbo")
            
        Returns:
            Dict with input_cost, output_cost, total_cost
        """
        try:
            # Get pricing for specific model
            chat_models = self.pricing.get("chat_models", {})
            model_pricing = chat_models.get(model)
            
            if not model_pricing:
                logger.warning(f"⚠️ No pricing found for chat model: {model}, using default")
                defaults = self.pricing.get("default", {})
                input_cost_per_1m = defaults.get("chat_input_cost_per_1m", 0.50)
                output_cost_per_1m = defaults.get("chat_output_cost_per_1m", 1.50)
            else:
                input_cost_per_1m = model_pricing.get("input_cost_per_1m", 0.50)
                output_cost_per_1m = model_pricing.get("output_cost_per_1m", 1.50)
            
            # Calculate costs
            input_cost = (input_tokens / 1_000_000) * input_cost_per_1m
            output_cost = (output_tokens / 1_000_000) * output_cost_per_1m
            total_cost = input_cost + output_cost
            
            return {
                "input_cost": round(input_cost, 8),
                "output_cost": round(output_cost, 8),
                "total_cost": round(total_cost, 8)
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating chat cost: {e}")
            return {
                "input_cost": 0.0,
                "output_cost": 0.0,
                "total_cost": 0.0
            }


# Global cost calculator instance
cost_calculator = CostCalculator()
