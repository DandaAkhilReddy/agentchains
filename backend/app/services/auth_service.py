"""Firebase Admin SDK token verification."""

import base64
import json
import logging
import os

import firebase_admin
from firebase_admin import auth, credentials

from app.config import settings

logger = logging.getLogger(__name__)

_app = None


def _init_firebase():
    global _app
    if _app is not None:
        return
    try:
        # Strategy 1: Base64-encoded service account JSON (preferred for deployment)
        if settings.firebase_service_account_base64:
            sa_json = json.loads(
                base64.b64decode(settings.firebase_service_account_base64)
            )
            cred = credentials.Certificate(sa_json)
            _app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized with service account (base64)")

        # Strategy 2: GOOGLE_APPLICATION_CREDENTIALS env var (file path)
        elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            _app = firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized via GOOGLE_APPLICATION_CREDENTIALS")

        # Strategy 3: Project ID only (fallback)
        elif settings.firebase_project_id:
            _app = firebase_admin.initialize_app(options={
                "projectId": settings.firebase_project_id,
            })
            logger.info("Firebase Admin SDK initialized with project ID only")

        else:
            _app = firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with default credentials")

    except Exception as e:
        logger.warning(f"Firebase init failed (may already be initialized): {e}")


def verify_firebase_token(id_token: str) -> dict | None:
    """Verify a Firebase ID token and return decoded claims.

    Returns:
        Dict with uid, email, phone_number, name, etc. or None if invalid.
    """
    _init_firebase()
    try:
        decoded = auth.verify_id_token(id_token)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email"),
            "phone": decoded.get("phone_number"),
            "name": decoded.get("name"),
        }
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None
