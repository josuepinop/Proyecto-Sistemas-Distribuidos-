from __future__ import annotations

import hashlib
import secrets
from typing import Dict, Optional


class AuthService:
    def __init__(self) -> None:
        self._sessions: Dict[str, str] = {}

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return AuthService.hash_password(password) == password_hash

    def create_token(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = username
        return token

    def get_username(self, token: str) -> Optional[str]:
        return self._sessions.get(token)
