"""
KB Management API Routes

This module serves as the main entry point for KB API routes.
All endpoints are organized in the src/api/kb/ package:
- entries.py: CRUD operations
- vectors.py: Vector sync and management
- documents.py: Document upload
- duplicates.py: Duplicate detection

The router from this module maintains the /api/kb prefix.
"""

from fastapi import APIRouter

from src.api.kb import router as kb_router

# Create main router with prefix
router = APIRouter(prefix="/api/kb", tags=["kb"])

# Include all KB sub-routes
router.include_router(kb_router)
