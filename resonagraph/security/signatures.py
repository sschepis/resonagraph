"""
Signature management for beacon integrity.

According to NEXT_STEPS.md 6.2:
- Ed25519 signature implementation for beacon signing
- Signature verification before beacon processing
- Key rotation support (accept old + new keys)
- Signature key management per node
- Public key distribution via gossip
"""

import time
from typing import Dict, Optional, Set, Tuple
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


@dataclass
class SignatureKeyPair:
    """
    Ed25519 key pair for beacon signing.
    
    Attributes:
        private_key: Ed25519 private key
        public_key: Ed25519 public key
        key_id: Unique identifier for this key
        created_at: Timestamp when key was created
        expires_at: Timestamp when key expires (for rotation)
    """
    private_key: ed25519.Ed25519PrivateKey
    public_key: ed25519.Ed25519PublicKey
    key_id: str
    created_at: float
    expires_at: float


class SignatureKeyManager:
    """
    Manages Ed25519 key pairs for beacon signing and verification.
    
    According to NEXT_STEPS.md 6.2:
    - Generate Ed25519 key pairs per node
    - Distribute public keys via gossip
    - Key rotation and revocation
    - Accept old + new keys during rotation
    """
    
    def __init__(self, node_id: str, rotation_interval: float = 86400 * 30):
        """
        Initialize signature key manager.
        
        Args:
            node_id: Unique node identifier
            rotation_interval: Key rotation interval in seconds (default 30 days)
        """
        self.node_id = node_id
        self.rotation_interval = rotation_interval
        self._current_key: Optional[SignatureKeyPair] = None
        self._previous_key: Optional[SignatureKeyPair] = None
        self._trusted_keys: Dict[str, ed25519.Ed25519PublicKey] = {}  # key_id -> public key
        self._revoked_keys: Set[str] = set()
    
    def generate_key_pair(self) -> SignatureKeyPair:
        """
        Generate a new Ed25519 key pair.
        
        Returns:
            New key pair with metadata
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        now = time.time()
        # Use microseconds for uniqueness
        key_id = f"{self.node_id}:{int(now * 1000000)}"
        
        return SignatureKeyPair(
            private_key=private_key,
            public_key=public_key,
            key_id=key_id,
            created_at=now,
            expires_at=now + self.rotation_interval
        )
    
    def get_signing_key(self) -> ed25519.Ed25519PrivateKey:
        """
        Get the current signing key.
        
        Automatically rotates if needed.
        
        Returns:
            Current Ed25519 private key
        """
        if self._current_key is None or time.time() >= self._current_key.expires_at:
            self.rotate_key()
        
        return self._current_key.private_key
    
    def get_current_key_id(self) -> str:
        """
        Get the current key ID.
        
        Returns:
            Current key identifier
        """
        if self._current_key is None:
            self.rotate_key()
        
        return self._current_key.key_id
    
    def rotate_key(self) -> SignatureKeyPair:
        """
        Rotate to a new signing key.
        
        According to NEXT_STEPS.md 6.2:
        - Key rotation support (accept old + new keys)
        - Graceful transition period
        
        Returns:
            New key pair
        """
        # Move current to previous
        if self._current_key is not None:
            self._previous_key = self._current_key
            # Add previous public key to trusted keys
            self._trusted_keys[self._previous_key.key_id] = self._previous_key.public_key
        
        # Generate new key
        self._current_key = self.generate_key_pair()
        
        # Add new public key to trusted keys
        self._trusted_keys[self._current_key.key_id] = self._current_key.public_key
        
        return self._current_key
    
    def add_trusted_key(self, key_id: str, public_key: ed25519.Ed25519PublicKey) -> None:
        """
        Add a trusted public key from another node.
        
        Args:
            key_id: Key identifier
            public_key: Ed25519 public key
        """
        if key_id not in self._revoked_keys:
            self._trusted_keys[key_id] = public_key
    
    def revoke_key(self, key_id: str) -> None:
        """
        Revoke a key (mark as no longer trusted).
        
        Args:
            key_id: Key identifier to revoke
        """
        self._revoked_keys.add(key_id)
        if key_id in self._trusted_keys:
            del self._trusted_keys[key_id]
    
    def verify_signature(
        self,
        message: bytes,
        signature: bytes,
        key_id: Optional[str] = None,
        public_key: Optional[ed25519.Ed25519PublicKey] = None
    ) -> bool:
        """
        Verify an Ed25519 signature.
        
        According to NEXT_STEPS.md 6.2:
        - Verify beacon signatures before processing
        - Handle signature verification failures
        
        Args:
            message: Message that was signed
            signature: Ed25519 signature
            key_id: Optional key ID (looked up in trusted keys)
            public_key: Optional public key (used if key_id not provided)
            
        Returns:
            True if signature is valid, False otherwise
        """
        # Get public key
        verify_key = None
        if key_id is not None:
            if key_id in self._revoked_keys:
                return False
            verify_key = self._trusted_keys.get(key_id)
        elif public_key is not None:
            verify_key = public_key
        
        if verify_key is None:
            return False
        
        try:
            verify_key.verify(signature, message)
            return True
        except Exception:
            return False
    
    def export_public_key(self, key_id: Optional[str] = None) -> bytes:
        """
        Export a public key in PEM format.
        
        Args:
            key_id: Key ID to export (defaults to current key)
            
        Returns:
            PEM-encoded public key
        """
        if key_id is None:
            if self._current_key is None:
                self.rotate_key()
            public_key = self._current_key.public_key
        else:
            public_key = self._trusted_keys.get(key_id)
            if public_key is None:
                raise ValueError(f"Unknown key ID: {key_id}")
        
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def import_public_key(self, key_id: str, pem_data: bytes) -> None:
        """
        Import a public key from PEM format.
        
        Args:
            key_id: Key identifier
            pem_data: PEM-encoded public key
        """
        public_key = serialization.load_pem_public_key(pem_data)
        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            raise ValueError("Not an Ed25519 public key")
        
        self.add_trusted_key(key_id, public_key)
    
    def get_trusted_keys(self) -> Dict[str, ed25519.Ed25519PublicKey]:
        """
        Get all trusted public keys.
        
        Returns:
            Dictionary mapping key_id to public key
        """
        return dict(self._trusted_keys)
    
    def is_key_valid(self, key_id: str) -> bool:
        """
        Check if a key is valid (not revoked and trusted).
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if key is valid
        """
        return key_id in self._trusted_keys and key_id not in self._revoked_keys
