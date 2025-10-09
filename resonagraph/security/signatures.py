"""
Digital signature management for ResonaGraph beacons.

Implements Ed25519 signatures for beacon authentication and integrity
according to Phase 6B specifications.
"""

import os
import time
import hashlib
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from resonagraph.security.audit import AuditLogger, AuditEvent, AuditEventType


class SignatureAlgorithm(Enum):
    """Supported signature algorithms."""
    ED25519 = "ed25519"
    # Future: Post-quantum algorithms
    DILITHIUM = "dilithium"  # Placeholder for PQ transition


@dataclass
class SignatureKeyInfo:
    """Information about a signature key."""
    key_id: str
    algorithm: SignatureAlgorithm
    public_key_pem: str
    created_at: float
    expires_at: Optional[float] = None
    revoked: bool = False
    
    @property
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if key is valid (not expired or revoked)."""
        return not self.revoked and not self.is_expired


class SignatureError(Exception):
    """Base exception for signature operations."""
    pass


class SignatureVerificationError(SignatureError):
    """Raised when signature verification fails."""
    pass


class SignatureKeyError(SignatureError):
    """Raised when there's an issue with signature keys."""
    pass


class SignatureKeyManager:
    """
    Manages Ed25519 signature keys for beacon authentication.
    
    Handles key generation, storage, distribution, and rotation for
    cryptographic verification of beacons.
    """
    
    def __init__(
        self,
        node_id: str,
        audit_logger: Optional[AuditLogger] = None,
        key_rotation_interval: int = 30 * 24 * 3600  # 30 days
    ):
        """
        Initialize signature key manager.
        
        Args:
            node_id: Unique identifier for this node
            audit_logger: Audit logger for key operations
            key_rotation_interval: Automatic key rotation interval (seconds)
        """
        self.node_id = node_id
        self.audit_logger = audit_logger
        self.key_rotation_interval = key_rotation_interval
        
        # Local key storage
        self._private_key: Optional[ed25519.Ed25519PrivateKey] = None
        self._public_key: Optional[ed25519.Ed25519PublicKey] = None
        self._key_info: Optional[SignatureKeyInfo] = None
        
        # Known public keys from other nodes
        self._known_keys: Dict[str, SignatureKeyInfo] = {}
        
        # Revoked key tracking
        self._revoked_keys: set[str] = set()
        
        # Statistics
        self.stats = {
            'signatures_created': 0,
            'signatures_verified': 0,
            'verification_failures': 0,
            'keys_rotated': 0
        }
    
    def generate_key_pair(self, key_id: Optional[str] = None) -> str:
        """
        Generate a new Ed25519 key pair for this node.
        
        Args:
            key_id: Optional key identifier (auto-generated if None)
            
        Returns:
            Key ID of the generated key pair
        """
        if key_id is None:
            key_id = f"{self.node_id}:{int(time.time())}"
        
        # Generate Ed25519 key pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize public key for storage/distribution
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Store keys
        self._private_key = private_key
        self._public_key = public_key
        self._key_info = SignatureKeyInfo(
            key_id=key_id,
            algorithm=SignatureAlgorithm.ED25519,
            public_key_pem=public_key_pem,
            created_at=time.time(),
            expires_at=time.time() + self.key_rotation_interval
        )
        
        # Audit key generation
        if self.audit_logger:
            self.audit_logger.log_security_event(
                AuditEventType.KEY_CREATED,
                key_id,
                "success",
                actor=self.node_id,
                metadata={
                    "algorithm": SignatureAlgorithm.ED25519.value,
                    "key_type": "signature",
                    "expires_at": self._key_info.expires_at
                }
            )
        
        self.stats['keys_rotated'] += 1
        return key_id
    
    def sign_data(self, data: bytes) -> bytes:
        """
        Sign data with the current private key.
        
        Args:
            data: Data to sign
            
        Returns:
            Signature bytes
            
        Raises:
            SignatureKeyError: If no private key is available
        """
        if self._private_key is None:
            raise SignatureKeyError("No private key available for signing")
        
        if self._key_info and not self._key_info.is_valid:
            raise SignatureKeyError("Current key is expired or revoked")
        
        try:
            signature = self._private_key.sign(data)
            self.stats['signatures_created'] += 1
            
            # Audit signature creation
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.KEY_ACCESSED,
                    self._key_info.key_id if self._key_info else "unknown",
                    "success",
                    actor=self.node_id,
                    metadata={
                        "operation": "sign",
                        "data_size": len(data)
                    }
                )
            
            return signature
        
        except Exception as e:
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.SIGNATURE_FAILED,
                    self._key_info.key_id if self._key_info else "unknown",
                    "error",
                    actor=self.node_id,
                    metadata={"error": str(e)}
                )
            raise SignatureError(f"Failed to sign data: {e}")
    
    def verify_signature(
        self,
        data: bytes,
        signature: bytes,
        key_id: str,
        public_key_pem: Optional[str] = None
    ) -> bool:
        """
        Verify a signature against data.
        
        Args:
            data: Original data that was signed
            signature: Signature to verify
            key_id: ID of the key used for signing
            public_key_pem: Public key PEM (looked up if None)
            
        Returns:
            True if signature is valid
            
        Raises:
            SignatureVerificationError: If verification fails
        """
        try:
            # Check if key is revoked
            if key_id in self._revoked_keys:
                raise SignatureVerificationError(f"Key {key_id} is revoked")
            
            # Get public key
            if public_key_pem is None:
                if key_id in self._known_keys:
                    key_info = self._known_keys[key_id]
                    if not key_info.is_valid:
                        raise SignatureVerificationError(f"Key {key_id} is expired or revoked")
                    public_key_pem = key_info.public_key_pem
                else:
                    raise SignatureVerificationError(f"Unknown key: {key_id}")
            
            # Deserialize public key
            public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
            
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                raise SignatureVerificationError("Invalid Ed25519 public key")
            
            # Verify signature
            public_key.verify(signature, data)
            
            self.stats['signatures_verified'] += 1
            
            # Audit successful verification
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.BEACON_VERIFIED,
                    key_id,
                    "success",
                    metadata={
                        "data_size": len(data),
                        "signature_size": len(signature)
                    }
                )
            
            return True
        
        except InvalidSignature:
            self.stats['verification_failures'] += 1
            
            # Audit verification failure
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.SIGNATURE_FAILED,
                    key_id,
                    "failure",
                    metadata={
                        "reason": "invalid_signature",
                        "data_size": len(data)
                    }
                )
            
            return False
        
        except Exception as e:
            self.stats['verification_failures'] += 1
            
            # Audit verification error
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.SIGNATURE_FAILED,
                    key_id,
                    "error",
                    metadata={"error": str(e)}
                )
            
            raise SignatureVerificationError(f"Signature verification failed: {e}")
    
    def import_public_key(self, key_id: str, public_key_pem: str, expires_at: Optional[float] = None) -> None:
        """
        Import a public key from another node.
        
        Args:
            key_id: Key identifier
            public_key_pem: Public key in PEM format
            expires_at: Optional expiration time
        """
        try:
            # Validate the public key
            public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
            
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                raise ValueError("Not an Ed25519 public key")
            
            # Store key info
            key_info = SignatureKeyInfo(
                key_id=key_id,
                algorithm=SignatureAlgorithm.ED25519,
                public_key_pem=public_key_pem,
                created_at=time.time(),
                expires_at=expires_at
            )
            
            self._known_keys[key_id] = key_info
            
            # Audit key import
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.KEY_CREATED,
                    key_id,
                    "success",
                    metadata={
                        "operation": "import",
                        "algorithm": SignatureAlgorithm.ED25519.value
                    }
                )
        
        except Exception as e:
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.KEY_CREATED,
                    key_id,
                    "error",
                    metadata={
                        "operation": "import",
                        "error": str(e)
                    }
                )
            raise SignatureKeyError(f"Failed to import public key: {e}")
    
    def export_public_key(self) -> str:
        """
        Export the current public key for distribution.
        
        Returns:
            Public key in PEM format
            
        Raises:
            SignatureKeyError: If no public key is available
        """
        if self._key_info is None or self._public_key is None:
            raise SignatureKeyError("No public key available for export")
        
        return self._key_info.public_key_pem
    
    def get_key_info(self) -> Optional[SignatureKeyInfo]:
        """Get information about the current key."""
        return self._key_info
    
    def list_known_keys(self) -> Dict[str, SignatureKeyInfo]:
        """List all known public keys."""
        return self._known_keys.copy()
    
    def revoke_key(self, key_id: str) -> None:
        """
        Revoke a key (mark as invalid).
        
        Args:
            key_id: Key to revoke
        """
        self._revoked_keys.add(key_id)
        
        # Mark key as revoked if we know about it
        if key_id in self._known_keys:
            self._known_keys[key_id].revoked = True
        
        # Audit key revocation
        if self.audit_logger:
            self.audit_logger.log_security_event(
                AuditEventType.KEY_REVOKED,
                key_id,
                "success",
                actor=self.node_id
            )
    
    def rotate_key(self) -> str:
        """
        Rotate to a new key pair.
        
        Returns:
            New key ID
        """
        old_key_id = self._key_info.key_id if self._key_info else None
        
        # Generate new key
        new_key_id = self.generate_key_pair()
        
        # Audit key rotation
        if self.audit_logger:
            self.audit_logger.log_security_event(
                AuditEventType.KEY_ROTATED,
                new_key_id,
                "success",
                actor=self.node_id,
                metadata={
                    "old_key_id": old_key_id,
                    "rotation_interval": self.key_rotation_interval
                }
            )
        
        return new_key_id
    
    def needs_rotation(self) -> bool:
        """Check if the current key needs rotation."""
        if self._key_info is None:
            return True
        
        if self._key_info.expires_at is None:
            return False
        
        # Rotate 24 hours before expiration
        rotation_threshold = self._key_info.expires_at - (24 * 3600)
        return time.time() > rotation_threshold
    
    def get_stats(self) -> Dict[str, Any]:
        """Get signature manager statistics."""
        return self.stats.copy()
    
    def cleanup_expired_keys(self) -> int:
        """
        Remove expired keys from known keys.
        
        Returns:
            Number of keys cleaned up
        """
        expired_keys = []
        
        for key_id, key_info in self._known_keys.items():
            if key_info.is_expired:
                expired_keys.append(key_id)
        
        for key_id in expired_keys:
            del self._known_keys[key_id]
        
        if expired_keys and self.audit_logger:
            self.audit_logger.log_security_event(
                AuditEventType.KEY_REVOKED,
                "system",
                "success",
                metadata={
                    "operation": "cleanup_expired",
                    "keys_removed": len(expired_keys)
                }
            )
        
        return len(expired_keys)


