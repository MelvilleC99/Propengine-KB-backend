"""Authentication — verify the caller's Firebase ID token.

A single dependency, `verify_user`, gates the protected routers (wired in main.py).
Behaviour is controlled by `settings.REQUIRE_AUTH`:
  - True  → a valid Firebase ID token is required, else 401.
  - False → auth is skipped (open). Use only for local dev or a short migration
            window (e.g. before the frontend is sending the token).

Firebase Admin is already initialised by the app (src/database/firebase_client.py),
so `auth.verify_id_token` works without any extra setup. The decoded token (uid,
email, and any custom claims like role) is returned, so a later `verify_admin` can
build on this without re-verifying.
"""

import logging
from fastapi import Header, HTTPException
from firebase_admin import auth as firebase_auth
from src.config.settings import settings

logger = logging.getLogger(__name__)


async def verify_user(authorization: str = Header(None)):
    """Verify the caller's Firebase ID token.

    Returns the decoded token dict (uid, email, custom claims) on success, or None
    when auth is disabled. Raises 401 when enabled and the token is missing/invalid.
    """
    # Migration / local-dev escape hatch — let everything through when auth is off.
    if not settings.REQUIRE_AUTH:
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    try:
        return firebase_auth.verify_id_token(token)
    except Exception as e:
        # Log the reason for us; return a generic message to the caller.
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def verify_user_optional(authorization: str = Header(None)):
    """Soft identity extractor — returns the decoded token if a valid one is present,
    else None. Never raises.

    Used by the customer chatbot routes to capture WHO is asking (createdBy) without
    being the gate themselves. The hard gate is the router-level `_customer_auth` in
    main.py: when CUSTOMER_AGENT_PUBLIC is true the flow is open (and this just grabs the
    identity if a token happens to be sent); when false, `_customer_auth` (verify_user)
    enforces a token before the request reaches the route, and this then decodes it.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        return firebase_auth.verify_id_token(token)
    except Exception as e:
        # In the open window an invalid token shouldn't 401 the customer; just drop identity.
        logger.warning(f"Optional token verification failed (ignored): {e}")
        return None
