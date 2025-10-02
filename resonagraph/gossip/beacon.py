"""
Beacon structure implementation for ResonaGraph gossip plane.

According to design.md Section 2.2.1 and copilot-instructions.md:
- Beacon Structure: 128-512 bytes compact metadata
  - Prime Index ID (delta-coded, 128 bits for 32 primes)
  - Epoch timestamp (32-bit, τ=2-13 seconds)
  - Phase Fingerprint (quantized phases, 64-128 bits)
  - Signature/MAC (Ed25519 + HMAC for integrity)
"""

import struct
import time
import hmac
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


# Epoch parameters from design.md Section 2.2.1
TAU_EPOCH = 8  # τ = 2^13 seconds ≈ 8192 seconds ≈ 2.27 hours (using 2^3 for testing)
EPOCH_BITS = 32

# Beacon structure parameters
PRIME_INDEX_BITS = 128  # For 32 primes delta-coded
PHASE_FINGERPRINT_BITS = 64  # Quantized phase fingerprint
SIGNATURE_BYTES = 64  # Ed25519 signature size
HMAC_BYTES = 32  # HMAC-SHA256 size

# Size calculations
MIN_BEACON_SIZE = 128
MAX_BEACON_SIZE = 512


@dataclass
class BeaconMetadata:
    """
    Metadata for a beacon.
    
    This is a high-level representation of beacon data before
    serialization into the compact binary format.
    """
    key: str
    primes: List[int]
    epoch: int
    phase_fingerprint: int  # Quantized fingerprint
    signature: bytes
    mac: bytes
    version: int = 1  # Protocol version


