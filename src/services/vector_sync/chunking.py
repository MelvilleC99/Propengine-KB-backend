"""
Smart Chunking Strategies for KB Entries

This module handles intelligent chunking of different entry types:
- DEFINITION: Single chunk (always short, one concept)
- ERROR: Single chunk (usually short, one problem)
- HOW_TO: Context-aware chunks by heading (overview, prerequisites, steps, issues)
- WORKFLOW: Context-aware chunks by heading (same as how_to)
"""

from typing import Dict, Any, List, Union
import logging

logger = logging.getLogger(__name__)


def _to_string(value: Union[str, list, dict, None]) -> str:
    """
    Convert any value to string for content building.
    Handles lists, dicts, and None gracefully.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        # Check if list contains dicts (like steps)
        if value and isinstance(value[0], dict):
            # Format as numbered list
            formatted_items = []
            for i, item in enumerate(value, 1):
                if isinstance(item, dict):
                    # Extract relevant fields from step dicts
                    action = item.get('action', '')
                    if action:
                        formatted_items.append(f"{i}. {action}")
                else:
                    formatted_items.append(f"{i}. {str(item)}")
            return "\n".join(formatted_items)
        else:
            # Simple list - join with newlines
            return "\n".join(str(item) for item in value if item)
    if isinstance(value, dict):
        # Convert dict to readable format
        return "\n".join(f"{k}: {v}" for k, v in value.items() if v)
    return str(value)


class Chunk:
    """Represents a single chunk of content with metadata"""
    
    def __init__(
        self,
        content: str,
        chunk_index: int,
        total_chunks: int,
        section_type: str,
        parent_id: str,
        parent_title: str,
        metadata: Dict[str, Any],
        context: Dict[str, Any] = None
    ):
        self.content = content
        self.chunk_index = chunk_index
        self.total_chunks = total_chunks
        self.section_type = section_type
        self.parent_id = parent_id
        self.parent_title = parent_title
        self.metadata = metadata
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for storage"""
        return {
            "content": self.content,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "section_type": self.section_type,
            "parent_id": self.parent_id,
            "parent_title": self.parent_title,
            "metadata": self.metadata,
            "context": self.context
        }


def chunk_entry(entry: Dict[str, Any]) -> List[Chunk]:
    """
    Main entry point for chunking.
    Routes to appropriate chunking strategy based on entry type.
    
    Args:
        entry: KB entry dict with type, rawFormData, etc.
        
    Returns:
        List of Chunk objects
    """
    entry_type = entry.get("type", "")
    
    if entry_type == "definition":
        return chunk_definition(entry)
    elif entry_type == "error":
        return chunk_error(entry)
    elif entry_type in ["how_to", "workflow"]:
        return chunk_how_to(entry)
    else:
        logger.warning(f"Unknown entry type: {entry_type}, using single chunk")
        return chunk_single(entry)


def chunk_definition(entry: Dict[str, Any]) -> List[Chunk]:
    """
    Create single chunk for definition entries.
    Definitions are always short and represent one concept.
    
    Args:
        entry: Definition entry
        
    Returns:
        List with single chunk
    """
    # Use pre-built content from frontend
    content = entry.get("content", "")
    
    # Fallback: Build from rawFormData if content is missing (shouldn't happen)
    if not content:
        logger.warning(f"No content field found for definition {entry.get('id')}, building from rawFormData")
        raw_data = entry.get("rawFormData", {})
        parts = []
        
        if term := raw_data.get("term"):
            parts.append(f"Term: {_to_string(term)}")
        
        if definition := raw_data.get("definition"):
            parts.append(f"Definition: {_to_string(definition)}")
        
        if context := raw_data.get("context"):
            parts.append(f"Context: {_to_string(context)}")
        
        if examples := raw_data.get("examples"):
            parts.append(f"Examples: {_to_string(examples)}")
        
        content = "\n\n".join(parts)
    
    # Add title as header for context
    title = entry.get("title", "")
    if title and not content.startswith(title):
        content = f"{title}\n\n{content}"
    
    # Create single chunk
    chunk = Chunk(
        content=content,
        chunk_index=0,
        total_chunks=1,
        section_type="full",
        parent_id=entry.get("id"),
        parent_title=title or "Untitled",
        metadata={
            "entryType": "definition",
            "category": entry.get("category"),
            "userType": entry.get("metadata", {}).get("userType", "internal"),
            "product": entry.get("metadata", {}).get("product", "property_engine"),
            "tags": entry.get("metadata", {}).get("tags", []),
            "title": title or "Untitled",  # Add title to metadata
            "related_documents": entry.get("metadata", {}).get("related_documents", [])  # Add related docs
        }
    )
    
    logger.info(f"Created definition chunk with {len(content)} characters")
    
    return [chunk]


