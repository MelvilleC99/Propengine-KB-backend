"""KB Document Upload Operations"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional
import logging

from src.services.firebase import FirebaseService
from src.services.vector_sync import VectorSyncService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["kb-documents"])


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    entry_type: str = Form(...),
    userType: str = Form(...),
    product: str = Form(...),
    category: str = Form(...),
    tags: str = Form(default=""),
    subcategory: str = Form(default=""),
    auto_sync: bool = Form(default=True)
):
    """
    Upload a document (DOCX or PDF) and create a KB entry.

    This endpoint:
    1. Extracts text and structure from the document
    2. Uses LLM to analyze and improve structure
    3. Builds a KB entry in the same format as template entries
    4. Saves to Firebase
    5. Optionally syncs to vector database

    Form fields:
    - file: The document file (DOCX or PDF)
    - title: Entry title
    - entry_type: Type of entry (how_to, definition, error)
    - userType: internal or customer
    - product: Product name
    - category: Category
    - tags: Comma-separated tags
    - subcategory: Optional subcategory
    - auto_sync: Whether to automatically sync to vector DB (default: true)
    """
    from src.document_processing import get_extractor, StructureAnalyzer, EntryBuilder

    try:
        logger.info(f"Document upload started: {file.filename}")

        # Validate file type
        filename_lower = file.filename.lower()
        if not (filename_lower.endswith('.docx') or filename_lower.endswith('.pdf')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only DOCX and PDF files are supported."
            )

        # Read file bytes
        file_bytes = await file.read()
        logger.info(f"Read {len(file_bytes)} bytes from {file.filename}")

        # Step 1: Extract text and structure
        extractor = get_extractor(file.filename)
        extraction_result = await extractor.extract(file_bytes, file.filename)

        if not extraction_result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to extract document: {extraction_result.error}"
            )

        logger.info(f"Extracted {len(extraction_result.sections)} sections from document")

        # Step 2: Analyze structure with LLM
        analyzer = StructureAnalyzer()
        analysis_result = await analyzer.analyze(extraction_result, entry_type)

        if not analysis_result.success:
            logger.warning(f"Structure analysis failed: {analysis_result.error}, proceeding with basic structure")

        # Step 3: Build KB entry
        builder = EntryBuilder()

        # Parse tags
        tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        user_metadata = {
            "title": title,
            "type": entry_type,
            "userType": userType,
            "product": product,
            "category": category,
            "subcategory": subcategory if subcategory else None,
            "tags": tags_list
        }

        entry_data = builder.build_entry(analysis_result, extraction_result, user_metadata)

        logger.info(f"Built KB entry: {entry_data.get('title')}")

        # Step 4: Save to Firebase
        firebase_mcp = FirebaseService()
        create_result = await firebase_mcp.create_entry(entry_data)

        if not create_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save entry: {create_result.get('error')}"
            )

        entry_id = create_result["entry_id"]
        logger.info(f"Saved to Firebase: {entry_id}")

        # Step 5: Optionally sync to vector database
        sync_result = None
        if auto_sync:
            sync_mcp = VectorSyncService()
            sync_result = await sync_mcp.sync_entry_to_vector(entry_id)

            if sync_result["success"]:
                logger.info(f"Synced to vector DB: {sync_result.get('chunks_created')} chunks")
            else:
                logger.warning(f"Vector sync failed: {sync_result.get('error')}")

        return {
            "success": True,
            "entry_id": entry_id,
            "title": entry_data.get("title"),
            "sections_extracted": len(extraction_result.sections),
            "word_count": extraction_result.metadata.get("word_count"),
            "sync_status": sync_result if auto_sync else {"status": "pending", "message": "Auto-sync disabled"},
            "message": "Document processed and saved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/documents/status/{entry_id}")
async def get_document_status(entry_id: str):
    """
    Get processing status for an uploaded document.

    Useful for async processing - check if document has been synced.
    """
    try:
        firebase_mcp = FirebaseService()
        result = await firebase_mcp.get_entry(entry_id)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )

        entry = result["entry"]

        return {
            "success": True,
            "entry_id": entry_id,
            "title": entry.get("title"),
            "vector_status": entry.get("vectorStatus", "unknown"),
            "chunks_created": entry.get("chunksCreated"),
            "sync_error": entry.get("syncError"),
            "source": entry.get("metadata", {}).get("source"),
            "original_filename": entry.get("metadata", {}).get("original_filename")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
