"""
Compression module for ResonaGraph.

Implements beacon compression and delta encoding for bandwidth optimization:
- LZ4 compression for beacon payloads
- Delta encoding for prime indices
- Quantized phase fingerprints
"""

from .lz4_compression import (
    LZ4Compressor,
    compress_beacon,
    decompress_beacon,
    estimate_compression_ratio
)
from .delta_encoding import (
    DeltaEncoder,
    encode_prime_indices,
    decode_prime_indices,
    quantize_phases,
    dequantize_phases
)

__all__ = [
    'LZ4Compressor',
    'compress_beacon',
    'decompress_beacon',
    'estimate_compression_ratio',
    'DeltaEncoder',
    'encode_prime_indices',
    'decode_prime_indices',
    'quantize_phases',
    'dequantize_phases'
]