def chunk_error(entry: Dict[str, Any]) -> List[Chunk]:
    """
    Create single chunk for error entries.
    Errors are usually short and represent one problem + solution.
    
    Args:
        entry: Error entry
        
    Returns:
        List with single chunk
    """
    # Use pre-built content from frontend
    content = entry.get("content", "")
    
    # Fallback: Build from rawFormData if content is missing (shouldn't happen)
    if not content:
        logger.warning(f"No content field found for error {entry.get('id')}, building from rawFormData")
        raw_data = entry.get("rawFormData", {})
        parts = []
        
        if title := entry.get("title"):
            parts.append(f"Error: {_to_string(title)}")
        
        if error_code := raw_data.get("errorCode"):
            parts.append(f"Error Code: {_to_string(error_code)}")
        
        if description := raw_data.get("description"):
            parts.append(f"Description: {_to_string(description)}")
        
        if symptoms := raw_data.get("symptoms"):
            parts.append(f"Symptoms: {_to_string(symptoms)}")
        
        if solution := raw_data.get("solution"):
            parts.append(f"Solution: {_to_string(solution)}")
        
        if causes := raw_data.get("causes"):
            # Handle error causes specially - they have cause_description and solution
            causes_text = []
            for i, cause in enumerate(causes, 1):
                if isinstance(cause, dict):
                    cause_desc = cause.get("cause_description", "")
                    cause_solution = cause.get("solution", "")
                    if cause_desc:
                        causes_text.append(f"Cause {i}: {cause_desc}")
                    if cause_solution:
                        causes_text.append(f"Solution: {cause_solution}")
                else:
                    causes_text.append(f"Cause {i}: {str(cause)}")
            
            if causes_text:
                parts.append("Common Causes:\n" + "\n\n".join(causes_text))
        
        if prevention := raw_data.get("prevention"):
            parts.append(f"Prevention: {_to_string(prevention)}")
        
        content = "\n\n".join(parts)
    
    # Add title as header for context if not already there
    title = entry.get("title", "")
    if title and not content.startswith("Error:"):
        content = f"Error: {title}\n\n{content}"
    
    # Create single chunk
    chunk = Chunk(
        content=content,
        chunk_index=0,
        total_chunks=1,
        section_type="full",
        parent_id=entry.get("id"),
        parent_title=title or "Untitled",
        metadata={
            "entryType": "error",
            "category": entry.get("category"),
            "userType": entry.get("metadata", {}).get("userType", "internal"),
            "product": entry.get("metadata", {}).get("product", "property_engine"),
            "tags": entry.get("metadata", {}).get("tags", []),
            "title": title or "Untitled",  # Add title to metadata
            "related_documents": entry.get("metadata", {}).get("related_documents", [])  # Add related docs
        }
    )
    
    logger.info(f"Created error chunk with {len(content)} characters")
    
    return [chunk]


