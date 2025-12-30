from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional


ENC_PREFIX = "ENC1:AES256GCM:"  # stable prefix to detect encrypted payloads


def _require_cryptography():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency 'cryptography'. Install with: pip install -r requirements.txt"
        ) from e


def derive_aes256_key(key_material: Optional[str]) -> Optional[bytes]:
    """Return 32-byte key for AES-256.

    Accepts either:
    - base64-encoded 32 bytes (recommended), or
    - a passphrase/string (will be SHA-256 hashed into 32 bytes)
    """
    if not key_material:
        return None

    key_material = str(key_material).strip()
    if not key_material:
        return None

    # Try base64 first
    try:
        raw = base64.b64decode(key_material, validate=True)
        if len(raw) == 32:
            return raw
    except Exception:
        pass

    # Fallback: derive key from passphrase
    return hashlib.sha256(key_material.encode("utf-8")).digest()


def encrypt_text(plaintext: str, key: bytes) -> str:
    """Encrypt UTF-8 plaintext to a printable string.

    Output format: ENC_PREFIX + base64(nonce || ciphertext_with_tag)
    """
    _require_cryptography()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if plaintext is None:
        plaintext = ""

    if not isinstance(key, (bytes, bytearray)) or len(key) != 32:
        raise ValueError("AES-256 key must be exactly 32 bytes")

    nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    token = base64.b64encode(nonce + ct).decode("ascii")
    return f"{ENC_PREFIX}{token}"


def decrypt_text(payload: str, key: bytes) -> str:
    """Decrypt payload if it looks encrypted; otherwise return as-is.

    - If payload doesn't start with ENC_PREFIX: return payload unchanged.
    - If decrypt fails (wrong key/corrupt): raise ValueError.
    """
    _require_cryptography()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if payload is None:
        return ""
    if not isinstance(payload, str):
        # Keep backward compatibility in case content is dict/other types
        return str(payload)

    if not payload.startswith(ENC_PREFIX):
        return payload

    if not isinstance(key, (bytes, bytearray)) or len(key) != 32:
        raise ValueError("AES-256 key must be exactly 32 bytes")

    token = payload[len(ENC_PREFIX) :]
    try:
        raw = base64.b64decode(token, validate=True)
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(key)
        pt = aesgcm.decrypt(nonce, ct, None)
        return pt.decode("utf-8")
    except Exception as e:
        raise ValueError("Failed to decrypt payload (wrong key or corrupted data)") from e


# Backward-compatible names (used elsewhere in repo historically)
def encrypt(text: str) -> str:  # pragma: no cover
    """Deprecated: use encrypt_text(plaintext, key)."""
    return text


def decrypt(text: str) -> str:  # pragma: no cover
    """Deprecated: use decrypt_text(payload, key)."""
    return text
