"""
GPU acceleration module for ResonaGraph.

Provides cross-platform GPU acceleration for resonance locking operations
using PyTorch backends:
- CUDA (Linux/Windows NVIDIA GPUs)
- ROCm (Linux AMD GPUs)  
- MPS (macOS Apple Silicon)
- CPU fallback (all platforms)
"""

from .gpu import (
    GPUBackend,
    GPUAccelerator,
    get_available_backend,
    is_gpu_available
)

__all__ = [
    'GPUBackend',
    'GPUAccelerator',
    'get_available_backend',
    'is_gpu_available'
]