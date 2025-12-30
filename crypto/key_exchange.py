import base64
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization


def generate_keypair():
    """Generate an X25519 keypair and return (priv_b64, pub_b64)."""
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return base64.b64encode(priv_bytes).decode('ascii'), base64.b64encode(pub_bytes).decode('ascii')

def derive_shared_key(priv_b64: str, peer_pub_b64: str) -> str:
    """Derive a 32-byte symmetric key via X25519 + HKDF-SHA256, return base64 string."""
    try:
        priv_bytes = base64.b64decode(priv_b64)
        peer_pub_bytes = base64.b64decode(peer_pub_b64)

        priv = x25519.X25519PrivateKey.from_private_bytes(priv_bytes)
        peer_pub = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)

        shared = priv.exchange(peer_pub)

        # Derive using HKDF to obtain AES-256 key material
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'peer-chat-shared-key'
        )
        key = hkdf.derive(shared)
        return base64.b64encode(key).decode('ascii')
    except Exception:
        return None
