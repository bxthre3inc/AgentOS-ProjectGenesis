"""
security.py — AgenticBusinessEmpire Security & Encryption Layer
"""
import os
import json
import logging
from typing import Any, Optional
from cryptography.fernet import Fernet
from . import config

logger = logging.getLogger("agenticbusinessempire.core.security")

class SecureData:
    _cipher: Optional[Fernet] = None

    @classmethod
    def get_cipher(cls) -> Optional[Fernet]:
        if cls._cipher: return cls._cipher
        
        if not os.path.exists(config.ENCRYPTION_KEY_PATH):
            logger.warning("[Security] Ledger key missing. Data will be UNENCRYPTED.")
            return None
            
        with open(config.ENCRYPTION_KEY_PATH, 'rb') as f:
            cls._cipher = Fernet(f.read())
        return cls._cipher

    @classmethod
    def encrypt(cls, data: str) -> str:
        cipher = cls.get_cipher()
        if not cipher or not data: return data
        return cipher.encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, token: str) -> str:
        cipher = cls.get_cipher()
        if not cipher or not token: return token
        try:
            return cipher.decrypt(token.encode()).decode()
        except Exception:
            return token

    @classmethod
    def encrypt_json(cls, data: Any) -> str:
        return cls.encrypt(json.dumps(data))

    @classmethod
    def decrypt_json(cls, token: str) -> Any:
        raw = cls.decrypt(token)
        try:
            return json.loads(raw)
        except Exception:
            return raw
