"""
Document Chunking - Chunking strategies for uploaded documents

This module handles chunking of document-based KB entries:
- Chunks by sections identified during document analysis
- Maintains parent-child relationships like template chunking
- Preserves context (prev/next section summaries)

Separate from chunking.py to avoid bloating that file.
"""

from typing import Dict, Any, List
import logging

# Import Chunk class from main chunking module for consistency
from .chunking import Chunk

logger = logging.getLogger(__name__)


def chunk_document(entry: Dict[str, Any]) -> List[Chunk]:
    """
    Create context-aware chunks for uploaded document entries.
    
    Similar to chunk_how_to but handles arbitrary sections from documents.
    Each section becomes a chunk with context about surrounding sections.
    Also includes steps from rawFormData for how_to entries.
    
    Args:
        entry: KB entry dict with rawFormData containing sections
        
    Returns:
        List of Chunk objects ready for vector storage
    """
    raw_data = entry.get("rawFormData", {})
    entry_id = entry.get("id")
    entry_title = entry.get("title", "Untitled")
    
    # Get sections from rawFormData
    sections = raw_data.get("sections", [])
    
    # Get steps if available (for how_to entries)
    steps = raw_data.get("steps", [])
    
    if not sections:
        # Fallback: create single chunk from content
        logger.warning(f"No sections found for document {entry_id}, creating single chunk")
        return _chunk_single_document(entry)
    
    # If we have many steps, chunk by steps instead of sections
    # This gives better granularity for searching
    if len(steps) > 3:
        return _chunk_by_steps(entry, sections, steps)
    
    # Build chunks from sections
    chunks = []
    total_chunks = len(sections)
    
    for i, section in enumerate(sections):
        # Build content with heading context
        heading = section.get("heading", f"Section {i+1}")
        content = section.get("content", "")
        section_type = section.get("section_type", "details")
        summary = section.get("summary", "")
        
        # Format content with heading
        content_parts = [
            f"{heading} - {entry_title}:",
            content
        ]
        chunk_content = "\n\n".join(content_parts)
        
        # Build context (prev/next section info)
        context = {
            "position": f"{i+1} of {total_chunks}",
            "section_name": heading,
            "section_type": section_type
        }
        
        # Add previous section context
        if i > 0:
            prev_section = sections[i-1]
            context["previous_section"] = prev_section.get("heading", "")
            context["previous_summary"] = prev_section.get("summary", "")[:200]
        
        # Add next section context
        if i < len(sections) - 1:
            next_section = sections[i+1]
            context["next_section"] = next_section.get("heading", "")
            context["next_summary"] = next_section.get("summary", "")[:200]
        
        # Add related chunk IDs for navigation
        related_chunks = [
            f"{entry_id}_chunk_{j}" 
            for j in range(total_chunks) 
            if j != i
        ]
        context["related_chunks"] = related_chunks
        
        # Create chunk
        chunk = Chunk(
            content=chunk_content,
            chunk_index=i,
            total_chunks=total_chunks,
            section_type=section_type,
            parent_id=entry_id,
            parent_title=entry_title,
            metadata={
                # Required fields for search compatibility (same as manual entries)
                "title": entry_title,
                "type": entry.get("type", "how_to"),
                "entryType": entry.get("type", "how_to"),
                "category": entry.get("category"),
                "subcategory": entry.get("metadata", {}).get("subcategory"),
                "userType": entry.get("metadata", {}).get("userType", "internal"),
                "product": entry.get("metadata", {}).get("product", "property_engine"),
                "tags": entry.get("metadata", {}).get("tags", []),
                "section": heading,
                "section_type": section_type,
                # Document-specific metadata
                "source": "upload",
                "original_filename": entry.get("metadata", {}).get("original_filename"),
            },
            context=context
        )
        
        chunks.append(chunk)
    
    logger.info(f"📄 Created {len(chunks)} chunks for document {entry_id}")
    
    return chunks


