from __future__ import annotations

"""
API Authentication — Token-based auth for all endpoints.
"""

import hashlib
import hmac
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("auth")

TOKEN_FILE = Path(__file__).parent.parent / "data" / "api_token"

# Exact public paths (no prefix matching — M7 fix)
PUBLIC_EXACT = {"/", "/manifest.json", "/sw.js"}
PUBLIC_PREFIXES = {"/css/", "/js/", "/assets/"}


def get_or_create_token() -> str:
    """Get existing API token or generate a new one."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()

    # C1: Use full 64-char hex for stronger entropy
    token = os.urandom(32).hex()
    TOKEN_FILE.write_text(token)
    os.chmod(str(TOKEN_FILE), 0o600)
    # C1: Do NOT log the token — only log that one was generated
    logger.info("New API token generated. Read it from: data/api_token")
    return token


API_TOKEN = get_or_create_token()


def verify_token(token: str) -> bool:
    """Verify an API token using timing-safe comparison (C2 fix)."""
    if not token:
        return False
    return hmac.compare_digest(token.encode(), API_TOKEN.encode())


def extract_token(request: Request) -> Optional[str]:
    """Extract token from request header or query param."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.query_params.get("token")


def is_public_path(path: str) -> bool:
    """Check if a path is public. Uses exact matches + strict prefix checks (M7 fix)."""
    if path in PUBLIC_EXACT:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix) and ".." not in path:
            return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if is_public_path(path):
            return await call_next(request)

        token = extract_token(request)
        if not verify_token(token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        return await call_next(request)


async def verify_ws_token(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token", "")
    return verify_token(token)
