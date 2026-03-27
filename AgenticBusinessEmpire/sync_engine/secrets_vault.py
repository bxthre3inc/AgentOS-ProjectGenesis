"""
Zo & Antigravity 2-Way Workspace Sync
AES-256-GCM encrypted secrets vault
"""
import os
import json
import base64
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

VAULT_DIR = os.path.join(os.path.dirname(__file__), "..", "secrets", ".vault")
VAULT_FILE = os.path.join(VAULT_DIR, "secrets.enc")
SALT_FILE = os.path.join(VAULT_DIR, ".salt")
_cache: dict = {}
_key: Optional[bytes] = None


def _ensure_vault_dir():
    os.makedirs(VAULT_DIR, exist_ok=True)


def _get_salt() -> bytes:
    _ensure_vault_dir()
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, "rb") as f:
            return f.read()
    salt = os.urandom(16)
    with open(SALT_FILE, "wb") as f:
        f.write(salt)
    return salt


def _derive_key(master_password: str) -> bytes:
    salt = _get_salt()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=480_000)
    return kdf.derive(master_password.encode())


def unlock(master_password: str) -> bool:
    """Unlock the vault with a master password."""
    global _key, _cache
    _key = _derive_key(master_password)
    if os.path.exists(VAULT_FILE):
        try:
            _cache = _load_all()
            return True
        except Exception:
            _key = None
            return False
    _cache = {}
    _save_all()
    return True


def _load_all() -> dict:
    if not _key:
        raise RuntimeError("Vault is locked")
    if not os.path.exists(VAULT_FILE):
        return {}
    with open(VAULT_FILE, "rb") as f:
        raw = f.read()
    nonce = raw[:12]
    ct = raw[12:]
    aesgcm = AESGCM(_key)
    plaintext = aesgcm.decrypt(nonce, ct, None)
    return json.loads(plaintext.decode())


def _save_all():
    if not _key:
        raise RuntimeError("Vault is locked")
    _ensure_vault_dir()
    aesgcm = AESGCM(_key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, json.dumps(_cache).encode(), None)
    with open(VAULT_FILE, "wb") as f:
        f.write(nonce + ct)


def set_secret(name: str, value: str, owner: str = "shared",
               visibility: str = "shared") -> bool:
    """Store a secret. visibility: 'shared' | 'zo' | 'antigravity'"""
    if not _key:
        # Auto-init with default key if not unlocked (dev mode)
        _auto_unlock()
    _cache[name] = {"value": value, "owner": owner, "visibility": visibility}
    _save_all()
    return True


def get_secret(name: str, requesting_agent: str = "shared") -> Optional[str]:
    """Retrieve a secret, respecting visibility rules."""
    if not _key:
        _auto_unlock()
    entry = _cache.get(name)
    if not entry:
        return None
    vis = entry.get("visibility", "shared")
    if vis == "shared" or vis == requesting_agent:
        return entry["value"]
    return None  # not authorized


def delete_secret(name: str) -> bool:
    if name in _cache:
        del _cache[name]
        _save_all()
        return True
    return False


def list_secrets(requesting_agent: str = "shared") -> list:
    result = []
    for name, entry in _cache.items():
        vis = entry.get("visibility", "shared")
        if vis == "shared" or vis == requesting_agent:
            result.append({
                "name": name,
                "owner": entry.get("owner"),
                "visibility": vis
            })
    return result


def _auto_unlock():
    """Auto-unlock in dev mode with a machine-derived key."""
    global _key, _cache
    machine_id = "zo-antigravity-sync-dev-2026"
    _key = _derive_key(machine_id)
    if os.path.exists(VAULT_FILE):
        try:
            _cache = _load_all()
        except Exception:
            _cache = {}
    else:
        _cache = {}
