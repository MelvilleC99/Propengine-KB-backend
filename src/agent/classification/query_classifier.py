"""Query Classification Module

Classifies user queries to determine routing and search strategy.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class QueryClassifier:
    """Classifies user queries to determine routing"""
    
    PATTERNS = {
        "greeting": [
            # Only match standalone greetings (nothing substantial after)
            r"^(hi|hello|hey|good morning|good afternoon|good evening)[\s\.,!?]*$",
            r"^(hi|hello|hey)[\s\.,!?]*(there|everyone|team)?[\s\.,!?]*$"
        ],
        "error": [
            r"\berror\s*\d+\b",  # Match "error 405", "error405", etc.
            r"\berror\b",
            r"\bissue\b",
            r"\bproblem\b",
            r"\bfail(ed|ing|ure)?\b",
            r"\bnot work(ing)?\b",
            # Troubleshooting patterns - common support queries
            r"\bcan'?t\s+(see|find|view|access|open|load|sync|log\s*in)\b",
            r"\b(not\s+showing|not\s+visible|not\s+appearing|not\s+loading|not\s+syncing)\b",
            r"\b(missing|disappeared|gone|lost)\b",
            r"\bwhy\s+(is|are|can'?t|won'?t|doesn'?t|isn'?t|don'?t)\b",
            r"\bunable\s+to\b",
            r"\b(stuck|frozen|blank|empty)\b"
        ],
        "definition": [
            r"\bwhat (is|are|does|do)\b(?!.*\berror\b)",
            r"\bdefine\b",
            r"\bmeaning of\b",
            r"\bmean\b(?!.*\berror\b)",
            r"\btell me about\b",
            r"\bexplain\b(?!.*\berror\b)"
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
        """
        Classify query and return (type, confidence)
        
        Args:
            query: User's query string
            
        Returns:
            Tuple of (query_type, confidence_score)
            
        Example:
            >>> QueryClassifier.classify("What is an API key?")
            ('definition', 0.8)
        """
        query_lower = query.lower().strip()
        
        # Check patterns
        for query_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.debug(f"Query classified as '{query_type}' (pattern: '{pattern}')")
                    return query_type, 0.8
        
        # Default to general for unknown queries (no entryType filter applied)
        logger.debug(f"Query defaulted to 'general' (no pattern match)")
        return "general", 0.5
