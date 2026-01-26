"""Entry Builder - Builds KB entries from analyzed documents"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .structure_analyzer import AnalysisResult, AnalyzedSection
from .extractors import ExtractionResult

logger = logging.getLogger(__name__)


class EntryBuilder:
    """
    Builds KB entries from analyzed documents.
    Produces entries in the same format as template-based entries.
    """
    
    def build_entry(
        self,
        analysis_result: AnalysisResult,
        extraction_result: ExtractionResult,
        user_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a KB entry from analyzed document.
        
        Args:
            analysis_result: Result from StructureAnalyzer
            extraction_result: Original extraction result (for metadata)
            user_metadata: User-provided metadata (userType, product, category, tags, title)
            
        Returns:
            KB entry dict ready for Firebase storage
        """
        entry_type = user_metadata.get("type", analysis_result.suggested_entry_type)
        
        # Build entry based on type
        if entry_type == "definition":
            return self._build_definition_entry(analysis_result, extraction_result, user_metadata)
        elif entry_type == "error":
            return self._build_error_entry(analysis_result, extraction_result, user_metadata)
        else:
            # Default to how_to for most documents
            return self._build_how_to_entry(analysis_result, extraction_result, user_metadata)
    
    def _build_how_to_entry(
        self,
        analysis_result: AnalysisResult,
        extraction_result: ExtractionResult,
        user_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a how_to type entry from document"""
        
        # Map analyzed sections to how_to structure
        raw_form_data = {
            "overview": analysis_result.overview or self._get_section_content(analysis_result.sections, "overview"),
            "prerequisites": self._get_section_content(analysis_result.sections, "prerequisites"),
            "steps": self._build_steps_from_sections(analysis_result.sections),
            "commonIssues": self._get_section_content(analysis_result.sections, "troubleshooting"),
            "tips": self._get_section_content(analysis_result.sections, "reference"),
            # Store all sections for complete content
            "sections": [
                {
                    "heading": s.heading,
                    "content": s.content,
                    "section_type": s.section_type,
                    "summary": s.summary
                }
                for s in analysis_result.sections
            ]
        }
        
        # Build searchable content string
        content = self._build_searchable_content(analysis_result, extraction_result)
        
        # Collect all key topics as tags
        all_topics = []
        for section in analysis_result.sections:
            all_topics.extend(section.key_topics)
        
        # Combine with user tags
        user_tags = user_metadata.get("tags", [])
        if isinstance(user_tags, str):
            user_tags = [t.strip() for t in user_tags.split(",") if t.strip()]
        combined_tags = list(set(user_tags + all_topics))
        
        return {
            "type": "how_to",
            "title": user_metadata.get("title") or analysis_result.title,
            "content": content,
            "category": user_metadata.get("category", "general"),
            "metadata": {
                "userType": user_metadata.get("userType", "internal"),
                "product": user_metadata.get("product", "property_engine"),
                "category": user_metadata.get("category", "general"),
                "subcategory": user_metadata.get("subcategory"),
                "tags": combined_tags,
                # Document-specific metadata
                "source": "upload",
                "original_filename": extraction_result.metadata.get("filename"),
                "document_type": analysis_result.document_type,
                "word_count": extraction_result.metadata.get("word_count"),
                "estimated_pages": extraction_result.metadata.get("estimated_pages"),
                "section_count": len(analysis_result.sections)
            },
            "rawFormData": raw_form_data,
            "tags": combined_tags
        }
    
    def _build_definition_entry(
        self,
        analysis_result: AnalysisResult,
        extraction_result: ExtractionResult,
        user_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a definition type entry from document"""
        
        # For definitions, extract term and definition from content
        first_section = analysis_result.sections[0] if analysis_result.sections else None
        
        raw_form_data = {
            "term": user_metadata.get("title") or analysis_result.title,
            "definition": analysis_result.overview or (first_section.content[:500] if first_section else ""),
            "context": self._get_section_content(analysis_result.sections, "details"),
            "examples": self._get_section_content(analysis_result.sections, "reference"),
        }
        
        content = self._build_searchable_content(analysis_result, extraction_result)
        
        return {
            "type": "definition",
            "title": user_metadata.get("title") or analysis_result.title,
            "content": content,
            "category": user_metadata.get("category", "general"),
            "metadata": {
                "userType": user_metadata.get("userType", "internal"),
                "product": user_metadata.get("product", "property_engine"),
                "category": user_metadata.get("category", "general"),
                "tags": user_metadata.get("tags", []),
                "source": "upload",
                "original_filename": extraction_result.metadata.get("filename")
            },
            "rawFormData": raw_form_data,
            "tags": user_metadata.get("tags", [])
        }
    
    def _build_error_entry(
        self,
        analysis_result: AnalysisResult,
        extraction_result: ExtractionResult,
        user_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build an error type entry from document"""
        
        raw_form_data = {
            "errorCode": "",  # User would need to provide
            "description": analysis_result.overview or "",
            "symptoms": self._get_section_content(analysis_result.sections, "overview"),
            "solution": self._get_section_content(analysis_result.sections, "steps") or 
                       self._get_section_content(analysis_result.sections, "troubleshooting"),
            "causes": self._extract_causes(analysis_result.sections),
            "prevention": self._get_section_content(analysis_result.sections, "reference"),
        }
        
        content = self._build_searchable_content(analysis_result, extraction_result)
        
        return {
            "type": "error",
            "title": user_metadata.get("title") or analysis_result.title,
            "content": content,
            "category": user_metadata.get("category", "general"),
            "metadata": {
                "userType": user_metadata.get("userType", "internal"),
                "product": user_metadata.get("product", "property_engine"),
                "category": user_metadata.get("category", "general"),
                "tags": user_metadata.get("tags", []),
                "source": "upload",
                "original_filename": extraction_result.metadata.get("filename")
            },
            "rawFormData": raw_form_data,
            "tags": user_metadata.get("tags", [])
        }
    
    def _get_section_content(
        self, 
        sections: List[AnalyzedSection], 
        section_type: str
    ) -> str:
        """Get content from sections matching a type"""
        matching = [s for s in sections if s.section_type == section_type]
        if matching:
            return "\n\n".join(s.content for s in matching)
        return ""
    
    def _build_steps_from_sections(
        self, 
        sections: List[AnalyzedSection]
    ) -> List[Dict[str, str]]:
        """Convert sections to steps format"""
        steps_sections = [s for s in sections if s.section_type == "steps"]
        
        if steps_sections:
            # If we have explicit steps sections, parse them
            steps = []
            for section in steps_sections:
                # Try to split by numbered items or paragraphs
                content = section.content
                lines = content.split("\n")
                
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 10:  # Skip very short lines
                        # Remove leading numbers like "1.", "2.", etc.
                        import re
                        clean_line = re.sub(r"^\d+[\.\)]\s*", "", line)
                        if clean_line:
                            steps.append({"action": clean_line})
            
            return steps if steps else [{"action": section.content} for section in steps_sections]
        
        # No explicit steps - use detail sections as steps
        detail_sections = [s for s in sections if s.section_type == "details"]
        return [{"action": s.content} for s in detail_sections[:10]]  # Max 10 steps
    
    def _extract_causes(self, sections: List[AnalyzedSection]) -> List[Dict[str, str]]:
        """Extract causes from sections for error entries"""
        causes = []
        
        # Look for troubleshooting or details sections
        for section in sections:
            if section.section_type in ["troubleshooting", "details"]:
                # Simple extraction - each paragraph could be a cause
                paragraphs = section.content.split("\n\n")
                for p in paragraphs[:5]:  # Max 5 causes
                    if p.strip():
                        causes.append({
                            "cause": p.strip()[:200],  # Truncate long causes
                            "solution": ""  # Would need more analysis
                        })
        
        return causes
    
    def _build_searchable_content(
        self, 
        analysis_result: AnalysisResult,
        extraction_result: ExtractionResult
    ) -> str:
        """Build a searchable content string for the entry"""
        parts = []
        
        # Add title
        parts.append(f"Title: {analysis_result.title}")
        
        # Add overview
        if analysis_result.overview:
            parts.append(f"Overview: {analysis_result.overview}")
        
        # Add section summaries
        for section in analysis_result.sections:
            if section.summary:
                parts.append(f"{section.heading}: {section.summary}")
            # Add key topics
            if section.key_topics:
                parts.append(f"Topics: {', '.join(section.key_topics)}")
        
        # Add truncated full text for search
        full_text = extraction_result.full_text
        if len(full_text) > 5000:
            full_text = full_text[:5000] + "..."
        parts.append(f"Content: {full_text}")
        
        return "\n\n".join(parts)