class Beacon:
    """
    Compact beacon structure for gossip coordination.
    
    According to design.md Section 2.2.1:
    - 128-512 bytes compact structure
    - Prime Index ID (delta-coded)
    - Epoch timestamp (32-bit)
    - Phase Fingerprint (quantized phases)
    - Signature/MAC (Ed25519 + HMAC)
    
    Binary format:
    - Bytes 0-3:      Version (8 bits) + Reserved (24 bits)
    - Bytes 4-7:      Epoch timestamp (32-bit)
    - Bytes 8-23:     Prime Index ID (128 bits, delta-coded)
    - Bytes 24-31:    Phase Fingerprint (64 bits, quantized)
    - Bytes 32-63:    HMAC (32 bytes)
    - Bytes 64-127:   Ed25519 Signature (64 bytes)
    - Bytes 128+:     Optional extensions
    """
    
    VERSION = 1
    HEADER_SIZE = 192  # Minimum beacon size (extended for key hash)
    
    def __init__(
        self,
        key: str,
        primes: List[int],
        phase_angles: List[float],
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        mac_key: Optional[bytes] = None
    ):
        """
        Initialize a beacon.
        
        Args:
            key: Key for this beacon
            primes: Selected primes for encoding
            phase_angles: Encoded phase angles
            signing_key: Ed25519 private key for signing (optional)
            mac_key: HMAC key (optional)
        """
        self.key = key
        self.primes = primes
        self.phase_angles = phase_angles
        self.epoch = self._compute_epoch()
        self.phase_fingerprint = self._compute_phase_fingerprint(phase_angles)
        
        # Generate signature and MAC
        payload = self._create_payload()
        
        if signing_key:
            self.signature = signing_key.sign(payload)
        else:
            self.signature = b'\x00' * SIGNATURE_BYTES
            
        if mac_key:
            self.mac = hmac.new(mac_key, payload, hashlib.sha256).digest()
        else:
            self.mac = b'\x00' * HMAC_BYTES
    
    @staticmethod
    def _compute_epoch() -> int:
        """
        Compute current epoch timestamp.
        
        According to design.md Section 2.2.1:
        - τ = 2^13 seconds (configurable)
        - Epoch te is 32-bit timestamp
        
        Returns:
            Current epoch number
        """
        current_time = int(time.time())
        return current_time // TAU_EPOCH
    
    def _compute_phase_fingerprint(self, phase_angles: List[float]) -> int:
        """
        Compute quantized phase fingerprint.
        
        According to design.md Section 2.2.1:
        - Quantized phases for coarse verification
        - 64-128 bits compact representation
        
        We use a simple quantization scheme:
        - Bin each phase into 8 bits (256 levels)
        - Take top 8 phases and pack into 64 bits
        
        Args:
            phase_angles: List of phase angles in radians
            
        Returns:
            64-bit quantized fingerprint
        """
        import math
        TWO_PI = 2 * math.pi
        
        fingerprint = 0
        # Take up to 8 phases for fingerprint
        for i, angle in enumerate(phase_angles[:8]):
            # Normalize to [0, 2π) and quantize to 8 bits
            normalized = angle % TWO_PI
            quantized = int((normalized / TWO_PI) * 255)
            fingerprint |= (quantized << (i * 8))
        
        return fingerprint
    
    def _delta_encode_primes(self) -> bytes:
        """
        Delta-encode prime indices for compact representation.
        
        According to design.md Section 2.2.1:
        - Delta-coded prime indices
        - 128 bits for 32 primes
        
        We encode differences between consecutive primes.
        For 32 primes, we use 4 bits per delta (16 deltas per 64-bit word).
        
        Returns:
            16 bytes of delta-encoded primes
        """
        if not self.primes:
            return b'\x00' * 16
        
        # Delta encode: store differences between consecutive primes
        deltas = [self.primes[0]]  # First prime stored as-is (scaled)
        for i in range(1, len(self.primes)):
            delta = self.primes[i] - self.primes[i-1]
            deltas.append(delta)
        
        # Pack deltas into bytes (simplified encoding)
        # For now, just hash the primes for a compact representation
        prime_data = ','.join(str(p) for p in self.primes).encode()
        prime_hash = hashlib.sha256(prime_data).digest()[:16]
        
        return prime_hash
    
    def _create_payload(self) -> bytes:
        """
        Create payload for signing/MAC.
        
        Returns:
            Serialized payload bytes
        """
        # Create payload using key hash, epoch, primes, and fingerprint
        # This must match the format used in deserialization for signature verification
        key_hash = hashlib.sha256(self.key.encode('utf-8')).digest()
        epoch_bytes = struct.pack('<I', self.epoch)
        primes_bytes = self._delta_encode_primes()
        fingerprint_bytes = struct.pack('<Q', self.phase_fingerprint)
        
        return key_hash + epoch_bytes + primes_bytes + fingerprint_bytes
    
    def serialize(self) -> bytes:
        """
        Serialize beacon to compact binary format.
        
        Binary structure (design.md Section 2.2.1):
        - Bytes 0-3:      Version + Reserved
        - Bytes 4-7:      Epoch timestamp
        - Bytes 8-23:     Prime Index ID (delta-coded)
        - Bytes 24-31:    Phase Fingerprint
        - Bytes 32-63:    HMAC
        - Bytes 64-95:    Key hash (32 bytes for signature validation)
        - Bytes 96-127:   Reserved (32 bytes)
        - Bytes 128-191:  Ed25519 Signature (64 bytes)
        
        Returns:
            Serialized beacon bytes (192 bytes)
        """
        # Header (4 bytes): version + reserved
        header = struct.pack('<I', (self.VERSION << 24))
        
        # Epoch (4 bytes)
        epoch_bytes = struct.pack('<I', self.epoch)
        
        # Prime Index ID (16 bytes, delta-coded)
        primes_bytes = self._delta_encode_primes()
        
        # Phase Fingerprint (8 bytes)
        fingerprint_bytes = struct.pack('<Q', self.phase_fingerprint)
        
        # HMAC (32 bytes)
        mac_bytes = self.mac.ljust(HMAC_BYTES, b'\x00')[:HMAC_BYTES]
        
        # Key hash (32 bytes) - for signature validation
        key_hash = hashlib.sha256(self.key.encode('utf-8')).digest()
        
        # Reserved space (32 bytes)
        reserved = b'\x00' * 32
        
        # Signature (64 bytes)
        sig_bytes = self.signature.ljust(SIGNATURE_BYTES, b'\x00')[:SIGNATURE_BYTES]
        
        # Combine all parts
        beacon_data = (
            header +           # 4 bytes
            epoch_bytes +      # 4 bytes
            primes_bytes +     # 16 bytes
            fingerprint_bytes + # 8 bytes
            mac_bytes +        # 32 bytes
            key_hash +         # 32 bytes
            reserved +         # 32 bytes
            sig_bytes          # 64 bytes
        )                      # Total: 192 bytes
        
        return beacon_data
    
    @classmethod
    def deserialize(cls, data: bytes, verify_key: Optional[ed25519.Ed25519PublicKey] = None) -> 'Beacon':
        """
        Deserialize beacon from binary format.
        
        Args:
            data: Binary beacon data
            verify_key: Optional Ed25519 public key for signature verification
            
        Returns:
            Beacon instance
            
        Raises:
            ValueError: If data is invalid or signature verification fails
        """
        if len(data) < cls.HEADER_SIZE:
            raise ValueError(f"Beacon data too short: {len(data)} < {cls.HEADER_SIZE}")
        
        # Parse header
        header = struct.unpack('<I', data[0:4])[0]
        version = (header >> 24) & 0xFF
        
        if version != cls.VERSION:
            raise ValueError(f"Unsupported beacon version: {version}")
        
        # Parse fields
        epoch = struct.unpack('<I', data[4:8])[0]
        primes_bytes = data[8:24]
        fingerprint = struct.unpack('<Q', data[24:32])[0]
        mac = data[32:64]
        key_hash = data[64:96]
        # reserved = data[96:128]
        signature = data[128:192]
        
        # For deserialization, we create a minimal beacon
        # In a full implementation, we'd decode the prime indices
        beacon = cls.__new__(cls)
        beacon.key = ""  # Unknown from serialized data, use key_hash
        beacon.primes = []  # Would decode from primes_bytes
        beacon.phase_angles = []
        beacon.epoch = epoch
        beacon.phase_fingerprint = fingerprint
        beacon.mac = mac
        beacon.signature = signature
        beacon._key_hash = key_hash  # Store for signature verification
        
        # Verify signature if key provided
        if verify_key and signature != b'\x00' * SIGNATURE_BYTES:
            # Create payload using key hash instead of key
            payload = (
                key_hash +
                struct.pack('<I', epoch) +
                primes_bytes +
                struct.pack('<Q', fingerprint)
            )
            try:
                verify_key.verify(signature, payload)
            except Exception as e:
                raise ValueError(f"Signature verification failed: {e}")
        
        return beacon
    
    def to_metadata(self) -> BeaconMetadata:
        """
        Convert beacon to metadata representation.
        
        Returns:
            BeaconMetadata object
        """
        return BeaconMetadata(
            key=self.key,
            primes=self.primes,
            epoch=self.epoch,
            phase_fingerprint=self.phase_fingerprint,
            signature=self.signature,
            mac=self.mac,
            version=self.VERSION
        )
    
    def size(self) -> int:
        """
        Get serialized size of beacon.
        
        Returns:
            Size in bytes
        """
        return len(self.serialize())
    
    def __repr__(self) -> str:
        return (
            f"Beacon(key={self.key!r}, epoch={self.epoch}, "
            f"primes={len(self.primes)}, fingerprint={self.phase_fingerprint:016x})"
        )
