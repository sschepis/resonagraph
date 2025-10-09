"""
GPU-accelerated probe synthesis for ResonaGraph.

Extends the standard probe synthesizer with optional GPU acceleration
for improved performance on systems with CUDA, ROCm, or MPS support.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging

from resonagraph.resonance.probe import ProbeState, ProbeSynthesizer
from resonagraph.acceleration import GPUAccelerator, create_accelerator, is_gpu_available

logger = logging.getLogger(__name__)


class GPUProbeState(ProbeState):
    """
    GPU-accelerated probe state with cached tensor representations.
    
    Stores both NumPy arrays (for compatibility) and PyTorch tensors
    (for GPU acceleration) to minimize CPU↔GPU data movement.
    """
    
    def __init__(
        self,
        primes: List[int],
        phase_angles: List[float],
        weights: Optional[List[float]] = None,
        accelerator: Optional[GPUAccelerator] = None
    ):
        """
        Initialize GPU-accelerated probe state.
        
        Args:
            primes: List of prime numbers
            phase_angles: Phase angles for each prime
            weights: Optional weights for each prime
            accelerator: Optional GPU accelerator instance
        """
        super().__init__(primes, phase_angles, weights)
        
        self.accelerator = accelerator
        
        # Pre-compute complex representation for GPU
        if accelerator is not None:
            self._precompute_gpu_state()
    
    def _precompute_gpu_state(self):
        """Pre-compute and cache GPU-friendly representations."""
        # Convert to numpy arrays for GPU transfer
        self.np_weights = np.array(self.weights, dtype=np.float32)
        self.np_phases = np.array(self.phase_angles, dtype=np.float32)
        
        # Compute complex components
        self.real_part = self.np_weights * np.cos(self.np_phases)
        self.imag_part = self.np_weights * np.sin(self.np_phases)
    
    def get_complex_components(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get pre-computed real and imaginary components.
        
        Returns:
            Tuple of (real_part, imag_part) as numpy arrays
        """
        if not hasattr(self, 'real_part'):
            self._precompute_gpu_state()
        
        return self.real_part, self.imag_part


