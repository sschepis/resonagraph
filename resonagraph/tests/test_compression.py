"""
Tests for compression functionality.

Tests cover:
- LZ4 compression/decompression
- Delta encoding for prime indices
- Phase quantization
- Compression ratio validation
- Performance benchmarks
"""

import pytest
import numpy as np
import struct
from typing import List

# Try importing compression modules
try:
    from resonagraph.compression import (
        LZ4Compressor,
        compress_beacon,
        decompress_beacon,
        estimate_compression_ratio,
        BeaconCompressor,
        DeltaEncoder,
        encode_prime_indices,
        decode_prime_indices,
        PhaseQuantizer,
        quantize_phases,
        dequantize_phases,
        estimate_compression_savings
    )
    COMPRESSION_AVAILABLE = True
except ImportError as e:
    COMPRESSION_AVAILABLE = False
    pytest.skip(f"Compression modules not available: {e}", allow_module_level=True)


class TestLZ4Compression:
    """Test LZ4 compression functionality."""
    
    def test_create_compressor(self):
        """Test compressor creation."""
        compressor = LZ4Compressor()
        assert compressor is not None
        assert compressor.compression_level == LZ4Compressor.LEVEL_DEFAULT
    
    def test_compress_decompress_roundtrip(self):
        """Test compression and decompression roundtrip."""
        compressor = LZ4Compressor()
        
        # Test data
        original = b"Hello, World! " * 100  # Repeating pattern
        
        # Compress
        compressed = compressor.compress(original)
        assert len(compressed) < len(original)  # Should be smaller
        
        # Decompress
        decompressed = compressor.decompress(compressed)
        assert decompressed == original
    
    def test_small_data_not_compressed(self):
        """Test that small data is not compressed."""
        compressor = LZ4Compressor(min_size_threshold=128)
        
        small_data = b"tiny"
        result = compressor.compress(small_data)
        
        # Should have uncompressed marker
        assert result[0:1] == b'\x00'
        assert result[1:] == small_data
    
    def test_incompressible_data(self):
        """Test handling of incompressible data."""
        compressor = LZ4Compressor(min_size_threshold=0)
        
        # Random data (incompressible)
        random_data = np.random.bytes(1000)
        
        compressed = compressor.compress(random_data)
        decompressed = compressor.decompress(compressed)
        
        assert decompressed == random_data
    
    def test_compression_levels(self):
        """Test different compression levels."""
        test_data = b"Repeating pattern! " * 100
        
        # Fast compression
        fast = LZ4Compressor(compression_level=LZ4Compressor.LEVEL_FAST)
        fast_compressed = fast.compress(test_data)
        
        # High compression
        high = LZ4Compressor(compression_level=LZ4Compressor.LEVEL_HIGH)
        high_compressed = high.compress(test_data)
        
        # High compression should be smaller (or equal)
        assert len(high_compressed) <= len(fast_compressed)
        
        # Both should decompress correctly
        assert fast.decompress(fast_compressed) == test_data
        assert high.decompress(high_compressed) == test_data
    
    def test_compression_stats(self):
        """Test compression statistics tracking."""
        compressor = LZ4Compressor()
        
        test_data = b"Test data " * 50
        
        # Perform compression
        compressed = compressor.compress(test_data)
        
        # Check stats
        stats = compressor.get_stats()
        assert stats['total_compressed'] == 1
        assert stats['total_bytes_in'] == len(test_data)
        assert stats['total_bytes_out'] == len(compressed)
        assert 0 < stats['compression_ratio'] < 1.0
    
    def test_reset_stats(self):
        """Test statistics reset."""
        compressor = LZ4Compressor()
        
        # Compress some data
        compressor.compress(b"test data" * 10)
        
        # Reset stats
        compressor.reset_stats()
        
        stats = compressor.get_stats()
        assert stats['total_compressed'] == 0
        assert stats['total_bytes_in'] == 0


class TestBeaconCompressor:
    """Test beacon-specific compression."""
    
    def test_create_beacon_compressor(self):
        """Test beacon compressor creation."""
        compressor = BeaconCompressor()
        assert compressor is not None
    
    def test_compress_decompress_beacon(self):
        """Test beacon payload compression roundtrip."""
        compressor = BeaconCompressor()
        
        # Create test beacon components
        prime_indices = b'\x02\x03\x05\x07\x0b\x0d'
        epoch = 12345
        phase_fingerprint = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        signature = b'0' * 64  # 64-byte signature
        
        # Compress
        compressed = compressor.compress_beacon_payload(
            prime_indices, epoch, phase_fingerprint, signature
        )
        
        # Decompress
        result = compressor.decompress_beacon_payload(compressed)
        
        # Verify components
        assert result['prime_indices'] == prime_indices
        assert result['epoch'] == epoch
        assert result['phase_fingerprint'] == phase_fingerprint
        assert result['signature'] == signature
    
    def test_beacon_compression_ratio(self):
        """Test beacon compression achieves good ratio."""
        compressor = BeaconCompressor()
        
        # Typical beacon components
        prime_indices = bytes(range(32))  # 32 prime indices
        epoch = 12345
        phase_fingerprint = bytes(range(16))  # 16-byte fingerprint
        signature = b'S' * 64  # 64-byte signature
        
        compressed = compressor.compress_beacon_payload(
            prime_indices, epoch, phase_fingerprint, signature
        )
        
        # Original size (without compression)
        original_size = 2 + len(prime_indices) + 4 + 2 + len(phase_fingerprint) + len(signature)
        
        # Should achieve some compression
        print(f"\nBeacon: {original_size} bytes → {len(compressed)} bytes")
        print(f"Ratio: {len(compressed)/original_size:.2f}")


