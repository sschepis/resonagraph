"""
Delta encoding for ResonaGraph beacons.

Implements delta encoding for prime indices and phase quantization
to minimize beacon size while preserving essential information.

- Prime indices: Delta-coded differences (128 bits → ~32 bits)
- Phase fingerprints: Quantized to 64-128 bits
"""

import struct
import numpy as np
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class DeltaEncoder:
    """
    Delta encoder for prime indices.
    
    Stores differences between consecutive primes instead of
    absolute values, achieving significant compression.
    """
    
    # Encoding formats
    VARINT = 0  # Variable-length integer encoding
    FIXED8 = 1  # Fixed 8-bit deltas
    FIXED16 = 2  # Fixed 16-bit deltas
    
    def __init__(self, encoding_format: int = VARINT):
        """
        Initialize delta encoder.
        
        Args:
            encoding_format: Encoding format for deltas
        """
        self.encoding_format = encoding_format
    
    def encode(self, prime_indices: List[int]) -> bytes:
        """
        Delta-encode prime indices.
        
        Args:
            prime_indices: List of prime indices (sorted)
            
        Returns:
            Delta-encoded bytes
        """
        if not prime_indices:
            return b''
        
        # Compute deltas
        deltas = [prime_indices[0]]  # First value absolute
        for i in range(1, len(prime_indices)):
            delta = prime_indices[i] - prime_indices[i-1]
            deltas.append(delta)
        
        # Encode based on format
        if self.encoding_format == self.VARINT:
            return self._encode_varint(deltas)
        elif self.encoding_format == self.FIXED8:
            return self._encode_fixed8(deltas)
        elif self.encoding_format == self.FIXED16:
            return self._encode_fixed16(deltas)
        else:
            raise ValueError(f"Unknown encoding format: {self.encoding_format}")
    
    def decode(self, encoded: bytes) -> List[int]:
        """
        Decode delta-encoded prime indices.
        
        Args:
            encoded: Delta-encoded bytes
            
        Returns:
            List of prime indices
        """
        if not encoded:
            return []
        
        # Decode based on format marker
        if self.encoding_format == self.VARINT:
            deltas = self._decode_varint(encoded)
        elif self.encoding_format == self.FIXED8:
            deltas = self._decode_fixed8(encoded)
        elif self.encoding_format == self.FIXED16:
            deltas = self._decode_fixed16(encoded)
        else:
            raise ValueError(f"Unknown encoding format: {self.encoding_format}")
        
        # Reconstruct absolute values
        if not deltas:
            return []
        
        indices = [deltas[0]]
        for delta in deltas[1:]:
            indices.append(indices[-1] + delta)
        
        return indices
    
    def _encode_varint(self, deltas: List[int]) -> bytes:
        """Encode deltas as variable-length integers."""
        result = bytearray()
        
        for delta in deltas:
            # Encode as varint (7 bits per byte, MSB = continuation)
            while delta >= 128:
                result.append((delta & 0x7F) | 0x80)
                delta >>= 7
            result.append(delta & 0x7F)
        
        return bytes(result)
    
    def _decode_varint(self, encoded: bytes) -> List[int]:
        """Decode variable-length integer deltas."""
        deltas = []
        value = 0
        shift = 0
        
        for byte in encoded:
            value |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                deltas.append(value)
                value = 0
                shift = 0
            else:
                shift += 7
        
        return deltas
    
    def _encode_fixed8(self, deltas: List[int]) -> bytes:
        """Encode deltas as fixed 8-bit values."""
        # Check if all deltas fit in 8 bits
        if any(d < 0 or d > 255 for d in deltas):
            raise ValueError("Deltas too large for 8-bit encoding")
        
        return bytes(deltas)
    
    def _decode_fixed8(self, encoded: bytes) -> List[int]:
        """Decode fixed 8-bit deltas."""
        return list(encoded)
    
    def _encode_fixed16(self, deltas: List[int]) -> bytes:
        """Encode deltas as fixed 16-bit values."""
        result = bytearray()
        for delta in deltas:
            if delta < 0 or delta > 65535:
                raise ValueError("Delta too large for 16-bit encoding")
            result.extend(struct.pack('<H', delta))
        return bytes(result)
    
    def _decode_fixed16(self, encoded: bytes) -> List[int]:
        """Decode fixed 16-bit deltas."""
        if len(encoded) % 2 != 0:
            raise ValueError("Invalid fixed16 encoding length")
        
        deltas = []
        for i in range(0, len(encoded), 2):
            delta = struct.unpack('<H', encoded[i:i+2])[0]
            deltas.append(delta)
        
        return deltas
    
    def estimate_size(self, prime_indices: List[int]) -> int:
        """
        Estimate encoded size for prime indices.
        
        Args:
            prime_indices: List of prime indices
            
        Returns:
            Estimated size in bytes
        """
        if not prime_indices:
            return 0
        
        return len(self.encode(prime_indices))


