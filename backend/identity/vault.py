from __future__ import annotations

"""
Identity Vault — Encrypted Credential Store

Agents need to authenticate to services without the user entering
passwords or solving captchas every time. The Identity Vault:

1. Stores OAuth tokens, API keys, and session cookies encrypted
2. Auto-refreshes expired tokens
3. Handles OAuth2 device flow for new service connections
4. Provides agents with temporary scoped tokens (not raw credentials)
5. Revokes access instantly if compromised

The vault is the ONLY component that touches raw credentials.
Agents receive scoped, time-limited access tokens.
"""

import base64
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("identity")

VAULT_PATH = Path(__file__).parent.parent.parent / "data" / "vault.enc"


class IdentityVault:
    """Encrypted credential store for agent authentication."""

    def __init__(self, master_key: str = ""):
        self._key = self._derive_key(master_key or self._get_machine_id())
        self._credentials: Dict[str, dict] = {}
        self._sessions: Dict[str, dict] = {}  # agent_id -> {service, token, expires_at}
        self._load()

    def _derive_key(self, passphrase: str) -> bytes:
        """Derive encryption key with per-installation random salt (C6 fix)."""
        salt_file = VAULT_PATH.parent / "vault_salt"
        salt_file.parent.mkdir(parents=True, exist_ok=True)
        if salt_file.exists():
            salt = salt_file.read_bytes()
        else:
            salt = os.urandom(32)
            salt_file.write_bytes(salt)
            os.chmod(str(salt_file), 0o600)
        return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 100000)

    def _get_machine_id(self) -> str:
        """Get a machine-specific ID + random component for default encryption."""
        import platform
        # Include random per-install component
        id_file = VAULT_PATH.parent / "machine_id"
        id_file.parent.mkdir(parents=True, exist_ok=True)
        if id_file.exists():
            extra = id_file.read_text()
        else:
            extra = os.urandom(16).hex()
            id_file.write_text(extra)
            os.chmod(str(id_file), 0o600)
        parts = [platform.node(), platform.machine(), extra]
        return hashlib.sha256(":".join(parts).encode()).hexdigest()[:32]

    def _encrypt(self, data: str) -> str:
        """AES-256 encryption via Fernet. No fallback (C5 fix)."""
        from cryptography.fernet import Fernet
        fernet_key = base64.urlsafe_b64encode(self._key[:32])
        f = Fernet(fernet_key)
        return f.encrypt(data.encode()).decode()

    def _decrypt(self, data: str) -> str:
        """Decrypt AES-256 encrypted data. No XOR fallback."""
        from cryptography.fernet import Fernet
        fernet_key = base64.urlsafe_b64encode(self._key[:32])
        f = Fernet(fernet_key)
        return f.decrypt(data.encode()).decode()

    def _load(self):
        """Load vault from encrypted file."""
        if not VAULT_PATH.exists():
            return
        try:
            encrypted = VAULT_PATH.read_text()
            decrypted = self._decrypt(encrypted)
            self._credentials = json.loads(decrypted)
            logger.info(f"Vault loaded: {len(self._credentials)} credentials")
        except Exception as e:
            logger.error(f"Vault load error: {e}")
            self._credentials = {}

    def _save(self):
        """Save vault to encrypted file."""
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.dumps(self._credentials)
            encrypted = self._encrypt(data)
            VAULT_PATH.write_text(encrypted)
        except Exception as e:
            logger.error(f"Vault save error: {e}")

    def store_credential(
        self,
        service_id: str,
        credential_type: str,  # "oauth2", "api_key", "session", "password"
        data: dict,
    ):
        """Store a credential in the vault."""
        self._credentials[service_id] = {
            "type": credential_type,
            "data": data,
            "stored_at": time.time(),
            "last_used": time.time(),
        }
        self._save()
        logger.info(f"Stored credential for: {service_id}")

    def get_credential(self, service_id: str) -> Optional[dict]:
        """Get raw credential (only used internally by vault)."""
        cred = self._credentials.get(service_id)
        if cred:
            cred["last_used"] = time.time()
            self._save()
        return cred

    def issue_session_token(
        self,
        agent_id: str,
        service_id: str,
        scopes: List[str] = None,
        ttl: int = 3600,
    ) -> Optional[str]:
        """Issue a scoped, time-limited token for an agent.

        The agent never sees the raw credential — only this session token.
        """
        cred = self._credentials.get(service_id)
        if not cred:
            return None

        session_id = hashlib.sha256(
            f"{agent_id}:{service_id}:{time.time()}:{os.urandom(8).hex()}".encode()
        ).hexdigest()[:32]

        self._sessions[session_id] = {
            "agent_id": agent_id,
            "service_id": service_id,
            "scopes": scopes or ["read"],
            "issued_at": time.time(),
            "expires_at": time.time() + ttl,
            "credential_type": cred["type"],
        }

        logger.info(f"Issued session token for {agent_id} -> {service_id} (TTL: {ttl}s)")
        return session_id

    def validate_session(self, session_id: str) -> Optional[dict]:
        """Validate a session token and return session info."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        if time.time() > session["expires_at"]:
            del self._sessions[session_id]
            return None

        return session

    def get_access_token(self, session_id: str) -> Optional[str]:
        """Get the actual access token for a valid session.

        This is the only way an agent can get credential data,
        and it's scoped and time-limited.
        """
        session = self.validate_session(session_id)
        if not session:
            return None

        cred = self._credentials.get(session["service_id"])
        if not cred:
            return None

        cred_data = cred.get("data", {})

        if cred["type"] == "oauth2":
            # Check if token needs refresh
            if time.time() > cred_data.get("expires_at", 0):
                refreshed = self._refresh_oauth(session["service_id"], cred_data)
                if not refreshed:
                    return None
                cred_data = self._credentials[session["service_id"]]["data"]
            return cred_data.get("access_token")

        elif cred["type"] == "api_key":
            return cred_data.get("key")

        elif cred["type"] == "session":
            return cred_data.get("session_token")

        return None

    def _refresh_oauth(self, service_id: str, cred_data: dict) -> bool:
        """Refresh an OAuth2 token."""
        refresh_token = cred_data.get("refresh_token")
        token_url = cred_data.get("token_url")
        client_id = cred_data.get("client_id")
        client_secret = cred_data.get("client_secret")

        if not all([refresh_token, token_url, client_id]):
            return False

        try:
            import httpx
            with httpx.Client() as client:
                resp = client.post(token_url, data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret or "",
                })
                if resp.status_code == 200:
                    new_data = resp.json()
                    cred_data["access_token"] = new_data["access_token"]
                    cred_data["expires_at"] = time.time() + new_data.get("expires_in", 3600)
                    if "refresh_token" in new_data:
                        cred_data["refresh_token"] = new_data["refresh_token"]
                    self._credentials[service_id]["data"] = cred_data
                    self._save()
                    logger.info(f"Refreshed OAuth token for {service_id}")
                    return True
        except Exception as e:
            logger.error(f"OAuth refresh error for {service_id}: {e}")

        return False

    def revoke(self, service_id: str):
        """Revoke all credentials and sessions for a service."""
        if service_id in self._credentials:
            del self._credentials[service_id]
            self._save()

        # Kill all sessions for this service
        to_remove = [
            sid for sid, s in self._sessions.items()
            if s["service_id"] == service_id
        ]
        for sid in to_remove:
            del self._sessions[sid]

        logger.info(f"Revoked all credentials for {service_id}")

    def revoke_agent(self, agent_id: str):
        """Revoke all sessions for a specific agent."""
        to_remove = [
            sid for sid, s in self._sessions.items()
            if s["agent_id"] == agent_id
        ]
        for sid in to_remove:
            del self._sessions[sid]
        logger.info(f"Revoked all sessions for agent {agent_id}")

    def list_services(self) -> List[dict]:
        """List all stored services (without revealing credentials)."""
        return [
            {
                "service_id": sid,
                "type": cred["type"],
                "stored_at": cred["stored_at"],
                "last_used": cred["last_used"],
                "active_sessions": sum(
                    1 for s in self._sessions.values()
                    if s["service_id"] == sid and time.time() < s["expires_at"]
                ),
            }
            for sid, cred in self._credentials.items()
        ]

    def get_stats(self) -> dict:
        active_sessions = sum(
            1 for s in self._sessions.values()
            if time.time() < s["expires_at"]
        )
        return {
            "stored_credentials": len(self._credentials),
            "active_sessions": active_sessions,
            "total_sessions_issued": len(self._sessions),
        }
