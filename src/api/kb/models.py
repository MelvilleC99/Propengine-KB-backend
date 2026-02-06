"""Pydantic models for KB API endpoints"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


# ============================================================================
# ENTRY MODELS
# ============================================================================

class CreateEntryRequest(BaseModel):
    """Request to create a new KB entry - matches frontend format"""
    type: str = Field(..., description="Entry type: how_to, error, definition, workflow")
    title: str = Field(..., min_length=3, description="Entry title")
    content: str = Field(..., description="Searchable text content")
    metadata: Dict[str, Any] = Field(..., description="Entry metadata with category, userType, etc")
    rawFormData: Optional[Dict[str, Any]] = Field(default=None, description="Raw form data")
    tags: Optional[List[str]] = Field(default=None, description="Entry tags")
    author: Optional[str] = Field(default=None, description="Entry author")


class UpdateEntryRequest(BaseModel):
    """Request to update an existing KB entry"""
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    rawFormData: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class EntryResponse(BaseModel):
    """Response containing entry data"""
    success: bool
    entry_id: str
    entry: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class ListEntriesResponse(BaseModel):
    """Response containing list of entries"""
    success: bool
    entries: List[Dict[str, Any]]
    count: int


# ============================================================================
# SYNC MODELS
# ============================================================================

class SyncRequest(BaseModel):
    """Request to sync a KB entry to vector database"""
    entry_id: str


class SyncResponse(BaseModel):
    """Response from sync operation"""
    success: bool
    message: str
    entry_id: str
    error: Optional[str] = None


# ============================================================================
# DUPLICATE CHECK MODELS
# ============================================================================

class DuplicateCheckRequest(BaseModel):
    """Request to check for duplicate entries"""
    title: str = Field(..., min_length=1, description="Entry title")
    content: str = Field(..., min_length=1, description="Entry content")
    type: str = Field(..., description="Entry type: how_to, error, definition, workflow")


class SimilarEntry(BaseModel):
    """A similar entry found during duplicate check"""
    id: str
    title: str
    similarity_score: float
    type: str
    category: Optional[str] = None
    content_snippet: str
    created_at: Optional[str] = None


class DuplicateCheckResponse(BaseModel):
    """Response from duplicate check"""
    has_duplicates: bool
    similar_entries: List[SimilarEntry]