class BeaconSigner:
    """
    High-level interface for signing and verifying beacon data.
    
    Integrates with SignatureKeyManager to provide beacon-specific
    signature operations.
    """
    
    def __init__(self, signature_manager: SignatureKeyManager):
        """
        Initialize beacon signer.
        
        Args:
            signature_manager: Signature key manager
        """
        self.signature_manager = signature_manager
    
    def sign_beacon_data(
        self,
        beacon_key: str,
        primes: list[int],
        phase_fingerprint: int,
        epoch: float,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bytes, str]:
        """
        Sign beacon metadata.
        
        Args:
            beacon_key: Beacon key
            primes: Selected primes
            phase_fingerprint: Phase fingerprint
            epoch: Beacon epoch
            additional_data: Optional additional data to include
            
        Returns:
            (signature_bytes, key_id) tuple
        """
        # Create canonical data representation for signing
        data_to_sign = self._create_beacon_hash(
            beacon_key, primes, phase_fingerprint, epoch, additional_data
        )
        
        # Sign the data
        signature = self.signature_manager.sign_data(data_to_sign)
        key_id = self.signature_manager.get_key_info().key_id
        
        return signature, key_id
    
    def verify_beacon_signature(
        self,
        beacon_key: str,
        primes: list[int],
        phase_fingerprint: int,
        epoch: float,
        signature: bytes,
        signer_key_id: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Verify beacon signature.
        
        Args:
            beacon_key: Beacon key
            primes: Selected primes
            phase_fingerprint: Phase fingerprint
            epoch: Beacon epoch
            signature: Signature to verify
            signer_key_id: ID of signing key
            additional_data: Optional additional data
            
        Returns:
            True if signature is valid
        """
        # Recreate the signed data
        data_to_verify = self._create_beacon_hash(
            beacon_key, primes, phase_fingerprint, epoch, additional_data
        )
        
        # Verify signature
        return self.signature_manager.verify_signature(
            data_to_verify, signature, signer_key_id
        )
    
    def _create_beacon_hash(
        self,
        beacon_key: str,
        primes: list[int],
        phase_fingerprint: int,
        epoch: float,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Create canonical hash of beacon data for signing.
        
        Args:
            beacon_key: Beacon key
            primes: Selected primes
            phase_fingerprint: Phase fingerprint
            epoch: Beacon epoch
            additional_data: Optional additional data
            
        Returns:
            SHA-256 hash of canonical beacon data
        """
        # Create canonical representation
        canonical_data = {
            "beacon_key": beacon_key,
            "primes": sorted(primes),  # Ensure deterministic ordering
            "phase_fingerprint": phase_fingerprint,
            "epoch": epoch,
            "additional_data": additional_data or {}
        }
        
        # Serialize to bytes (deterministic JSON)
        import json
        json_str = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
        
        # Return SHA-256 hash
        return hashlib.sha256(json_str.encode('utf-8')).digest()


# Factory function for easy setup
def create_signature_manager(
    node_id: str,
    audit_logger: Optional[AuditLogger] = None,
    auto_generate_key: bool = True
) -> SignatureKeyManager:
    """
    Create and initialize a signature manager.
    
    Args:
        node_id: Node identifier
        audit_logger: Optional audit logger
        auto_generate_key: Whether to generate initial key pair
        
    Returns:
        Configured signature manager
    """
    manager = SignatureKeyManager(node_id=node_id, audit_logger=audit_logger)
    
    if auto_generate_key:
        manager.generate_key_pair()
    
    return manager
