"""
Phase key management for cryptographic access control.

According to copilot-instructions.md Section 5:
- Root K_root derives per-topic K_topic via HKDF
- Rotate keys every 24h for security
- Without correct phase key K, probes misalign (R < R_min)
"""

import hashlib
import hmac
import secrets
from typing import Optional


class PhaseKey:
    """
    Manages cryptographic phase keys for access control.
    
    According to design.md Section 6.1:
    - Enforcement: Without K, probes misalign
    - Key Hierarchy: K_root derives K_topic via HKDF
    - Rotate every 24h
    """
    
    KEY_SIZE = 32  # 256 bits
    
    def __init__(self, key_bytes: bytes):
        """
        Initialize a phase key from raw bytes.
        
        Args:
            key_bytes: Raw key material (should be 32 bytes)
        """
        if len(key_bytes) != self.KEY_SIZE:
            raise ValueError(f"Key must be exactly {self.KEY_SIZE} bytes")
        self._key = key_bytes
    
    @classmethod
    def from_secret(cls, secret: bytes) -> "PhaseKey":
        """
        Create a phase key from a secret.
        
        Args:
            secret: Secret bytes (will be hashed to proper size)
            
        Returns:
            PhaseKey instance
        """
        # Hash secret to get key material
        key_bytes = hashlib.sha256(secret).digest()
        return cls(key_bytes)
    
    @classmethod
    def generate(cls) -> "PhaseKey":
        """
        Generate a new random phase key.
        
        Returns:
            PhaseKey instance with cryptographically secure random bytes
        """
        key_bytes = secrets.token_bytes(cls.KEY_SIZE)
        return cls(key_bytes)
    
    @classmethod
    def derive_topic_key(
        cls,
        root_key: "PhaseKey",
        topic: str,
        salt: Optional[bytes] = None
    ) -> "PhaseKey":
        """
        Derive a per-topic key from root key using HKDF.
        
        According to design.md Section 6.1:
        K_root derives per-topic K_topic via HKDF
        
        Args:
            root_key: Root phase key
            topic: Topic string for key derivation
            salt: Optional salt (random if not provided)
            
        Returns:
            Derived topic key
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        # HKDF Extract: PRK = HMAC-Hash(salt, IKM)
        prk = hmac.new(salt, root_key._key, hashlib.sha256).digest()
        
        # HKDF Expand: OKM = HMAC-Hash(PRK, info || 0x01)
        info = topic.encode('utf-8')
        okm = hmac.new(prk, info + b'\x01', hashlib.sha256).digest()
        
        return cls(okm)
    
    def get_bytes(self) -> bytes:
        """
        Get the raw key bytes.
        
        Returns:
            Raw key material
        """
        return self._key
    
    def __repr__(self) -> str:
        """String representation (does not reveal key)."""
        return f"PhaseKey(***hidden***)"
    
    def __eq__(self, other: object) -> bool:
        """
        Compare keys in constant time.
        
        According to copilot-instructions.md:
        Use constant-time comparisons for security-critical paths
        """
        if not isinstance(other, PhaseKey):
            return False
        
        # Constant-time comparison using hmac.compare_digest
        return hmac.compare_digest(self._key, other._key)
    
    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash(self._key)