class PhaseQuantizer:
    """
    Phase quantizer for reducing fingerprint precision.
    
    Quantizes phase values to fewer bits while maintaining
    sufficient precision for resonance locking.
    """
    
    def __init__(self, bits: int = 8):
        """
        Initialize phase quantizer.
        
        Args:
            bits: Number of bits per quantized phase (4-16)
        """
        if not (4 <= bits <= 16):
            raise ValueError("bits must be 4-16")
        
        self.bits = bits
        self.levels = 2 ** bits
        self.scale = self.levels / (2 * np.pi)
    
    def quantize(self, phases: np.ndarray) -> np.ndarray:
        """
        Quantize phase values.
        
        Args:
            phases: Array of phase values in [0, 2π]
            
        Returns:
            Quantized phase indices
        """
        # Normalize to [0, 2π]
        normalized = np.fmod(phases, 2 * np.pi)
        normalized = np.where(normalized < 0, normalized + 2*np.pi, normalized)
        
        # Quantize to integer levels
        quantized = np.round(normalized * self.scale).astype(np.int32)
        quantized = np.clip(quantized, 0, self.levels - 1)
        
        return quantized
    
    def dequantize(self, quantized: np.ndarray) -> np.ndarray:
        """
        Dequantize phase indices back to phase values.
        
        Args:
            quantized: Quantized phase indices
            
        Returns:
            Reconstructed phase values
        """
        return quantized.astype(np.float64) / self.scale
    
    def encode(self, phases: np.ndarray) -> bytes:
        """
        Encode phases to bytes.
        
        Args:
            phases: Array of phase values
            
        Returns:
            Encoded bytes
        """
        quantized = self.quantize(phases)
        
        # Pack efficiently based on bit depth
        if self.bits <= 8:
            return quantized.astype(np.uint8).tobytes()
        else:
            return quantized.astype(np.uint16).tobytes()
    
    def decode(self, encoded: bytes, count: int) -> np.ndarray:
        """
        Decode phases from bytes.
        
        Args:
            encoded: Encoded bytes
            count: Number of phases to decode
            
        Returns:
            Reconstructed phase values
        """
        if self.bits <= 8:
            quantized = np.frombuffer(encoded, dtype=np.uint8, count=count)
        else:
            quantized = np.frombuffer(encoded, dtype=np.uint16, count=count)
        
        return self.dequantize(quantized)
    
    def estimate_error(self, phases: np.ndarray) -> float:
        """
        Estimate quantization error.
        
        Args:
            phases: Original phase values
            
        Returns:
            RMS quantization error
        """
        quantized = self.quantize(phases)
        reconstructed = self.dequantize(quantized)
        
        # Compute circular distance
        diff = np.abs(phases - reconstructed)
        diff = np.minimum(diff, 2*np.pi - diff)
        
        return np.sqrt(np.mean(diff**2))


# Convenience functions
def encode_prime_indices(indices: List[int], format: int = DeltaEncoder.VARINT) -> bytes:
    """
    Delta-encode prime indices.
    
    Args:
        indices: List of prime indices
        format: Encoding format
        
    Returns:
        Encoded bytes
    """
    encoder = DeltaEncoder(encoding_format=format)
    return encoder.encode(indices)


def decode_prime_indices(encoded: bytes, format: int = DeltaEncoder.VARINT) -> List[int]:
    """
    Decode delta-encoded prime indices.
    
    Args:
        encoded: Encoded bytes
        format: Encoding format
        
    Returns:
        List of prime indices
    """
    encoder = DeltaEncoder(encoding_format=format)
    return encoder.decode(encoded)


def quantize_phases(phases: np.ndarray, bits: int = 8) -> bytes:
    """
    Quantize and encode phase values.
    
    Args:
        phases: Array of phase values
        bits: Quantization bits
        
    Returns:
        Encoded bytes
    """
    quantizer = PhaseQuantizer(bits=bits)
    return quantizer.encode(phases)


def dequantize_phases(encoded: bytes, count: int, bits: int = 8) -> np.ndarray:
    """
    Decode and dequantize phase values.
    
    Args:
        encoded: Encoded bytes
        count: Number of phases
        bits: Quantization bits
        
    Returns:
        Reconstructed phase values
    """
    quantizer = PhaseQuantizer(bits=bits)
    return quantizer.decode(encoded, count)


def estimate_compression_savings(
    num_primes: int,
    avg_prime: int = 1000
) -> Tuple[int, int, float]:
    """
    Estimate compression savings for beacon.
    
    Args:
        num_primes: Number of primes in beacon
        avg_prime: Average prime value
        
    Returns:
        Tuple of (original_size, compressed_size, savings_percent)
    """
    # Original: 4 bytes per prime index (int32)
    original_size = num_primes * 4
    
    # Delta-encoded: estimate ~1.5 bytes per delta (varint)
    # First value: ~2 bytes, subsequent: ~1 byte each
    compressed_size = 2 + (num_primes - 1) * 1
    
    savings = 100 * (1 - compressed_size / original_size)
    
    return original_size, compressed_size, savings