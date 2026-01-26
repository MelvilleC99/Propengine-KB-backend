"""Structure Analyzer - Uses LLM to analyze and improve document structure"""

import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from .extractors import ExtractedSection, ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class AnalyzedSection:
    """A section after LLM analysis with improved metadata"""
    heading: str
    content: str
    level: int
    section_type: str  # overview, prerequisites, steps, details, troubleshooting, reference
    summary: str  # Brief summary for context
    key_topics: List[str]  # Main topics covered


@dataclass 
class AnalysisResult:
    """Result of structure analysis"""
    title: str
    overview: str
    sections: List[AnalyzedSection]
    document_type: str  # how_to, reference, policy, training
    suggested_entry_type: str  # how_to, definition, error
    success: bool
    error: Optional[str] = None


class StructureAnalyzer:
    """
    Analyzes extracted document content using LLM to:
    1. Identify logical sections if not well-structured
    2. Classify section types (overview, steps, troubleshooting, etc.)
    3. Generate summaries for context
    4. Suggest appropriate KB entry type
    """
    
    def __init__(self):
        from langchain_openai import ChatOpenAI
        
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # Fast and cost-effective for analysis
            temperature=0
        )
        logger.info("✅ Structure Analyzer initialized")
    
    async def analyze(
        self, 
        extraction_result: ExtractionResult,
        user_selected_type: Optional[str] = None
    ) -> AnalysisResult:
        """
        Analyze extracted document and improve structure.
        
        Args:
            extraction_result: Result from DocxExtractor
            user_selected_type: If user already chose entry type, respect it
            
        Returns:
            AnalysisResult with improved structure
        """
        try:
            if not extraction_result.success:
                return AnalysisResult(
                    title="",
                    overview="",
                    sections=[],
                    document_type="unknown",
                    suggested_entry_type=user_selected_type or "how_to",
                    success=False,
                    error=extraction_result.error
                )
            
            # If document has good structure (multiple sections), analyze each
            if len(extraction_result.sections) > 1:
                return await self._analyze_structured_document(
                    extraction_result, 
                    user_selected_type
                )
            else:
                # Single section - need LLM to identify structure
                return await self._analyze_unstructured_document(
                    extraction_result,
                    user_selected_type
                )
                
        except Exception as e:
            logger.error(f"❌ Structure analysis failed: {e}", exc_info=True)
            return AnalysisResult(
                title=extraction_result.metadata.get("title", "Untitled"),
                overview="",
                sections=[],
                document_type="unknown",
                suggested_entry_type=user_selected_type or "how_to",
                success=False,
                error=str(e)
            )
    
    async def _analyze_structured_document(
        self,
        extraction_result: ExtractionResult,
        user_selected_type: Optional[str]
    ) -> AnalysisResult:
        """Analyze document that already has heading structure"""
        
        # Build sections summary for LLM
        sections_summary = []
        for i, section in enumerate(extraction_result.sections):
            sections_summary.append({
                "index": i,
                "heading": section.heading,
                "content_preview": section.content[:500] + "..." if len(section.content) > 500 else section.content,
                "level": section.level
            })
        
        prompt = f"""Analyze this document structure and classify each section.

Document title: {extraction_result.metadata.get('title', 'Untitled')}
Total sections: {len(extraction_result.sections)}

Sections:
{json.dumps(sections_summary, indent=2)}

For each section, determine:
1. section_type: One of [overview, prerequisites, steps, details, troubleshooting, reference, glossary, appendix]
2. summary: A 1-2 sentence summary of what this section covers
3. key_topics: List of 2-4 main topics/keywords

Also determine:
- document_type: One of [how_to, reference, policy, training, troubleshooting]
- suggested_entry_type: One of [how_to, definition, error] - which KB template fits best
- overview: A 2-3 sentence overview of the entire document

Respond in JSON format:
{{
    "overview": "...",
    "document_type": "...",
    "suggested_entry_type": "...",
    "sections": [
        {{
            "index": 0,
            "section_type": "...",
            "summary": "...",
            "key_topics": ["...", "..."]
        }}
    ]
}}"""

        response = await self.llm.ainvoke(prompt)
        
        try:
            # Parse LLM response
            response_text = response.content
            # Handle markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            analysis = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response, using defaults: {e}")
            analysis = self._get_default_analysis(extraction_result.sections)
        
        # Build analyzed sections
        analyzed_sections = []
        for i, section in enumerate(extraction_result.sections):
            section_analysis = next(
                (s for s in analysis.get("sections", []) if s.get("index") == i),
                {"section_type": "details", "summary": "", "key_topics": []}
            )
            
            analyzed_sections.append(AnalyzedSection(
                heading=section.heading,
                content=section.content,
                level=section.level,
                section_type=section_analysis.get("section_type", "details"),
                summary=section_analysis.get("summary", ""),
                key_topics=section_analysis.get("key_topics", [])
            ))
        
        return AnalysisResult(
            title=extraction_result.metadata.get("title", "Untitled"),
            overview=analysis.get("overview", ""),
            sections=analyzed_sections,
            document_type=analysis.get("document_type", "how_to"),
            suggested_entry_type=user_selected_type or analysis.get("suggested_entry_type", "how_to"),
            success=True
        )
    
    async def _analyze_unstructured_document(
        self,
        extraction_result: ExtractionResult,
        user_selected_type: Optional[str]
    ) -> AnalysisResult:
        """Analyze document without clear heading structure - LLM identifies sections"""
        
        full_text = extraction_result.full_text
        
        # Truncate if too long (for cost/context limits)
        max_chars = 15000
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n\n[Document truncated for analysis...]"
        
        prompt = f"""Analyze this document and identify logical sections.

Document title: {extraction_result.metadata.get('title', 'Untitled')}

Content:
{full_text}

Identify 3-8 logical sections in this document. For each section:
1. heading: A clear heading for this section
2. content: The text that belongs to this section (copy exactly from document)
3. section_type: One of [overview, prerequisites, steps, details, troubleshooting, reference]
4. summary: 1-2 sentence summary
5. key_topics: 2-4 main topics

Also determine:
- overview: 2-3 sentence overview of entire document
- document_type: One of [how_to, reference, policy, training, troubleshooting]
- suggested_entry_type: One of [how_to, definition, error]

Respond in JSON format:
{{
    "overview": "...",
    "document_type": "...",
    "suggested_entry_type": "...",
    "sections": [
        {{
            "heading": "...",
            "content": "...",
            "section_type": "...",
            "summary": "...",
            "key_topics": ["...", "..."]
        }}
    ]
}}"""

        response = await self.llm.ainvoke(prompt)
        
        try:
            response_text = response.content
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            analysis = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Return single section as fallback
            return AnalysisResult(
                title=extraction_result.metadata.get("title", "Untitled"),
                overview="",
                sections=[AnalyzedSection(
                    heading="Document Content",
                    content=extraction_result.full_text,
                    level=1,
                    section_type="details",
                    summary="",
                    key_topics=[]
                )],
                document_type="how_to",
                suggested_entry_type=user_selected_type or "how_to",
                success=True
            )
        
        # Build analyzed sections from LLM response
        analyzed_sections = []
        for i, section_data in enumerate(analysis.get("sections", [])):
            analyzed_sections.append(AnalyzedSection(
                heading=section_data.get("heading", f"Section {i+1}"),
                content=section_data.get("content", ""),
                level=1,
                section_type=section_data.get("section_type", "details"),
                summary=section_data.get("summary", ""),
                key_topics=section_data.get("key_topics", [])
            ))
        
        return AnalysisResult(
            title=extraction_result.metadata.get("title", "Untitled"),
            overview=analysis.get("overview", ""),
            sections=analyzed_sections,
            document_type=analysis.get("document_type", "how_to"),
            suggested_entry_type=user_selected_type or analysis.get("suggested_entry_type", "how_to"),
            success=True
        )
    
    def _get_default_analysis(self, sections: List[ExtractedSection]) -> Dict[str, Any]:
        """Generate default analysis when LLM fails"""
        return {
            "overview": "",
            "document_type": "how_to",
            "suggested_entry_type": "how_to",
            "sections": [
                {
                    "index": i,
                    "section_type": "overview" if i == 0 else "details",
                    "summary": "",
                    "key_topics": []
                }
                for i in range(len(sections))
            ]
        }
