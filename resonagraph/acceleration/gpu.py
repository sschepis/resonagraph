"""
GPU acceleration for ResonaGraph using PyTorch.

Provides cross-platform GPU support:
- CUDA: NVIDIA GPUs (Linux/Windows)
- ROCm: AMD GPUs (Linux)
- MPS: Apple Silicon (macOS M1/M2/M3/M4)
- CPU: Universal fallback

This module accelerates resonance locking operations by parallelizing
probe synthesis, overlap computation, and gradient descent on GPU.
"""

import numpy as np
from enum import Enum
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

# Try importing PyTorch
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. GPU acceleration disabled.")


class GPUBackend(Enum):
    """Available GPU acceleration backends."""
    CUDA = "cuda"      # NVIDIA GPUs
    ROCm = "cuda"      # AMD GPUs (uses same PyTorch backend)
    MPS = "mps"        # Apple Silicon
    CPU = "cpu"        # CPU fallback


def get_available_backend() -> GPUBackend:
    """
    Detect and return the best available GPU backend.
    
    Returns:
        GPUBackend: Best available backend for this system
    """
    if not TORCH_AVAILABLE:
        return GPUBackend.CPU
    
    # Check for CUDA (NVIDIA or AMD with ROCm)
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"CUDA available: {device_name}")
        return GPUBackend.CUDA
    
    # Check for MPS (Apple Silicon)
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        logger.info("MPS (Apple Silicon) available")
        return GPUBackend.MPS
    
    # Fallback to CPU
    logger.info("No GPU available, using CPU")
    return GPUBackend.CPU


def is_gpu_available() -> bool:
    """
    Check if any GPU backend is available.
    
    Returns:
        bool: True if GPU is available, False otherwise
    """
    backend = get_available_backend()
    return backend != GPUBackend.CPU