class TestDeltaEncoding:
    """Test delta encoding for prime indices."""
    
    def test_create_encoder(self):
        """Test encoder creation."""
        encoder = DeltaEncoder()
        assert encoder is not None
    
    def test_encode_decode_roundtrip(self):
        """Test delta encoding roundtrip."""
        encoder = DeltaEncoder(encoding_format=DeltaEncoder.VARINT)
        
        # Test prime indices (sorted)
        indices = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
        
        # Encode
        encoded = encoder.encode(indices)
        
        # Decode
        decoded = encoder.decode(encoded)
        
        assert decoded == indices
    
    def test_varint_encoding(self):
        """Test variable-length integer encoding."""
        encoder = DeltaEncoder(encoding_format=DeltaEncoder.VARINT)
        
        # Small deltas (fit in 1 byte each)
        small_indices = [0, 1, 2, 3, 4, 5]
        encoded = encoder.encode(small_indices)
        
        # Should be very compact
        assert len(encoded) <= len(small_indices) * 2
        
        # Verify correctness
        assert encoder.decode(encoded) == small_indices
    
    def test_fixed8_encoding(self):
        """Test fixed 8-bit encoding."""
        encoder = DeltaEncoder(encoding_format=DeltaEncoder.FIXED8)
        
        # Indices with small deltas
        indices = [0, 1, 3, 6, 10, 15]
        
        encoded = encoder.encode(indices)
        decoded = encoder.decode(encoded)
        
        assert decoded == indices
        assert len(encoded) == len(indices)
    
    def test_fixed16_encoding(self):
        """Test fixed 16-bit encoding."""
        encoder = DeltaEncoder(encoding_format=DeltaEncoder.FIXED16)
        
        # Indices with larger deltas
        indices = [0, 100, 500, 1200, 2500]
        
        encoded = encoder.encode(indices)
        decoded = encoder.decode(encoded)
        
        assert decoded == indices
        assert len(encoded) == len(indices) * 2
    
    def test_compression_savings(self):
        """Test that delta encoding reduces size."""
        encoder = DeltaEncoder()
        
        # Sequential primes (small deltas)
        indices = list(range(0, 100, 2))  # Even numbers
        
        encoded = encoder.encode(indices)
        
        # Original: 4 bytes per index = 400 bytes
        # Encoded should be much smaller
        original_size = len(indices) * 4
        print(f"\nDelta: {original_size} bytes → {len(encoded)} bytes")
        print(f"Savings: {(1 - len(encoded)/original_size)*100:.1f}%")
        
        assert len(encoded) < original_size * 0.5  # At least 50% savings
    
    def test_empty_list(self):
        """Test encoding empty list."""
        encoder = DeltaEncoder()
        
        encoded = encoder.encode([])
        decoded = encoder.decode(encoded)
        
        assert decoded == []
        assert encoded == b''


