"""Pydantic models for KB API endpoints"""

from pydantic import BaseModel, Field, ConfigDict
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

    # Audit trail fields - who created this entry
    createdBy: Optional[str] = Field(default=None, description="User ID who created the entry")
    createdByEmail: Optional[str] = Field(default=None, description="Email of creator")
    createdByName: Optional[str] = Field(default=None, description="Display name of creator")
    createdAt: Optional[str] = Field(default=None, description="ISO 8601 timestamp of creation")


class UpdateEntryRequest(BaseModel):
    """Request to update an existing KB entry"""
    # Allow extra fields from frontend without causing 422
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    rawFormData: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

    # Additional fields frontend may send
    userType: Optional[str] = None
    category: Optional[str] = None

    # Audit trail fields - who modified this entry
    lastModifiedBy: Optional[str] = Field(default=None, description="User ID who last modified")
    lastModifiedByEmail: Optional[str] = Field(default=None, description="Email of modifier")
    lastModifiedByName: Optional[str] = Field(default=None, description="Display name of modifier")
    lastModifiedAt: Optional[str] = Field(default=None, description="ISO 8601 timestamp of modification")
    updatedAt: Optional[str] = Field(default=None, description="ISO 8601 timestamp (alias for lastModifiedAt)")


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
# ARCHIVE MODELS
# ============================================================================

class ArchiveEntryRequest(BaseModel):
    """Request to archive a KB entry with audit trail"""
    archivedBy: Optional[str] = Field(default=None, description="User ID who archived")
    archivedByEmail: Optional[str] = Field(default=None, description="Email of archiver")
    archivedByName: Optional[str] = Field(default=None, description="Display name of archiver")
    archivedAt: Optional[str] = Field(default=None, description="ISO 8601 timestamp of archive")
    reason: Optional[str] = Field(default="Archived by user", description="Reason for archiving")


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
