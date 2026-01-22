"""YAML Prompt Loader

Loads and manages prompts from YAML files.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PromptLoader:
    """Loads and caches YAML prompts"""
    
    def __init__(self):
        self.prompts_dir = Path(__file__).parent / "yaml"
        self._cache = {}
        logger.info(f"PromptLoader initialized. Prompts directory: {self.prompts_dir}")
    
    def load(self, prompt_name: str, **variables) -> str:
        """
        Load a YAML prompt file and optionally format with variables
        
        Args:
            prompt_name: Name without .yaml (e.g., 'query_builder')
            **variables: Variables to format into template
            
        Returns:
            Formatted prompt string
            
        Example:
            loader.load('query_builder', query="hello", context="none")
        """
        # Load from cache or file
        if prompt_name not in self._cache:
            self._load_from_file(prompt_name)
        
        prompt = self._cache[prompt_name]
        
        # Format with variables if provided
        if variables:
            try:
                prompt = prompt.format(**variables)
            except KeyError as e:
                logger.warning(f"Missing variable in prompt template: {e}")
        
        return prompt
    
    def _load_from_file(self, prompt_name: str):
        """Load YAML file and build prompt string"""
        file_path = self.prompts_dir / f"{prompt_name}.yaml"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        logger.debug(f"Loading prompt: {prompt_name}")
        
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Build prompt from YAML structure
        prompt = self._build_prompt(data)
        self._cache[prompt_name] = prompt
        
        logger.info(f"✅ Loaded prompt: {prompt_name} ({len(prompt)} chars)")
    
    def _build_prompt(self, data: Dict) -> str:
        """Convert YAML structure to prompt string"""
        sections = []
        
        # Role
        if 'role' in data:
            sections.append(f"Role: {data['role']}")
        
        # Identity
        if 'identity' in data:
            sections.append(f"\n{data['identity']}")
        
        # Task
        if 'task' in data:
            sections.append(f"\nTask: {data['task']}")
        
        # Instructions
        if 'instructions' in data:
            sections.append(f"\nInstructions:\n{data['instructions']}")
        
        # Rules
        if 'rules' in data:
            rules_text = "\n".join(f"- {rule}" for rule in data['rules'])
            sections.append(f"\nRules:\n{rules_text}")
        
        # Tone
        if 'tone' in data:
            sections.append(f"\nTone: {data['tone']}")
        
        # Forbidden
        if 'forbidden' in data:
            forbidden_text = "\n".join(f"- {item}" for item in data['forbidden'])
            sections.append(f"\nForbidden:\n{forbidden_text}")
        
        # Output format
        if 'output_format' in data:
            sections.append(f"\nOutput Format: {data['output_format']}")
        
        # Schema
        if 'schema' in data:
            schema_text = yaml.dump(data['schema'], default_flow_style=False)
            sections.append(f"\nSchema:\n{schema_text}")
        
        # Examples
        if 'examples' in data:
            examples_text = self._format_examples(data['examples'])
            sections.append(f"\nExamples:\n{examples_text}")
        
        # Template (usually at the end)
        if 'template' in data:
            sections.append(f"\n{data['template']}")
        
        return "\n".join(sections)
    
    def _format_examples(self, examples: list) -> str:
        """Format examples section"""
        formatted = []
        for i, ex in enumerate(examples, 1):
            formatted.append(f"\nExample {i}:")
            if 'input' in ex:
                formatted.append(f"Input: {ex['input']}")
            if 'output' in ex:
                formatted.append(f"Output:\n{ex['output']}")
            if 'good_response' in ex:
                formatted.append(f"Good: {ex['good_response']}")
            if 'bad_response' in ex:
                formatted.append(f"Bad: {ex['bad_response']}")
        return "\n".join(formatted)
    
    def reload(self):
        """Clear cache and reload all prompts"""
        self._cache.clear()
        logger.info("Prompt cache cleared")


# Global instance
prompt_loader = PromptLoader()