def chunk_large_document(entry: Dict[str, Any], max_chunk_tokens: int = 800) -> List[Chunk]:
    """
    Chunk large documents that have sections exceeding token limits.
    
    For very large sections, this will split them into smaller chunks
    while maintaining section context.
    
    Args:
        entry: KB entry dict
        max_chunk_tokens: Maximum tokens per chunk (rough estimate: 1 token ≈ 4 chars)
        
    Returns:
        List of Chunk objects
    """
    raw_data = entry.get("rawFormData", {})
    entry_id = entry.get("id")
    entry_title = entry.get("title", "Untitled")
    
    sections = raw_data.get("sections", [])
    max_chars = max_chunk_tokens * 4  # Rough token to char conversion
    
    if not sections:
        return _chunk_single_document(entry)
    
    # First pass: split large sections
    expanded_sections = []
    for section in sections:
        content = section.get("content", "")
        heading = section.get("heading", "Section")
        
        if len(content) > max_chars:
            # Split this section into sub-chunks
            sub_sections = _split_large_section(section, max_chars)
            expanded_sections.extend(sub_sections)
        else:
            expanded_sections.append(section)
    
    # Now chunk the expanded sections
    chunks = []
    total_chunks = len(expanded_sections)
    
    for i, section in enumerate(expanded_sections):
        heading = section.get("heading", f"Section {i+1}")
        content = section.get("content", "")
        section_type = section.get("section_type", "details")
        is_continuation = section.get("is_continuation", False)
        
        # Adjust heading for continuations
        if is_continuation:
            chunk_heading = f"{heading} (continued)"
        else:
            chunk_heading = heading
        
        content_parts = [
            f"{chunk_heading} - {entry_title}:",
            content
        ]
        chunk_content = "\n\n".join(content_parts)
        
        # Build context
        context = {
            "position": f"{i+1} of {total_chunks}",
            "section_name": heading,
            "section_type": section_type,
            "is_continuation": is_continuation
        }
        
        if i > 0:
            prev_section = expanded_sections[i-1]
            context["previous_section"] = prev_section.get("heading", "")
            context["previous_summary"] = prev_section.get("summary", "")[:200]
        
        if i < len(expanded_sections) - 1:
            next_section = expanded_sections[i+1]
            context["next_section"] = next_section.get("heading", "")
            context["next_summary"] = next_section.get("summary", "")[:200]
        
        context["related_chunks"] = [
            f"{entry_id}_chunk_{j}" 
            for j in range(total_chunks) 
            if j != i
        ]
        
        chunk = Chunk(
            content=chunk_content,
            chunk_index=i,
            total_chunks=total_chunks,
            section_type=section_type,
            parent_id=entry_id,
            parent_title=entry_title,
            metadata={
                # Required fields for search compatibility (same as manual entries)
                "title": entry_title,
                "type": entry.get("type", "how_to"),
                "entryType": entry.get("type", "how_to"),
                "category": entry.get("category"),
                "subcategory": entry.get("metadata", {}).get("subcategory"),
                "userType": entry.get("metadata", {}).get("userType", "internal"),
                "product": entry.get("metadata", {}).get("product", "property_engine"),
                "tags": entry.get("metadata", {}).get("tags", []),
                "section": heading,
                "section_type": section_type,
                "source": "upload",
                "original_filename": entry.get("metadata", {}).get("original_filename"),
                "is_continuation": is_continuation
            },
            context=context
        )
        
        chunks.append(chunk)
    
    logger.info(f"📄 Created {len(chunks)} chunks for large document {entry_id}")
    
    return chunks


def _split_large_section(section: Dict[str, Any], max_chars: int) -> List[Dict[str, Any]]:
    """
    Split a large section into smaller sub-sections.
    
    Tries to split at paragraph boundaries for cleaner chunks.
    """
    content = section.get("content", "")
    heading = section.get("heading", "Section")
    section_type = section.get("section_type", "details")
    summary = section.get("summary", "")
    
    # Split by paragraphs
    paragraphs = content.split("\n\n")
    
    sub_sections = []
    current_content = []
    current_length = 0
    part_num = 1
    
    for para in paragraphs:
        para_length = len(para)
        
        if current_length + para_length > max_chars and current_content:
            # Save current chunk and start new one
            sub_sections.append({
                "heading": heading,
                "content": "\n\n".join(current_content),
                "section_type": section_type,
                "summary": summary if part_num == 1 else f"Continuation of {heading}",
                "is_continuation": part_num > 1
            })
            current_content = [para]
            current_length = para_length
            part_num += 1
        else:
            current_content.append(para)
            current_length += para_length
    
    # Don't forget last chunk
    if current_content:
        sub_sections.append({
            "heading": heading,
            "content": "\n\n".join(current_content),
            "section_type": section_type,
            "summary": summary if part_num == 1 else f"Continuation of {heading}",
            "is_continuation": part_num > 1
        })
    
    return sub_sections


def _chunk_single_document(entry: Dict[str, Any]) -> List[Chunk]:
    """
    Fallback: Create single chunk for documents without sections.
    """
    entry_id = entry.get("id")
    entry_title = entry.get("title", "Untitled")
    
    # Get content from various possible sources
    content = entry.get("content", "")
    if not content:
        raw_data = entry.get("rawFormData", {})
        content = raw_data.get("overview", "") or str(raw_data)
    
    chunk = Chunk(
        content=content,
        chunk_index=0,
        total_chunks=1,
        section_type="full",
        parent_id=entry_id,
        parent_title=entry_title,
        metadata={
            # Required fields for search compatibility (same as manual entries)
            "title": entry_title,
            "type": entry.get("type", "how_to"),
            "entryType": entry.get("type", "how_to"),
            "category": entry.get("category"),
            "userType": entry.get("metadata", {}).get("userType", "internal"),
            "product": entry.get("metadata", {}).get("product", "property_engine"),
            "tags": entry.get("metadata", {}).get("tags", []),
            "source": "upload",
            "original_filename": entry.get("metadata", {}).get("original_filename"),
        }
    )
    
    return [chunk]


