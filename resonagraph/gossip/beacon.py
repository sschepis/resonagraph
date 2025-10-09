"""
Enhanced beacon structure with cryptographic signatures and integrity protection.

Updated to support Ed25519 signatures and HMAC-based phase chunk authentication
according to Phase 6B specifications.
"""

import time
import struct
import hashlib
import hmac
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from cryptography.hazmat.primitives.asymmetric import ed25519

from resonagraph.security.signatures import SignatureKeyManager, BeaconSigner
from resonagraph.security.integrity import IntegrityManager


# Time constants from design.md Section 2.2.1
TAU_EPOCH = 30.0  # τ = 30 seconds (beacon epoch duration)


@dataclass
class BeaconMetadata:
    """Enhanced metadata for a beacon."""
    key: str
    primes: List[int]
    epoch: float
    phase_fingerprint: int
    
    # Security fields
    signature: Optional[bytes] = None
    signer_key_id: Optional[str] = None
    chunk_macs: Optional[List[bytes]] = None
    
    # Optional fields
    node_id: Optional[str] = None
    ttl: int = 3
    created_at: Optional[float] = field(default_factory=time.time)
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.created_at is None:
            self.created_at = time.time()


class Beacon:
    """
    Enhanced beacon with cryptographic security.
    
    Integrates Ed25519 signatures and HMAC-based integrity protection
    for secure beacon verification in the gossip plane.
    """
    
    def __init__(
        self,
        key: str,
        primes: List[int],
        phase_angles: List[float],
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        mac_key: Optional[bytes] = None,
        node_id: Optional[str] = None,
        signature_manager: Optional[SignatureKeyManager] = None,
        integrity_manager: Optional[IntegrityManager] = None
    ):
        """
        Create a beacon with optional cryptographic protection.
        
        Args:
            key: Beacon key
            primes: Selected primes
            phase_angles: Phase angles for each prime
            signing_key: Ed25519 private key for signing (legacy)
            mac_key: HMAC key for phase chunk protection (legacy)
            node_id: Node identifier
            signature_manager: Signature manager for advanced signing
            integrity_manager: Integrity manager for MAC protection
        """
        self.key = key
        self.primes = primes
        self.phase_angles = phase_angles
        self.node_id = node_id
        self.epoch = time.time()
        
        # Security managers (new approach)
        self.signature_manager = signature_manager
        self.integrity_manager = integrity_manager
        
        # Legacy support
        self._signing_key = signing_key
        self._mac_key = mac_key
        
        # Computed fields
        self.phase_fingerprint = self._compute_phase_fingerprint()
        
        # Security fields
        self.signature: Optional[bytes] = None
        self.signer_key_id: Optional[str] = None
        self.chunk_macs: Optional[List[bytes]] = None
        
        # Apply security if managers are available
        if self.signature_manager:
            self._apply_signature()
        elif self._signing_key:
            self._apply_legacy_signature()
        
        if self.integrity_manager:
            self._apply_integrity_protection()
        elif self._mac_key:
            self._apply_legacy_mac()
    
    def _compute_phase_fingerprint(self) -> int:
        """
        Compute a fingerprint of the phase angles.
        
        Returns:
            64-bit fingerprint of phase angles
        """
        # Quantize phase angles to reduce precision
        quantized = []
        for angle in self.phase_angles:
            # Quantize to 16 bits (0-65535)
            quantized_angle = int((angle / (2 * 3.14159)) * 65535) & 0xFFFF
            quantized.append(quantized_angle)
        
        # Hash the quantized angles
        data = struct.pack(f'>{len(quantized)}H', *quantized)
        hash_value = hashlib.sha256(data).digest()
        
        # Return first 64 bits as fingerprint
        return struct.unpack('>Q', hash_value[:8])[0]
    
    def _apply_signature(self) -> None:
        """Apply signature using signature manager."""
        if not self.signature_manager:
            return
        
        signer = BeaconSigner(self.signature_manager)
        
        try:
            signature, key_id = signer.sign_beacon_data(
                beacon_key=self.key,
                primes=self.primes,
                phase_fingerprint=self.phase_fingerprint,
                epoch=self.epoch,
                additional_data={"node_id": self.node_id} if self.node_id else None
            )
            
            self.signature = signature
            self.signer_key_id = key_id
        
        except Exception:
            # Signing failed, beacon will be unsigned
            pass
    
    def _apply_legacy_signature(self) -> None:
        """Apply signature using legacy signing key."""
        if not self._signing_key:
            return
        
        try:
            # Create data to sign (legacy format)
            data_to_sign = self._create_legacy_signature_data()
            signature = self._signing_key.sign(data_to_sign)
            
            self.signature = signature
            self.signer_key_id = f"legacy:{self.node_id or 'unknown'}"
        
        except Exception:
            # Signing failed, beacon will be unsigned
            pass
    
    def _apply_integrity_protection(self) -> None:
        """Apply integrity protection using integrity manager."""
        if not self.integrity_manager:
            return
        
        try:
            # Create phase chunks for MAC computation
            phase_chunks = []
            for i, (prime, angle) in enumerate(zip(self.primes, self.phase_angles)):
                # Convert phase angle to bytes
                angle_bytes = struct.pack('>f', angle)
                phase_chunks.append((angle_bytes, i, prime))
            
            # Compute MACs
            chunk_macs = self.integrity_manager.create_protected_chunks(
                beacon_key=self.key,
                epoch=self.epoch,
                phase_chunks=phase_chunks
            )
            
            self.chunk_macs = chunk_macs
        
        except Exception:
            # MAC computation failed
            pass
    
    def _apply_legacy_mac(self) -> None:
        """Apply MAC protection using legacy MAC key."""
        if not self._mac_key:
            return
        
        try:
            chunk_macs = []
            
            for i, (prime, angle) in enumerate(zip(self.primes, self.phase_angles)):
                # Create message to authenticate
                angle_bytes = struct.pack('>f', angle)
                message = (
                    angle_bytes +
                    i.to_bytes(4, 'big') +
                    prime.to_bytes(8, 'big') +
                    self.key.encode('utf-8')
                )
                
                # Compute HMAC
                mac = hmac.new(self._mac_key, message, hashlib.sha256).digest()
                chunk_macs.append(mac)
            
            self.chunk_macs = chunk_macs
        
        except Exception:
            # MAC computation failed
            pass
    
    def verify_signature(
        self,
        public_key: Optional[ed25519.Ed25519PublicKey] = None,
        signature_manager: Optional[SignatureKeyManager] = None
    ) -> bool:
        """
        Verify the beacon signature.
        
        Args:
            public_key: Ed25519 public key for verification (legacy)
            signature_manager: Signature manager for verification
            
        Returns:
            True if signature is valid
        """
        if not self.signature or not self.signer_key_id:
            return False
        
        try:
            # Use signature manager if available
            if signature_manager:
                signer = BeaconSigner(signature_manager)
                return signer.verify_beacon_signature(
                    beacon_key=self.key,
                    primes=self.primes,
                    phase_fingerprint=self.phase_fingerprint,
                    epoch=self.epoch,
                    signature=self.signature,
                    signer_key_id=self.signer_key_id,
                    additional_data={"node_id": self.node_id} if self.node_id else None
                )
            
            # Legacy verification
            elif public_key and self.signer_key_id.startswith("legacy:"):
                data_to_verify = self._create_legacy_signature_data()
                public_key.verify(self.signature, data_to_verify)
                return True
            
            return False
        
        except Exception:
            return False
    
    def verify_integrity(
        self,
        integrity_manager: Optional[IntegrityManager] = None,
        mac_key: Optional[bytes] = None
    ) -> bool:
        """
        Verify beacon integrity (replay protection + MAC).
        
        Args:
            integrity_manager: Integrity manager for verification
            mac_key: MAC key for legacy verification
            
        Returns:
            True if integrity is valid
        """
        if not self.chunk_macs:
            return False
        
        try:
            # Use integrity manager if available
            if integrity_manager:
                # Create phase chunks for verification
                phase_chunks = []
                for i, (prime, angle) in enumerate(zip(self.primes, self.phase_angles)):
                    angle_bytes = struct.pack('>f', angle)
                    phase_chunks.append((angle_bytes, i, prime))
                
                return integrity_manager.verify_beacon_integrity(
                    beacon_key=self.key,
                    epoch=self.epoch,
                    phase_chunks=phase_chunks,
                    chunk_macs=self.chunk_macs,
                    node_id=self.node_id,
                    signature_key_id=self.signer_key_id
                )
            
            # Legacy MAC verification
            elif mac_key:
                return self._verify_legacy_macs(mac_key)
            
            return False
        
        except Exception:
            return False
    
    def _verify_legacy_macs(self, mac_key: bytes) -> bool:
        """Verify MACs using legacy method."""
        if not self.chunk_macs or len(self.chunk_macs) != len(self.phase_angles):
            return False
        
        try:
            for i, (prime, angle, expected_mac) in enumerate(zip(
                self.primes, self.phase_angles, self.chunk_macs
            )):
                # Recompute MAC
                angle_bytes = struct.pack('>f', angle)
                message = (
                    angle_bytes +
                    i.to_bytes(4, 'big') +
                    prime.to_bytes(8, 'big') +
                    self.key.encode('utf-8')
                )
                
                computed_mac = hmac.new(mac_key, message, hashlib.sha256).digest()
                
                # Use constant-time comparison
                if not hmac.compare_digest(computed_mac, expected_mac):
                    return False
            
            return True
        
        except Exception:
            return False
    
    def _create_legacy_signature_data(self) -> bytes:
        """Create data for legacy signature computation."""
        # Include key, primes, epoch, and fingerprint
        data_parts = [
            self.key.encode('utf-8'),
            struct.pack('>Q', self.phase_fingerprint),
            struct.pack('>d', self.epoch),
        ]
        
        # Add primes
        for prime in self.primes:
            data_parts.append(struct.pack('>Q', prime))
        
        return b''.join(data_parts)
    
    def size(self) -> int:
        """
        Calculate beacon size in bytes.
        
        Returns:
            Total beacon size including security fields
        """
        base_size = (
            32 +                              # Key hash
            len(self.primes) * 4 +           # Prime indices
            len(self.phase_angles) * 4 +     # Phase angles  
            8 +                              # Epoch
            8 +                              # Phase fingerprint
            4                                # TTL
        )
        
        # Add security field sizes
        if self.signature:
            base_size += 64  # Ed25519 signature
        
        if self.signer_key_id:
            base_size += len(self.signer_key_id.encode('utf-8'))
        
        if self.chunk_macs:
            base_size += len(self.chunk_macs) * 32  # SHA256 MACs
        
        if self.node_id:
            base_size += len(self.node_id.encode('utf-8'))
        
        return base_size
    
    def serialize(self) -> bytes:
        """
        Serialize beacon to bytes.
        
        Returns:
            Serialized beacon data
        """
        # Create beacon metadata for serialization
        metadata = BeaconMetadata(
            key=self.key,
            primes=self.primes,
            epoch=self.epoch,
            phase_fingerprint=self.phase_fingerprint,
            signature=self.signature,
            signer_key_id=self.signer_key_id,
            chunk_macs=self.chunk_macs,
            node_id=self.node_id
        )
        
        # Simple serialization (in production, use protobuf or similar)
        import pickle
        return pickle.dumps({
            'metadata': metadata,
            'phase_angles': self.phase_angles
        })
    
    @classmethod
    def deserialize(
        cls,
        data: bytes,
        verify_key: Optional[ed25519.Ed25519PublicKey] = None,
        signature_manager: Optional[SignatureKeyManager] = None,
        integrity_manager: Optional[IntegrityManager] = None
    ) -> 'Beacon':
        """
        Deserialize beacon from bytes.
        
        Args:
            data: Serialized beacon data
            verify_key: Ed25519 public key for verification (legacy)
            signature_manager: Signature manager for verification
            integrity_manager: Integrity manager for verification
            
        Returns:
            Deserialized beacon
            
        Raises:
            ValueError: If deserialization fails
            SecurityError: If signature/integrity verification fails
        """
        try:
            import pickle
            serialized = pickle.loads(data)
            
            metadata = serialized['metadata']
            phase_angles = serialized['phase_angles']
            
            # Create beacon
            beacon = cls(
                key=metadata.key,
                primes=metadata.primes,
                phase_angles=phase_angles,
                node_id=metadata.node_id,
                signature_manager=signature_manager,
                integrity_manager=integrity_manager
            )
            
            # Restore security fields
            beacon.epoch = metadata.epoch
            beacon.phase_fingerprint = metadata.phase_fingerprint
            beacon.signature = metadata.signature
            beacon.signer_key_id = metadata.signer_key_id
            beacon.chunk_macs = metadata.chunk_macs
            
            # Verify signature if present
            if beacon.signature and not beacon.verify_signature(verify_key, signature_manager):
                raise SecurityError("Signature verification failed")
            
            # Verify integrity if present  
            if beacon.chunk_macs and integrity_manager:
                if not beacon.verify_integrity(integrity_manager):
                    raise SecurityError("Integrity verification failed")
            
            return beacon
        
        except Exception as e:
            raise ValueError(f"Failed to deserialize beacon: {e}")
    
    def __repr__(self) -> str:
        """String representation of beacon."""
        security_info = []
        if self.signature:
            security_info.append("signed")
        if self.chunk_macs:
            security_info.append("mac-protected")
        
        security_str = f" ({', '.join(security_info)})" if security_info else ""
        
        return (
            f"Beacon(key={self.key}, epoch={self.epoch:.1f}, "
            f"primes={len(self.primes)}, fingerprint={self.phase_fingerprint:016x}"
            f"{security_str})"
        )