def chunk_how_to(entry: Dict[str, Any]) -> List[Chunk]:
    """
    Create context-aware chunks for how_to/workflow entries.
    
    For entries with pre-built content field:
    - Uses the content directly if it's reasonably sized (<2000 tokens)
    - Falls back to section-based chunking for very large content
    
    For entries without content field (legacy):
    - Chunks by heading sections: overview, prerequisites, steps, issues, tips
    
    Each chunk includes:
    - Main content for that section
    - Context about previous/next sections
    - Position information
    
    Args:
        entry: How-to or workflow entry
        
    Returns:
        List of chunks with contextual metadata
    """
    # Try to use pre-built content first
    content = entry.get("content", "")
    entry_id = entry.get("id")
    entry_title = entry.get("title", "Untitled")
    
    # If content exists and is reasonably sized, use it as a single chunk
    if content:
        # Rough token estimate (words * 1.3)
        estimated_tokens = len(content.split()) * 1.3
        
        if estimated_tokens < 2000:  # Single chunk for reasonable size
            logger.info(f"Using single chunk for how_to entry {entry_id} ({estimated_tokens:.0f} tokens)")
            
            # Add title as header if not already there
            # Check for "How to:" prefix, not exact title match
            if not content.startswith("How to:"):
                content = f"How to: {entry_title}\n\n{content}"
            
            chunk = Chunk(
                content=content,
                chunk_index=0,
                total_chunks=1,
                section_type="full",
                parent_id=entry_id,
                parent_title=entry_title,
                metadata={
                    "entryType": entry.get("type"),
                    "category": entry.get("category"),
                    "subcategory": entry.get("metadata", {}).get("subcategory"),
                    "userType": entry.get("metadata", {}).get("userType", "internal"),
                    "product": entry.get("metadata", {}).get("product", "property_engine"),
                    "tags": entry.get("metadata", {}).get("tags", []),
                    "title": entry_title,  # Add title to metadata
                    "related_documents": entry.get("metadata", {}).get("related_documents", [])  # Add related docs
                }
            )
            
            return [chunk]
        else:
            logger.info(f"Content too large ({estimated_tokens:.0f} tokens), falling back to section-based chunking")
    
    # Fallback: Build sections from rawFormData for large content or missing content field
    logger.warning(f"Building how_to chunks from rawFormData for entry {entry_id}")
    raw_data = entry.get("rawFormData", {})
    
    # Build sections
    sections = []
    
    # Section 1: Overview
    if overview := raw_data.get("overview"):
        sections.append({
            "name": "overview",
            "heading": "Overview",
            "content": _to_string(overview),
            "summary": _summarize(_to_string(overview))
        })
    
    # Section 2: Prerequisites
    if prerequisites := raw_data.get("prerequisites"):
        sections.append({
            "name": "prerequisites",
            "heading": "Prerequisites",
            "content": _to_string(prerequisites),
            "summary": _summarize(_to_string(prerequisites))
        })
    
    # Section 3: Steps
    if steps := raw_data.get("steps"):
        sections.append({
            "name": "steps",
            "heading": "Steps",
            "content": _to_string(steps),
            "summary": "Step-by-step instructions to complete the task"
        })
    
    # Section 4: Common Issues
    if issues := raw_data.get("commonIssues"):
        sections.append({
            "name": "issues",
            "heading": "Common Issues",
            "content": _to_string(issues),
            "summary": "Troubleshooting common problems"
        })
    
    # Section 5: Tips
    if tips := raw_data.get("tips"):
        sections.append({
            "name": "tips",
            "heading": "Tips & Best Practices",
            "content": _to_string(tips),
            "summary": "Tips and best practices"
        })
    
    # If no sections found, create single chunk
    if not sections:
        return chunk_single(entry)
    
    # Create chunks with context
    chunks = []
    total_chunks = len(sections)
    
    for i, section in enumerate(sections):
        # Build content with heading
        content_parts = [
            f"{section['heading']} for {entry_title}:",
            section['content']
        ]
        content = "\n\n".join(content_parts)
        
        # Build context
        context = {
            "position": f"{i+1} of {total_chunks}",
            "section_name": section['name']
        }
        
        # Add previous section context
        if i > 0:
            context["previous_section"] = sections[i-1]['name']
            context["previous_summary"] = sections[i-1]['summary']
        
        # Add next section context
        if i < len(sections) - 1:
            context["next_section"] = sections[i+1]['name']
            context["next_summary"] = sections[i+1]['summary']
        
        # Add related chunk IDs for easy navigation
        related_chunks = [
            f"{entry_id}_chunk_{j}" 
            for j in range(total_chunks) 
            if j != i
        ]
        context["related_chunks"] = related_chunks
        
        # Create chunk
        chunk = Chunk(
            content=content,
            chunk_index=i,
            total_chunks=total_chunks,
            section_type=section['name'],
            parent_id=entry_id,
            parent_title=entry_title,
            metadata={
                "entryType": entry.get("type"),
                "category": entry.get("category"),
                "subcategory": entry.get("metadata", {}).get("subcategory"),
                "userType": entry.get("metadata", {}).get("userType", "internal"),
                "product": entry.get("metadata", {}).get("product", "property_engine"),
                "tags": entry.get("metadata", {}).get("tags", []),
                "section": section['name'],
                "title": entry_title,  # Add title to metadata
                "related_documents": entry.get("metadata", {}).get("related_documents", [])  # Add related docs
            },
            context=context
        )
        
        chunks.append(chunk)
    
    logger.info(f"Created {len(chunks)} chunks for entry {entry_id}")
    
    return chunks


