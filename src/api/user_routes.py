"""User Management API Routes

Handles user CRUD operations using Firebase Admin SDK.
Creates/updates/deletes users in both Firebase Auth AND Firestore users collection.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging

from src.database.firebase_client import get_firestore_client, get_firebase_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


# ==================== REQUEST/RESPONSE MODELS ====================

class CreateUserRequest(BaseModel):
    """Request model for creating a new user"""
    email: str = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 chars)")
    name: str = Field(..., description="User's first name")
    surname: str = Field(..., description="User's surname")
    phone: Optional[str] = Field(None, description="User's phone number")
    company: str = Field(..., description="Company name")
    office: Optional[str] = Field("", description="Office location")
    role: str = Field("agent", description="User role (agent, admin, etc.)")


class UpdateUserRequest(BaseModel):
    """Request model for updating a user"""
    name: Optional[str] = Field(None, description="User's first name")
    surname: Optional[str] = Field(None, description="User's surname")
    phone: Optional[str] = Field(None, description="User's phone number")
    company: Optional[str] = Field(None, description="Company name")
    office: Optional[str] = Field(None, description="Office location")
    role: Optional[str] = Field(None, description="User role")
    password: Optional[str] = Field(None, min_length=6, description="New password (min 6 chars)")


class UserResponse(BaseModel):
    """Response model for user operations"""
    success: bool
    message: str
    user: Optional[dict] = None


# ==================== ENDPOINTS ====================

@router.post("/", response_model=UserResponse)
async def create_user(request: CreateUserRequest):
    """
    Create a new user in Firebase Auth AND Firestore users collection.

    This mirrors the Next.js route.ts logic (lines 22-66):
    1. Create user in Firebase Auth with email/password
    2. Create user document in Firestore 'users' collection (keyed by email)
    """
    try:
        auth = get_firebase_auth()
        db = get_firestore_client()

        # 1. Create user in Firebase Auth
        logger.info(f"Creating Firebase Auth user: {request.email}")

        user_record = auth.create_user(
            email=request.email,
            password=request.password,
            display_name=f"{request.name} {request.surname}"
        )

        logger.info(f"✅ Firebase Auth user created: {user_record.uid}")

        # 2. Create user document in Firestore
        user_data = {
            "agent_id": user_record.uid,
            "email": request.email,
            "name": request.name,
            "surname": request.surname,
            "full_name": f"{request.name} {request.surname}",
            "phone": request.phone,
            "company": request.company,
            "office": request.office or "",
            "agency": f"{request.company} Real Estate",
            "division": request.office or "General",
            "user_type": "internal",
            "role": request.role,
            "created_at": datetime.now(),
            "last_login": None,
            "total_queries": 0,
            "total_sessions": 0,
            "preferences": {
                "notifications": True,
                "email_updates": False
            }
        }

        # Use email as document ID (matching Next.js logic)
        db.collection("users").document(request.email).set(user_data)

        logger.info(f"✅ Firestore user document created: {request.email}")

        return UserResponse(
            success=True,
            message=f"User {request.email} created successfully",
            user={
                "uid": user_record.uid,
                "email": request.email,
                "name": request.name,
                "surname": request.surname,
                "role": request.role
            }
        )

    except auth.EmailAlreadyExistsError:
        logger.warning(f"User already exists: {request.email}")
        raise HTTPException(
            status_code=409,
            detail=f"User with email {request.email} already exists"
        )
    except Exception as e:
        logger.error(f"❌ Failed to create user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{email}", response_model=UserResponse)
async def update_user(email: str, request: UpdateUserRequest):
    """
    Update an existing user in Firebase Auth AND Firestore.

    Updates:
    1. Firebase Auth (display_name, password if provided)
    2. Firestore user document (all provided fields)
    """
    try:
        auth = get_firebase_auth()
        db = get_firestore_client()

        # 1. Get user from Firebase Auth by email
        try:
            user_record = auth.get_user_by_email(email)
        except auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {email} not found")

        # 2. Update Firebase Auth
        auth_updates = {}

        if request.name or request.surname:
            # Get current values for partial updates
            current_name = request.name or user_record.display_name.split()[0] if user_record.display_name else ""
            current_surname = request.surname or (user_record.display_name.split()[1] if user_record.display_name and len(user_record.display_name.split()) > 1 else "")
            auth_updates["display_name"] = f"{current_name} {current_surname}".strip()

        if request.password:
            auth_updates["password"] = request.password

        if auth_updates:
            auth.update_user(user_record.uid, **auth_updates)
            logger.info(f"✅ Firebase Auth user updated: {email}")

        # 3. Update Firestore document
        firestore_updates = {"updated_at": datetime.now()}

        if request.name:
            firestore_updates["name"] = request.name
        if request.surname:
            firestore_updates["surname"] = request.surname
        if request.name or request.surname:
            name = request.name or ""
            surname = request.surname or ""
            firestore_updates["full_name"] = f"{name} {surname}".strip()
        if request.phone is not None:
            firestore_updates["phone"] = request.phone
        if request.company:
            firestore_updates["company"] = request.company
            firestore_updates["agency"] = f"{request.company} Real Estate"
        if request.office is not None:
            firestore_updates["office"] = request.office
            firestore_updates["division"] = request.office or "General"
        if request.role:
            firestore_updates["role"] = request.role

        db.collection("users").document(email).update(firestore_updates)
        logger.info(f"✅ Firestore user document updated: {email}")

        return UserResponse(
            success=True,
            message=f"User {email} updated successfully",
            user={"email": email, "updated_fields": list(firestore_updates.keys())}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{email}", response_model=UserResponse)
async def delete_user(email: str):
    """
    Delete a user from Firebase Auth AND Firestore.

    Removes:
    1. User from Firebase Auth
    2. User document from Firestore 'users' collection
    """
    try:
        auth = get_firebase_auth()
        db = get_firestore_client()

        # 1. Get user from Firebase Auth
        try:
            user_record = auth.get_user_by_email(email)
        except auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail=f"User {email} not found")

        # 2. Delete from Firebase Auth
        auth.delete_user(user_record.uid)
        logger.info(f"✅ Firebase Auth user deleted: {email}")

        # 3. Delete from Firestore
        db.collection("users").document(email).delete()
        logger.info(f"✅ Firestore user document deleted: {email}")

        return UserResponse(
            success=True,
            message=f"User {email} deleted successfully",
            user={"email": email, "uid": user_record.uid}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{email}", response_model=UserResponse)
async def get_user(email: str):
    """
    Get a user's details from Firestore.
    """
    try:
        db = get_firestore_client()

        # Get user document
        user_doc = db.collection("users").document(email).get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail=f"User {email} not found")

        user_data = user_doc.to_dict()

        # Convert datetime objects to ISO strings for JSON serialization
        if user_data.get("created_at"):
            user_data["created_at"] = user_data["created_at"].isoformat() if hasattr(user_data["created_at"], 'isoformat') else str(user_data["created_at"])
        if user_data.get("last_login"):
            user_data["last_login"] = user_data["last_login"].isoformat() if hasattr(user_data["last_login"], 'isoformat') else str(user_data["last_login"])

        return UserResponse(
            success=True,
            message=f"User {email} retrieved successfully",
            user=user_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=dict)
async def list_users(limit: int = 50):
    """
    List all users from Firestore users collection.
    """
    try:
        db = get_firestore_client()

        # Get users from Firestore
        users_ref = db.collection("users").limit(limit)
        users_docs = users_ref.get()

        users = []
        for doc in users_docs:
            user_data = doc.to_dict()
            # Convert datetime for serialization
            if user_data.get("created_at"):
                user_data["created_at"] = str(user_data["created_at"])
            if user_data.get("last_login"):
                user_data["last_login"] = str(user_data["last_login"])
            users.append(user_data)

        return {
            "success": True,
            "users": users,
            "count": len(users)
        }

    except Exception as e:
        logger.error(f"❌ Failed to list users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