class SecurityError(Exception):
    """Raised when beacon security verification fails."""
    pass


# Factory functions for easy beacon creation

def create_signed_beacon(
    key: str,
    primes: List[int],
    phase_angles: List[float],
    signature_manager: SignatureKeyManager,
    node_id: Optional[str] = None
) -> Beacon:
    """
    Create a beacon with signature protection.
    
    Args:
        key: Beacon key
        primes: Selected primes
        phase_angles: Phase angles
        signature_manager: Signature manager
        node_id: Optional node ID
        
    Returns:
        Signed beacon
    """
    return Beacon(
        key=key,
        primes=primes,
        phase_angles=phase_angles,
        signature_manager=signature_manager,
        node_id=node_id
    )


def create_secure_beacon(
    key: str,
    primes: List[int],
    phase_angles: List[float],
    signature_manager: SignatureKeyManager,
    integrity_manager: IntegrityManager,
    node_id: Optional[str] = None
) -> Beacon:
    """
    Create a beacon with full security protection (signature + integrity).
    
    Args:
        key: Beacon key
        primes: Selected primes
        phase_angles: Phase angles
        signature_manager: Signature manager
        integrity_manager: Integrity manager
        node_id: Optional node ID
        
    Returns:
        Fully secured beacon
    """
    return Beacon(
        key=key,
        primes=primes,
        phase_angles=phase_angles,
        signature_manager=signature_manager,
        integrity_manager=integrity_manager,
        node_id=node_id
    )