class GPUAccelerator:
    """
    GPU accelerator for resonance locking operations.
    
    Handles probe synthesis, overlap computation, and gradient descent
    using PyTorch for cross-platform GPU acceleration.
    """
    
    def __init__(self, backend: Optional[GPUBackend] = None, device_id: int = 0):
        """
        Initialize GPU accelerator.
        
        Args:
            backend: Specific backend to use, or None for auto-detect
            device_id: GPU device ID (for multi-GPU systems)
        """
        if not TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is required for GPU acceleration. "
                "Install with: pip install torch"
            )
        
        # Determine backend
        if backend is None:
            self.backend = get_available_backend()
        else:
            self.backend = backend
        
        # Create PyTorch device
        if self.backend == GPUBackend.CPU:
            self.device = torch.device("cpu")
        elif self.backend == GPUBackend.MPS:
            self.device = torch.device("mps")
        else:  # CUDA/ROCm
            self.device = torch.device(f"cuda:{device_id}")
        
        logger.info(f"Initialized GPU accelerator: {self.device}")
        
        # Performance settings
        if self.backend == GPUBackend.CUDA:
            # Enable TF32 for better performance on Ampere+ GPUs
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
    
    def to_tensor(self, array: np.ndarray) -> torch.Tensor:
        """
        Convert numpy array to PyTorch tensor on device.
        
        Args:
            array: NumPy array to convert
            
        Returns:
            PyTorch tensor on GPU/CPU
        """
        return torch.from_numpy(array).to(self.device)
    
    def to_numpy(self, tensor: torch.Tensor) -> np.ndarray:
        """
        Convert PyTorch tensor to numpy array.
        
        Args:
            tensor: PyTorch tensor to convert
            
        Returns:
            NumPy array
        """
        return tensor.cpu().numpy()
    
    def synthesize_probe(
        self,
        prime_indices: np.ndarray,
        weights: Optional[np.ndarray] = None,
        initial_phases: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Synthesize resonance probe on GPU.
        
        Creates probe state |Q⟩ = ∑ w_p e^{iφ_p} |p⟩
        
        Args:
            prime_indices: Array of prime indices (k_primes,)
            weights: Optional probe weights (k_primes,)
            initial_phases: Optional initial phases (k_primes,)
            
        Returns:
            Tuple of (real_part, imag_part) of probe state
        """
        k_primes = len(prime_indices)
        
        # Convert to tensors
        primes_t = self.to_tensor(prime_indices.astype(np.float32))
        
        if weights is None:
            weights_t = torch.ones(k_primes, device=self.device, dtype=torch.float32)
        else:
            weights_t = self.to_tensor(weights.astype(np.float32))
        
        if initial_phases is None:
            phases_t = torch.zeros(k_primes, device=self.device, dtype=torch.float32)
        else:
            phases_t = self.to_tensor(initial_phases.astype(np.float32))
        
        # Compute probe: w_p * e^{iφ_p}
        real_part = weights_t * torch.cos(phases_t)
        imag_part = weights_t * torch.sin(phases_t)
        
        return self.to_numpy(real_part), self.to_numpy(imag_part)
    
    def compute_overlap(
        self,
        probe_real: np.ndarray,
        probe_imag: np.ndarray,
        beacon_real: np.ndarray,
        beacon_imag: np.ndarray
    ) -> float:
        """
        Compute resonance overlap between probe and beacon on GPU.
        
        R = |⟨Q|B⟩| / (||Q|| ||B||)
        
        Args:
            probe_real: Real part of probe state
            probe_imag: Imaginary part of probe state
            beacon_real: Real part of beacon state
            beacon_imag: Imaginary part of beacon state
            
        Returns:
            Overlap value R ∈ [0, 1]
        """
        # Convert to tensors
        q_r = self.to_tensor(probe_real.astype(np.float32))
        q_i = self.to_tensor(probe_imag.astype(np.float32))
        b_r = self.to_tensor(beacon_real.astype(np.float32))
        b_i = self.to_tensor(beacon_imag.astype(np.float32))
        
        # Compute inner product ⟨Q|B⟩ = ∑(q_r*b_r + q_i*b_i) + i∑(q_i*b_r - q_r*b_i)
        inner_real = torch.sum(q_r * b_r + q_i * b_i)
        inner_imag = torch.sum(q_i * b_r - q_r * b_i)
        inner_magnitude = torch.sqrt(inner_real**2 + inner_imag**2)
        
        # Compute norms
        q_norm = torch.sqrt(torch.sum(q_r**2 + q_i**2))
        b_norm = torch.sqrt(torch.sum(b_r**2 + b_i**2))
        
        # Avoid division by zero
        if q_norm < 1e-10 or b_norm < 1e-10:
            return 0.0
        
        # Compute overlap
        overlap = inner_magnitude / (q_norm * b_norm)
        
        return float(overlap.cpu().item())
    
    def compute_phase_differences(
        self,
        probe_phases: np.ndarray,
        beacon_phases: np.ndarray
    ) -> np.ndarray:
        """
        Compute phase differences between probe and beacon on GPU.
        
        Δφ_p = (φ_beacon - φ_probe) mod 2π
        
        Args:
            probe_phases: Probe phases (k_primes,)
            beacon_phases: Beacon phases (k_primes,)
            
        Returns:
            Phase differences in [-π, π]
        """
        # Convert to tensors
        q_phases = self.to_tensor(probe_phases.astype(np.float32))
        b_phases = self.to_tensor(beacon_phases.astype(np.float32))
        
        # Compute differences
        diff = b_phases - q_phases
        
        # Normalize to [-π, π]
        diff = torch.atan2(torch.sin(diff), torch.cos(diff))
        
        return self.to_numpy(diff)
    
    def update_probe_gradient(
        self,
        probe_real: np.ndarray,
        probe_imag: np.ndarray,
        beacon_real: np.ndarray,
        beacon_imag: np.ndarray,
        learning_rate: float = 0.1
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Update probe using gradient descent on GPU.
        
        Performs one gradient descent step to align probe with beacon.
        
        Args:
            probe_real: Real part of probe
            probe_imag: Imaginary part of probe
            beacon_real: Real part of beacon
            beacon_imag: Imaginary part of beacon
            learning_rate: Learning rate for gradient descent
            
        Returns:
            Updated (probe_real, probe_imag)
        """
        # Convert to tensors with gradient tracking
        q_r = self.to_tensor(probe_real.astype(np.float32)).requires_grad_(True)
        q_i = self.to_tensor(probe_imag.astype(np.float32)).requires_grad_(True)
        b_r = self.to_tensor(beacon_real.astype(np.float32))
        b_i = self.to_tensor(beacon_imag.astype(np.float32))
        
        # Compute negative overlap as loss (maximize overlap = minimize negative)
        inner_real = torch.sum(q_r * b_r + q_i * b_i)
        inner_imag = torch.sum(q_i * b_r - q_r * b_i)
        inner_magnitude = torch.sqrt(inner_real**2 + inner_imag**2)
        
        q_norm = torch.sqrt(torch.sum(q_r**2 + q_i**2))
        b_norm = torch.sqrt(torch.sum(b_r**2 + b_i**2))
        
        # Loss = -overlap
        loss = -inner_magnitude / (q_norm * b_norm + 1e-10)
        
        # Compute gradients
        loss.backward()
        
        # Update probe
        with torch.no_grad():
            q_r -= learning_rate * q_r.grad
            q_i -= learning_rate * q_i.grad
        
        return self.to_numpy(q_r), self.to_numpy(q_i)
    
    def batch_overlap(
        self,
        probe_states: List[Tuple[np.ndarray, np.ndarray]],
        beacon_real: np.ndarray,
        beacon_imag: np.ndarray
    ) -> np.ndarray:
        """
        Compute overlap for multiple probes in parallel.
        
        Args:
            probe_states: List of (real, imag) tuples for each probe
            beacon_real: Beacon real part
            beacon_imag: Beacon imaginary part
            
        Returns:
            Array of overlap values
        """
        num_probes = len(probe_states)
        k_primes = len(beacon_real)
        
        # Stack all probes into batch tensors
        batch_real = torch.zeros(num_probes, k_primes, device=self.device, dtype=torch.float32)
        batch_imag = torch.zeros(num_probes, k_primes, device=self.device, dtype=torch.float32)
        
        for i, (real, imag) in enumerate(probe_states):
            batch_real[i] = self.to_tensor(real.astype(np.float32))
            batch_imag[i] = self.to_tensor(imag.astype(np.float32))
        
        # Beacon as tensors
        b_r = self.to_tensor(beacon_real.astype(np.float32))
        b_i = self.to_tensor(beacon_imag.astype(np.float32))
        
        # Compute batch inner products
        # inner = ⟨Q_i|B⟩ for each probe i
        inner_real = torch.sum(batch_real * b_r + batch_imag * b_i, dim=1)
        inner_imag = torch.sum(batch_imag * b_r - batch_real * b_i, dim=1)
        inner_magnitude = torch.sqrt(inner_real**2 + inner_imag**2)
        
        # Compute norms
        q_norms = torch.sqrt(torch.sum(batch_real**2 + batch_imag**2, dim=1))
        b_norm = torch.sqrt(torch.sum(b_r**2 + b_i**2))
        
        # Compute overlaps
        overlaps = inner_magnitude / (q_norms * b_norm + 1e-10)
        
        return self.to_numpy(overlaps)
    
    def get_memory_stats(self) -> dict:
        """
        Get GPU memory statistics.
        
        Returns:
            Dictionary with memory usage information
        """
        if self.backend == GPUBackend.CPU:
            return {"backend": "cpu", "memory_used": 0, "memory_total": 0}
        
        if self.backend == GPUBackend.CUDA:
            return {
                "backend": "cuda",
                "memory_allocated": torch.cuda.memory_allocated(self.device) / 1024**2,  # MB
                "memory_reserved": torch.cuda.memory_reserved(self.device) / 1024**2,    # MB
                "memory_total": torch.cuda.get_device_properties(self.device).total_memory / 1024**2  # MB
            }
        
        if self.backend == GPUBackend.MPS:
            return {
                "backend": "mps",
                "memory_allocated": torch.mps.current_allocated_memory() / 1024**2,  # MB
                "driver_allocated": torch.mps.driver_allocated_memory() / 1024**2    # MB
            }
        
        return {"backend": str(self.backend)}
    
    def clear_cache(self):
        """Clear GPU memory cache."""
        if self.backend == GPUBackend.CUDA:
            torch.cuda.empty_cache()
        elif self.backend == GPUBackend.MPS:
            torch.mps.empty_cache()
    
    def __repr__(self) -> str:
        return f"GPUAccelerator(backend={self.backend.value}, device={self.device})"


# Convenience functions
def create_accelerator(
    prefer_gpu: bool = True,
    device_id: int = 0
) -> GPUAccelerator:
    """
    Create GPU accelerator with automatic backend selection.
    
    Args:
        prefer_gpu: If True, use GPU if available; if False, force CPU
        device_id: GPU device ID for multi-GPU systems
        
    Returns:
        GPUAccelerator instance
    """
    if not prefer_gpu or not TORCH_AVAILABLE:
        backend = GPUBackend.CPU
    else:
        backend = get_available_backend()
    
    return GPUAccelerator(backend=backend, device_id=device_id)