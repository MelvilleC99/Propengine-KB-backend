"""
KB API Routes Package

This package contains all KB-related API endpoints, organized by functionality:
- entries: CRUD operations for KB entries
- vectors: Vector sync and management
- documents: Document upload and processing
- duplicates: Duplicate detection before entry creation
"""

from fastapi import APIRouter

from .entries import router as entries_router
from .vectors import router as vectors_router
from .documents import router as documents_router
from .duplicates import router as duplicates_router

# Combined router for all KB endpoints
router = APIRouter()

# Include all sub-routers
router.include_router(entries_router)
router.include_router(vectors_router)
router.include_router(documents_router)
router.include_router(duplicates_router)

# Export for easy importing
__all__ = [
    "router",
    "entries_router",
    "vectors_router",
    "documents_router",
    "duplicates_router",
]
