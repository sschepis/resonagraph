"""
LZ4 compression for ResonaGraph beacons.

Implements fast LZ4 compression for beacon payloads to reduce
network bandwidth while maintaining high performance.

Target: 2:1 compression ratio
Speed: >500 MB/s compression, >2 GB/s decompression
"""

import logging
from typing import Optional, Dict, Any
import struct

logger = logging.getLogger(__name__)

# Try importing LZ4
try:
    import lz4.frame
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False
    logger.warning("LZ4 not available. Install with: pip install lz4")


class LZ4Compressor:
    """
    LZ4 compressor for beacon payloads.
    
    Provides fast compression with minimal CPU overhead suitable
    for real-time beacon transmission.
    """
    
    # Compression levels (0-16, higher = better compression but slower)
    LEVEL_FAST = 0      # Fastest, ~1.8:1 ratio
    LEVEL_DEFAULT = 3   # Balanced, ~2.0:1 ratio
    LEVEL_HIGH = 9      # Best compression, ~2.5:1 ratio
    
    # Minimum size threshold for compression (bytes)
    MIN_SIZE_THRESHOLD = 128  # Don't compress tiny payloads
    
    def __init__(
        self,
        compression_level: int = LEVEL_DEFAULT,
        min_size_threshold: int = MIN_SIZE_THRESHOLD
    ):
        """
        Initialize LZ4 compressor.
        
        Args:
            compression_level: LZ4 compression level (0-16)
            min_size_threshold: Minimum payload size to compress
        """
        if not LZ4_AVAILABLE:
            raise ImportError(
                "LZ4 is required for compression. "
                "Install with: pip install lz4"
            )
        
        if not (0 <= compression_level <= 16):
            raise ValueError("compression_level must be 0-16")
        
        self.compression_level = compression_level
        self.min_size_threshold = min_size_threshold
        
        # Statistics
        self.stats = {
            'total_compressed': 0,
            'total_decompressed': 0,
            'total_bytes_in': 0,
            'total_bytes_out': 0,
            'compression_ratio': 0.0
        }
    
    def compress(self, data: bytes) -> bytes:
        """
        Compress data using LZ4.
        
        Args:
            data: Raw bytes to compress
            
        Returns:
            Compressed bytes with header
        """
        if len(data) < self.min_size_threshold:
            # Too small, don't compress (add uncompressed marker)
            return b'\x00' + data
        
        try:
            # Compress using LZ4 frame format
            compressed = lz4.frame.compress(
                data,
                compression_level=self.compression_level,
                block_size=lz4.frame.BLOCKSIZE_MAX1MB
            )
            
            # Check if compression is beneficial
            if len(compressed) >= len(data):
                # Compression didn't help, store uncompressed
                result = b'\x00' + data
            else:
                # Add compressed marker
                result = b'\x01' + compressed
            
            # Update statistics
            self.stats['total_compressed'] += 1
            self.stats['total_bytes_in'] += len(data)
            self.stats['total_bytes_out'] += len(result)
            self._update_compression_ratio()
            
            return result
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            # Fall back to uncompressed
            return b'\x00' + data
    
    def decompress(self, data: bytes) -> bytes:
        """
        Decompress LZ4-compressed data.
        
        Args:
            data: Compressed bytes with header
            
        Returns:
            Decompressed bytes
            
        Raises:
            ValueError: If data is invalid
        """
        if len(data) < 1:
            raise ValueError("Invalid compressed data: too short")
        
        # Check compression marker
        marker = data[0:1]
        payload = data[1:]
        
        if marker == b'\x00':
            # Uncompressed data
            decompressed = payload
        elif marker == b'\x01':
            # Compressed data
            try:
                decompressed = lz4.frame.decompress(payload)
            except Exception as e:
                raise ValueError(f"Decompression failed: {e}")
        else:
            raise ValueError(f"Invalid compression marker: {marker}")
        
        # Update statistics
        self.stats['total_decompressed'] += 1
        
        return decompressed
    
    def _update_compression_ratio(self):
        """Update average compression ratio."""
        if self.stats['total_bytes_in'] > 0:
            self.stats['compression_ratio'] = (
                self.stats['total_bytes_out'] / self.stats['total_bytes_in']
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get compression statistics.
        
        Returns:
            Dictionary with compression stats
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset compression statistics."""
        self.stats = {
            'total_compressed': 0,
            'total_decompressed': 0,
            'total_bytes_in': 0,
            'total_bytes_out': 0,
            'compression_ratio': 0.0
        }


# Convenience functions
_default_compressor: Optional[LZ4Compressor] = None


def get_default_compressor() -> LZ4Compressor:
    """Get or create default compressor instance."""
    global _default_compressor
    if _default_compressor is None:
        _default_compressor = LZ4Compressor()
    return _default_compressor


def compress_beacon(beacon_data: bytes, level: int = LZ4Compressor.LEVEL_DEFAULT) -> bytes:
    """
    Compress beacon data using LZ4.
    
    Args:
        beacon_data: Raw beacon bytes
        level: Compression level (0-16)
        
    Returns:
        Compressed bytes
    """
    compressor = LZ4Compressor(compression_level=level)
    return compressor.compress(beacon_data)


def decompress_beacon(compressed_data: bytes) -> bytes:
    """
    Decompress beacon data.
    
    Args:
        compressed_data: Compressed beacon bytes
        
    Returns:
        Decompressed bytes
    """
    compressor = get_default_compressor()
    return compressor.decompress(compressed_data)


def estimate_compression_ratio(sample_data: bytes, level: int = LZ4Compressor.LEVEL_DEFAULT) -> float:
    """
    Estimate compression ratio for sample data.
    
    Args:
        sample_data: Sample beacon data
        level: Compression level
        
    Returns:
        Estimated compression ratio (output/input)
    """
    if len(sample_data) == 0:
        return 1.0
    
    compressor = LZ4Compressor(compression_level=level, min_size_threshold=0)
    compressed = compressor.compress(sample_data)
    
    return len(compressed) / len(sample_data)


class BeaconCompressor:
    """
    Specialized beacon compressor with beacon-aware optimizations.
    
    Implements compression strategies specifically tuned for
    beacon structure and content.
    """
    
    def __init__(self, compression_level: int = LZ4Compressor.LEVEL_DEFAULT):
        """
        Initialize beacon compressor.
        
        Args:
            compression_level: LZ4 compression level
        """
        self.compressor = LZ4Compressor(
            compression_level=compression_level,
            min_size_threshold=64  # Lower threshold for beacons
        )
    
    def compress_beacon_payload(
        self,
        prime_indices: bytes,
        epoch: int,
        phase_fingerprint: bytes,
        signature: bytes
    ) -> bytes:
        """
        Compress beacon payload components.
        
        Args:
            prime_indices: Encoded prime indices
            epoch: Epoch timestamp
            phase_fingerprint: Phase fingerprint
            signature: Beacon signature
            
        Returns:
            Compressed beacon payload
        """
        # Pack components
        epoch_bytes = struct.pack('<I', epoch)
        
        # Concatenate all components
        payload = (
            struct.pack('<H', len(prime_indices)) +
            prime_indices +
            epoch_bytes +
            struct.pack('<H', len(phase_fingerprint)) +
            phase_fingerprint +
            signature
        )
        
        # Compress the entire payload
        return self.compressor.compress(payload)
    
    def decompress_beacon_payload(self, compressed: bytes) -> Dict[str, Any]:
        """
        Decompress beacon payload.
        
        Args:
            compressed: Compressed beacon payload
            
        Returns:
            Dictionary with beacon components
        """
        # Decompress
        payload = self.compressor.decompress(compressed)
        
        # Unpack components
        offset = 0
        
        # Prime indices
        prime_len = struct.unpack('<H', payload[offset:offset+2])[0]
        offset += 2
        prime_indices = payload[offset:offset+prime_len]
        offset += prime_len
        
        # Epoch
        epoch = struct.unpack('<I', payload[offset:offset+4])[0]
        offset += 4
        
        # Phase fingerprint
        fp_len = struct.unpack('<H', payload[offset:offset+2])[0]
        offset += 2
        phase_fingerprint = payload[offset:offset+fp_len]
        offset += fp_len
        
        # Signature (rest of payload)
        signature = payload[offset:]
        
        return {
            'prime_indices': prime_indices,
            'epoch': epoch,
            'phase_fingerprint': phase_fingerprint,
            'signature': signature
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return self.compressor.get_stats()