def chunk_single(entry: Dict[str, Any]) -> List[Chunk]:
    """
    Fallback: Create single chunk for entries without clear structure.
    
    Args:
        entry: KB entry
        
    Returns:
        List with single chunk
    """
    # Try pre-built content first
    content = entry.get("content", "")
    
    # Fallback: Combine from rawFormData if no content field
    if not content:
        logger.warning(f"No content field found for entry {entry.get('id')}, building from rawFormData")
        parts = []
        
        if title := entry.get("title"):
            parts.append(title)
        
        raw_data = entry.get("rawFormData", {})
        
        for key, value in raw_data.items():
            if value and isinstance(value, str):
                parts.append(value)
        
        content = "\n\n".join(parts)
    
    # Add title as header if not already there
    title = entry.get("title", "")
    if title and not content.startswith(title):
        content = f"{title}\n\n{content}"
    
    chunk = Chunk(
        content=content,
        chunk_index=0,
        total_chunks=1,
        section_type="full",
        parent_id=entry.get("id"),
        parent_title=title or "Untitled",
        metadata={
            "entryType": entry.get("type", "unknown"),
            "category": entry.get("category"),
            "userType": entry.get("metadata", {}).get("userType", "internal"),
            "product": entry.get("metadata", {}).get("product", "property_engine"),
            "tags": entry.get("metadata", {}).get("tags", []),
            "title": title or "Untitled",  # Add title to metadata
            "related_documents": entry.get("metadata", {}).get("related_documents", [])  # Add related docs
        }
    )
    
    logger.info(f"Created single chunk with {len(content)} characters")
    
    return [chunk]


def _summarize(text: str, max_length: int = 100) -> str:
    """
    Create a brief summary of text for context.
    
    Args:
        text: Text to summarize
        max_length: Maximum length of summary
        
    Returns:
        Summary string
    """
    if not text:
        return ""
    
    # Simple truncation with ellipsis
    if len(text) <= max_length:
        return text
    
    # Find last sentence boundary before max_length
    truncated = text[:max_length]
    last_period = truncated.rfind('.')
    last_exclaim = truncated.rfind('!')
    last_question = truncated.rfind('?')
    
    boundary = max(last_period, last_exclaim, last_question)
    
    if boundary > max_length // 2:  # Use boundary if it's not too early
        return text[:boundary + 1]
    else:
        return truncated.rstrip() + "..."