def _chunk_by_steps(entry: Dict[str, Any], sections: List[Dict], steps: List[Dict]) -> List[Chunk]:
    """
    Chunk document by steps for better granularity.
    Groups 3-4 steps per chunk to keep chunks meaningful but searchable.
    
    Args:
        entry: KB entry dict
        sections: List of section dicts
        steps: List of step dicts with 'action' key
        
    Returns:
        List of Chunk objects
    """
    entry_id = entry.get("id")
    entry_title = entry.get("title", "Untitled")
    
    # Get overview from first section or rawFormData
    overview = ""
    if sections and sections[0].get("section_type") == "overview":
        overview = sections[0].get("content", "")
    else:
        overview = entry.get("rawFormData", {}).get("overview", "")
    
    chunks = []
    
    # First chunk: Overview
    if overview:
        chunks.append(Chunk(
            content=f"{entry_title} - Overview:\n\n{overview}",
            chunk_index=0,
            total_chunks=0,  # Will update after
            section_type="overview",
            parent_id=entry_id,
            parent_title=entry_title,
            metadata={
                "title": entry_title,
                "type": entry.get("type", "how_to"),
                "entryType": entry.get("type", "how_to"),
                "category": entry.get("category"),
                "subcategory": entry.get("metadata", {}).get("subcategory"),
                "userType": entry.get("metadata", {}).get("userType", "internal"),
                "product": entry.get("metadata", {}).get("product", "property_engine"),
                "tags": entry.get("metadata", {}).get("tags", []),
                "section": "Overview",
                "section_type": "overview",
                "source": "upload",
                "original_filename": entry.get("metadata", {}).get("original_filename"),
            }
        ))
    
    # Group steps into chunks of 3-4 steps each
    steps_per_chunk = 4
    step_groups = [steps[i:i + steps_per_chunk] for i in range(0, len(steps), steps_per_chunk)]
    
    for group_idx, step_group in enumerate(step_groups):
        # Build content for this chunk
        step_start = group_idx * steps_per_chunk + 1
        step_end = step_start + len(step_group) - 1
        
        content_parts = [f"{entry_title} - Steps {step_start}-{step_end}:"]
        
        for i, step in enumerate(step_group):
            step_num = step_start + i
            action = step.get("action", "")
            content_parts.append(f"\nStep {step_num}: {action}")
        
        chunk_content = "\n".join(content_parts)
        
        # Context about previous/next steps
        context = {
            "position": f"Steps {step_start}-{step_end} of {len(steps)}",
            "section_name": f"Steps {step_start}-{step_end}",
            "section_type": "steps"
        }
        
        if group_idx > 0:
            prev_start = (group_idx - 1) * steps_per_chunk + 1
            context["previous_section"] = f"Steps {prev_start}-{step_start - 1}"
        
        if group_idx < len(step_groups) - 1:
            next_start = step_end + 1
            next_end = min(next_start + steps_per_chunk - 1, len(steps))
            context["next_section"] = f"Steps {next_start}-{next_end}"
        
        chunks.append(Chunk(
            content=chunk_content,
            chunk_index=len(chunks),
            total_chunks=0,  # Will update after
            section_type="steps",
            parent_id=entry_id,
            parent_title=entry_title,
            metadata={
                "title": entry_title,
                "type": entry.get("type", "how_to"),
                "entryType": entry.get("type", "how_to"),
                "category": entry.get("category"),
                "subcategory": entry.get("metadata", {}).get("subcategory"),
                "userType": entry.get("metadata", {}).get("userType", "internal"),
                "product": entry.get("metadata", {}).get("product", "property_engine"),
                "tags": entry.get("metadata", {}).get("tags", []),
                "section": f"Steps {step_start}-{step_end}",
                "section_type": "steps",
                "source": "upload",
                "original_filename": entry.get("metadata", {}).get("original_filename"),
            },
            context=context
        ))
    
    # Update total_chunks for all chunks
    total = len(chunks)
    for chunk in chunks:
        chunk.total_chunks = total
    
    logger.info(f"📄 Created {len(chunks)} step-based chunks for document {entry_id} ({len(steps)} steps)")
    
    return chunks


def is_document_entry(entry: Dict[str, Any]) -> bool:
    """
    Check if an entry is from document upload (vs template).
    
    Args:
        entry: KB entry dict
        
    Returns:
        True if this is an uploaded document entry
    """
    metadata = entry.get("metadata", {})
    return metadata.get("source") == "upload"