class GPUProbeSynthesizer(ProbeSynthesizer):
    """
    GPU-accelerated probe synthesizer.
    
    Extends the standard synthesizer with optional GPU acceleration
    while maintaining full backward compatibility.
    """
    
    def __init__(
        self,
        taper_alpha: float = ProbeSynthesizer.DEFAULT_TAPER_ALPHA,
        use_gpu: bool = True,
        device_id: int = 0
    ):
        """
        Initialize GPU-accelerated probe synthesizer.
        
        Args:
            taper_alpha: Taper parameter for weighted probes
            use_gpu: Enable GPU acceleration if available
            device_id: GPU device ID for multi-GPU systems
        """
        super().__init__(taper_alpha)
        
        # Initialize GPU accelerator if requested and available
        self.accelerator: Optional[GPUAccelerator] = None
        if use_gpu and is_gpu_available():
            try:
                self.accelerator = create_accelerator(prefer_gpu=True, device_id=device_id)
                logger.info(f"GPU acceleration enabled: {self.accelerator}")
            except Exception as e:
                logger.warning(f"Failed to initialize GPU acceleration: {e}")
                logger.info("Falling back to CPU")
        else:
            if use_gpu:
                logger.info("GPU requested but not available, using CPU")
    
    def synthesize_probe(
        self,
        primes: List[int],
        phase_angles: List[float],
        use_tapered: bool = True
    ) -> GPUProbeState:
        """
        Synthesize a GPU-accelerated probe state.
        
        Args:
            primes: List of prime numbers
            phase_angles: Phase angles for each prime
            use_tapered: Use tapered weights if True
            
        Returns:
            GPUProbeState object with optional GPU tensors
        """
        if len(primes) != len(phase_angles):
            raise ValueError("primes and phase_angles must have same length")
        
        # Generate weights using parent class method
        if use_tapered:
            weights = self._compute_tapered_weights(len(primes))
        else:
            weights = None
        
        return GPUProbeState(primes, phase_angles, weights, self.accelerator)
    
    def compute_overlap(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]]
    ) -> float:
        """
        Compute overlap using GPU if available.
        
        Falls back to CPU computation if GPU not available or
        if probe is not a GPUProbeState.
        
        Args:
            probe: Probe state
            address_phases: Address phases
            
        Returns:
            Overlap magnitude R
        """
        # Use GPU acceleration if available
        if self.accelerator is not None and isinstance(probe, GPUProbeState):
            return self._compute_overlap_gpu(probe, address_phases)
        
        # Fall back to CPU computation
        return super().compute_overlap(probe, address_phases)
    
    def _compute_overlap_gpu(
        self,
        probe: GPUProbeState,
        address_phases: Dict[int, List[float]]
    ) -> float:
        """
        GPU-accelerated overlap computation.
        
        Args:
            probe: GPU probe state
            address_phases: Address phases
            
        Returns:
            Overlap magnitude
        """
        # Build address state complex components
        k_primes = len(probe.primes)
        address_real = np.zeros(k_primes, dtype=np.float32)
        address_imag = np.zeros(k_primes, dtype=np.float32)
        
        for i, prime in enumerate(probe.primes):
            if prime in address_phases and address_phases[prime]:
                # Use first symbol's phase (simplified)
                phase = address_phases[prime][0]
                address_real[i] = np.cos(phase)
                address_imag[i] = np.sin(phase)
        
        # Get probe components
        probe_real, probe_imag = probe.get_complex_components()
        
        # Compute overlap on GPU
        overlap = self.accelerator.compute_overlap(
            probe_real, probe_imag,
            address_real, address_imag
        )
        
        return overlap
    
    def refine_probe(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]],
        learning_rate: float = 0.1
    ) -> ProbeState:
        """
        Refine probe using GPU gradient descent if available.
        
        Args:
            probe: Current probe state
            address_phases: Target address phases
            learning_rate: Learning rate for refinement
            
        Returns:
            Refined probe state
        """
        # Use GPU acceleration if available
        if self.accelerator is not None and isinstance(probe, GPUProbeState):
            return self._refine_probe_gpu(probe, address_phases, learning_rate)
        
        # Fall back to CPU refinement
        return super().refine_probe(probe, address_phases, learning_rate)
    
    def _refine_probe_gpu(
        self,
        probe: GPUProbeState,
        address_phases: Dict[int, List[float]],
        learning_rate: float
    ) -> GPUProbeState:
        """
        GPU-accelerated probe refinement.
        
        Args:
            probe: Current GPU probe state
            address_phases: Target address phases
            learning_rate: Learning rate
            
        Returns:
            Refined GPU probe state
        """
        # Build address state
        k_primes = len(probe.primes)
        address_real = np.zeros(k_primes, dtype=np.float32)
        address_imag = np.zeros(k_primes, dtype=np.float32)
        
        for i, prime in enumerate(probe.primes):
            if prime in address_phases and address_phases[prime]:
                phase = address_phases[prime][0]
                address_real[i] = np.cos(phase)
                address_imag[i] = np.sin(phase)
        
        # Get current probe components
        probe_real, probe_imag = probe.get_complex_components()
        
        # Perform gradient descent on GPU
        new_real, new_imag = self.accelerator.update_probe_gradient(
            probe_real, probe_imag,
            address_real, address_imag,
            learning_rate
        )
        
        # Extract new phases from complex components
        new_phases = np.arctan2(new_imag, new_real).tolist()
        
        # Create refined probe
        return GPUProbeState(
            probe.primes,
            new_phases,
            probe.weights,
            self.accelerator
        )
    
    def batch_compute_overlap(
        self,
        probes: List[ProbeState],
        address_phases: Dict[int, List[float]]
    ) -> List[float]:
        """
        Compute overlap for multiple probes in parallel on GPU.
        
        Significantly faster than sequential computation for large batches.
        
        Args:
            probes: List of probe states
            address_phases: Address phases
            
        Returns:
            List of overlap values
        """
        if self.accelerator is None or not all(isinstance(p, GPUProbeState) for p in probes):
            # Fall back to sequential CPU computation
            return [self.compute_overlap(p, address_phases) for p in probes]
        
        # Build address state
        k_primes = len(probes[0].primes)
        address_real = np.zeros(k_primes, dtype=np.float32)
        address_imag = np.zeros(k_primes, dtype=np.float32)
        
        for i, prime in enumerate(probes[0].primes):
            if prime in address_phases and address_phases[prime]:
                phase = address_phases[prime][0]
                address_real[i] = np.cos(phase)
                address_imag[i] = np.sin(phase)
        
        # Collect all probe states
        probe_states = [p.get_complex_components() for p in probes]
        
        # Batch compute on GPU
        overlaps = self.accelerator.batch_overlap(
            probe_states,
            address_real,
            address_imag
        )
        
        return overlaps.tolist()
    
    def get_acceleration_stats(self) -> Dict[str, Any]:
        """
        Get GPU acceleration statistics.
        
        Returns:
            Dictionary with acceleration information
        """
        if self.accelerator is None:
            return {
                "enabled": False,
                "backend": "cpu"
            }
        
        stats = self.accelerator.get_memory_stats()
        stats["enabled"] = True
        
        return stats
    
    def clear_gpu_cache(self):
        """Clear GPU memory cache if using GPU acceleration."""
        if self.accelerator is not None:
            self.accelerator.clear_cache()


# Convenience function for backward compatibility
def create_probe_synthesizer(
    taper_alpha: float = ProbeSynthesizer.DEFAULT_TAPER_ALPHA,
    use_gpu: bool = True,
    device_id: int = 0
) -> ProbeSynthesizer:
    """
    Create probe synthesizer with automatic GPU detection.
    
    Args:
        taper_alpha: Taper parameter
        use_gpu: Enable GPU if available
        device_id: GPU device ID
        
    Returns:
        GPUProbeSynthesizer if GPU available, otherwise ProbeSynthesizer
    """
    if use_gpu and is_gpu_available():
        return GPUProbeSynthesizer(taper_alpha, use_gpu=True, device_id=device_id)
    else:
        return ProbeSynthesizer(taper_alpha)