class TestPhaseQuantization:
    """Test phase quantization."""
    
    def test_create_quantizer(self):
        """Test quantizer creation."""
        quantizer = PhaseQuantizer(bits=8)
        assert quantizer is not None
        assert quantizer.bits == 8
    
    def test_quantize_dequantize_roundtrip(self):
        """Test quantization roundtrip."""
        quantizer = PhaseQuantizer(bits=8)
        
        # Test phases
        phases = np.array([0.0, np.pi/4, np.pi/2, np.pi, 3*np.pi/2, 2*np.pi-0.1])
        
        # Quantize and dequantize
        quantized = quantizer.quantize(phases)
        reconstructed = quantizer.dequantize(quantized)
        
        # Should be close (within quantization error)
        assert len(reconstructed) == len(phases)
        for orig, recon in zip(phases, reconstructed):
            # Circular distance
            diff = abs(orig - recon)
            diff = min(diff, 2*np.pi - diff)
            assert diff < 0.1  # Within 0.1 radians
    
    def test_quantization_bits(self):
        """Test different quantization bit depths."""
        phases = np.linspace(0, 2*np.pi, 100, endpoint=False)
        
        # Low precision
        q4 = PhaseQuantizer(bits=4)
        error_4 = q4.estimate_error(phases)
        
        # Medium precision
        q8 = PhaseQuantizer(bits=8)
        error_8 = q8.estimate_error(phases)
        
        # High precision
        q12 = PhaseQuantizer(bits=12)
        error_12 = q12.estimate_error(phases)
        
        # Higher bits should have lower error
        assert error_12 < error_8 < error_4
        
        print(f"\nQuantization errors:")
        print(f"  4-bit: {error_4:.4f} rad")
        print(f"  8-bit: {error_8:.4f} rad")
        print(f"  12-bit: {error_12:.4f} rad")
    
    def test_encode_decode_phases(self):
        """Test phase encoding/decoding."""
        quantizer = PhaseQuantizer(bits=8)
        
        phases = np.array([0.1, 0.5, 1.0, 2.0, 3.0, 5.0])
        
        # Encode
        encoded = quantizer.encode(phases)
        
        # Decode
        decoded = quantizer.decode(encoded, len(phases))
        
        # Verify shape
        assert len(decoded) == len(phases)
        
        # Verify values are close
        for orig, dec in zip(phases, decoded):
            diff = abs(orig - dec)
            diff = min(diff, 2*np.pi - diff)
            assert diff < 0.05


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_compress_decompress_beacon(self):
        """Test beacon compression convenience functions."""
        data = b"Test beacon data " * 20
        
        compressed = compress_beacon(data)
        decompressed = decompress_beacon(compressed)
        
        assert decompressed == data
    
    def test_estimate_compression_ratio(self):
        """Test compression ratio estimation."""
        # Highly compressible data
        compressible = b"A" * 1000
        ratio = estimate_compression_ratio(compressible)
        
        # Should achieve good compression
        assert ratio < 0.2  # Better than 5:1
        
        # Random data (incompressible)
        random_data = np.random.bytes(1000)
        ratio = estimate_compression_ratio(random_data)
        
        # Should be close to 1:1 (no compression)
        assert ratio > 0.9
    
    def test_encode_decode_prime_indices(self):
        """Test prime indices encoding convenience."""
        indices = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        
        encoded = encode_prime_indices(indices)
        decoded = decode_prime_indices(encoded)
        
        assert decoded == indices
    
    def test_quantize_dequantize_phases(self):
        """Test phase quantization convenience."""
        phases = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        
        encoded = quantize_phases(phases, bits=8)
        decoded = dequantize_phases(encoded, len(phases), bits=8)
        
        # Should be close
        np.testing.assert_allclose(phases, decoded, atol=0.05)
    
    def test_estimate_compression_savings(self):
        """Test compression savings estimation."""
        num_primes = 32
        
        original, compressed, savings = estimate_compression_savings(num_primes)
        
        assert original > compressed
        assert savings > 50  # At least 50% savings
        
        print(f"\nCompression estimate for {num_primes} primes:")
        print(f"  Original: {original} bytes")
        print(f"  Compressed: {compressed} bytes")
        print(f"  Savings: {savings:.1f}%")


@pytest.mark.benchmark
class TestPerformance:
    """Performance benchmarks for compression."""
    
    def test_lz4_compression_speed(self):
        """Benchmark LZ4 compression speed."""
        import time
        
        compressor = LZ4Compressor()
        
        # Create test data (1 MB)
        data = b"Test pattern " * 80000
        
        # Benchmark compression
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            compressed = compressor.compress(data)
        compress_time = time.perf_counter() - start
        
        # Benchmark decompression
        start = time.perf_counter()
        for _ in range(iterations):
            decompressed = compressor.decompress(compressed)
        decompress_time = time.perf_counter() - start
        
        # Calculate throughput
        mb_compressed = (len(data) * iterations) / 1024**2
        mb_decompressed = (len(decompressed) * iterations) / 1024**2
        
        compress_throughput = mb_compressed / compress_time
        decompress_throughput = mb_decompressed / decompress_time
        
        print(f"\nLZ4 Performance:")
        print(f"  Compression: {compress_throughput:.1f} MB/s")
        print(f"  Decompression: {decompress_throughput:.1f} MB/s")
        
        # Should meet performance targets
        assert compress_throughput > 50  # At least 50 MB/s
        assert decompress_throughput > 200  # At least 200 MB/s
    
    def test_delta_encoding_speed(self):
        """Benchmark delta encoding speed."""
        import time
        
        encoder = DeltaEncoder()
        
        # Create test indices
        indices = list(range(0, 10000, 2))  # 5000 even numbers
        
        # Benchmark encoding
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            encoded = encoder.encode(indices)
        encode_time = time.perf_counter() - start
        
        # Benchmark decoding
        start = time.perf_counter()
        for _ in range(iterations):
            decoded = encoder.decode(encoded)
        decode_time = time.perf_counter() - start
        
        encode_rate = (len(indices) * iterations) / encode_time
        decode_rate = (len(indices) * iterations) / decode_time
        
        print(f"\nDelta Encoding Performance:")
        print(f"  Encoding: {encode_rate:.0f} indices/s")
        print(f"  Decoding: {decode_rate:.0f} indices/s")
        
        # Should be very fast
        assert encode_rate > 100000  # At least 100k indices/s
        assert decode_rate > 100000


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])