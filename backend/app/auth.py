import json
from functools import lru_cache

import firebase_admin
from fastapi import Header, HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.config import get_settings


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    settings = get_settings()
    if settings.firebase_service_account_path:
        cred = credentials.Certificate(settings.firebase_service_account_path)
    elif settings.firebase_service_account_json:
        cred = credentials.Certificate(json.loads(settings.firebase_service_account_json))
    else:
        raise RuntimeError(
            "Firebase is not configured: set FIREBASE_SERVICE_ACCOUNT_PATH or "
            "FIREBASE_SERVICE_ACCOUNT_JSON."
        )
    return firebase_admin.initialize_app(cred)


async def get_current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )

    get_firebase_app()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc
    return decoded["uid"]
