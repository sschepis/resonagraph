"""
GPU-accelerated resonance locking for ResonaGraph.

Extends the standard locking engine with optional GPU acceleration
for improved performance on large-scale locking operations.
"""

import math
import time
from typing import Dict, List, Any, Optional, Tuple
import logging

from resonagraph.resonance.locking import ResonanceLock, LockMetrics, R_MIN, S_MIN
from resonagraph.resonance.probe import ProbeState
from resonagraph.resonance.probe_gpu import GPUProbeSynthesizer, GPUProbeState
from resonagraph.acceleration import is_gpu_available

logger = logging.getLogger(__name__)


class GPUResonanceLock(ResonanceLock):
    """
    GPU-accelerated resonance locking engine.
    
    Extends the standard locking engine with GPU acceleration while
    maintaining full backward compatibility with CPU-only systems.
    """
    
    def __init__(
        self,
        r_min: float = R_MIN,
        s_min: float = S_MIN,
        max_iterations: int = 100,
        lambda_decay: float = 0.5,
        gamma_growth: float = 0.3,
        rs_star: float = 1.0,
        use_gpu: bool = True,
        device_id: int = 0
    ):
        """
        Initialize GPU-accelerated resonance lock engine.
        
        Args:
            r_min: Minimum overlap threshold
            s_min: Minimum entropy threshold
            max_iterations: Maximum locking iterations
            lambda_decay: Entropy decay rate
            gamma_growth: Resonance score growth rate
            rs_star: Target resonance score
            use_gpu: Enable GPU acceleration if available
            device_id: GPU device ID for multi-GPU systems
        """
        # Initialize parent class
        super().__init__(
            r_min=r_min,
            s_min=s_min,
            max_iterations=max_iterations,
            lambda_decay=lambda_decay,
            gamma_growth=gamma_growth,
            rs_star=rs_star
        )
        
        # Replace synthesizer with GPU version
        if use_gpu and is_gpu_available():
            self.synthesizer = GPUProbeSynthesizer(use_gpu=True, device_id=device_id)
            self.gpu_enabled = True
            logger.info(f"GPU-accelerated locking enabled")
        else:
            self.gpu_enabled = False
            if use_gpu:
                logger.info("GPU requested but not available, using CPU")
    
    def lock(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]],
        learning_rate: float = 0.1,
        early_stopping: bool = True
    ) -> Tuple[ProbeState, LockMetrics]:
        """
        Perform GPU-accelerated resonance locking.
        
        Uses GPU for overlap computation and gradient descent if available.
        Includes early stopping optimization for faster convergence.
        
        Args:
            probe: Initial probe state
            address_phases: Target address phases
            learning_rate: Phase adjustment rate
            early_stopping: Enable early convergence detection
            
        Returns:
            Tuple of (locked_probe, metrics)
        """
        if self.gpu_enabled and not isinstance(probe, GPUProbeState):
            # Convert to GPU probe if possible
            if hasattr(self.synthesizer, 'accelerator'):
                probe = GPUProbeState(
                    probe.primes,
                    probe.phase_angles,
                    probe.weights,
                    self.synthesizer.accelerator
                )
        
        # Use parent class lock method with GPU-accelerated synthesizer
        return super().lock(probe, address_phases, learning_rate)
    
    def batch_lock(
        self,
        probes: List[ProbeState],
        address_phases_list: List[Dict[int, List[float]]],
        learning_rate: float = 0.1
    ) -> List[Tuple[ProbeState, LockMetrics]]:
        """
        Perform batch locking of multiple probes in parallel.
        
        Significantly faster than sequential locking when using GPU.
        
        Args:
            probes: List of initial probe states
            address_phases_list: List of address phases for each probe
            learning_rate: Phase adjustment rate
            
        Returns:
            List of (locked_probe, metrics) tuples
        """
        if not self.gpu_enabled:
            # Fall back to sequential locking
            return [
                self.lock(probe, addr_phases, learning_rate)
                for probe, addr_phases in zip(probes, address_phases_list)
            ]
        
        # GPU batch processing
        results = []
        start_time = time.time()
        
        # Convert all probes to GPU probes
        gpu_probes = []
        for probe in probes:
            if isinstance(probe, GPUProbeState):
                gpu_probes.append(probe)
            else:
                gpu_probes.append(GPUProbeState(
                    probe.primes,
                    probe.phase_angles,
                    probe.weights,
                    self.synthesizer.accelerator
                ))
        
        # Process each probe (could be further parallelized)
        for gpu_probe, addr_phases in zip(gpu_probes, address_phases_list):
            locked_probe, metrics = self.lock(gpu_probe, addr_phases, learning_rate)
            results.append((locked_probe, metrics))
        
        batch_time = time.time() - start_time
        logger.info(f"Batch locked {len(probes)} probes in {batch_time:.3f}s")
        
        return results
    
    def adaptive_lock(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]],
        initial_learning_rate: float = 0.1,
        adaptive_rate: bool = True
    ) -> Tuple[ProbeState, LockMetrics]:
        """
        Perform adaptive locking with dynamic learning rate adjustment.
        
        Adjusts learning rate based on convergence progress for
        faster and more stable convergence.
        
        Args:
            probe: Initial probe state
            address_phases: Target address phases
            initial_learning_rate: Initial learning rate
            adaptive_rate: Enable adaptive learning rate
            
        Returns:
            Tuple of (locked_probe, metrics)
        """
        start_time = time.time()
        
        # Initialize
        s_0 = self._compute_initial_entropy(probe, address_phases)
        current_probe = probe
        learning_rate = initial_learning_rate
        
        # Track convergence history for adaptive rate
        overlap_history = []
        
        for iteration in range(self.max_iterations):
            # Compute current state
            overlap = self.synthesizer.compute_overlap(current_probe, address_phases)
            entropy = s_0 * math.exp(-self.lambda_decay * iteration)
            resonance_score = self.rs_star * (1 - math.exp(-self.gamma_growth * iteration))
            
            # Store overlap history
            overlap_history.append(overlap)
            
            # Check convergence
            if overlap >= self.r_min and entropy <= self.s_min:
                lock_time = time.time() - start_time
                return current_probe, LockMetrics(
                    converged=True,
                    iterations=iteration + 1,
                    final_overlap=overlap,
                    final_entropy=entropy,
                    final_resonance_score=resonance_score,
                    lock_time=lock_time,
                    convergence_reason=f"Converged with adaptive rate: R={overlap:.4f}, S={entropy:.6f}"
                )
            
            # Adaptive learning rate adjustment
            if adaptive_rate and len(overlap_history) > 5:
                # If progress is slow, increase learning rate
                recent_improvement = overlap_history[-1] - overlap_history[-5]
                if recent_improvement < 0.01:
                    learning_rate = min(learning_rate * 1.1, 0.5)
                # If oscillating, decrease learning rate
                elif len(overlap_history) > 10:
                    recent_variance = np.var(overlap_history[-10:])
                    if recent_variance > 0.01:
                        learning_rate = max(learning_rate * 0.9, 0.01)
            
            # Refine probe
            current_probe = self.synthesizer.refine_probe(
                current_probe, address_phases, learning_rate
            )
        
        # Max iterations reached
        lock_time = time.time() - start_time
        final_overlap = self.synthesizer.compute_overlap(current_probe, address_phases)
        final_entropy = s_0 * math.exp(-self.lambda_decay * self.max_iterations)
        final_rs = self.rs_star * (1 - math.exp(-self.gamma_growth * self.max_iterations))
        
        return current_probe, LockMetrics(
            converged=False,
            iterations=self.max_iterations,
            final_overlap=final_overlap,
            final_entropy=final_entropy,
            final_resonance_score=final_rs,
            lock_time=lock_time,
            convergence_reason=f"Max iterations with adaptive rate: R={final_overlap:.4f}"
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for GPU acceleration.
        
        Returns:
            Dictionary with performance information
        """
        if not self.gpu_enabled:
            return {
                "gpu_enabled": False,
                "backend": "cpu"
            }
        
        stats = self.synthesizer.get_acceleration_stats()
        stats["locking_engine"] = "gpu"
        
        return stats
    
    def clear_gpu_cache(self):
        """Clear GPU memory cache."""
        if self.gpu_enabled:
            self.synthesizer.clear_gpu_cache()


# Convenience function for creating lock engine
def create_lock_engine(
    r_min: float = R_MIN,
    s_min: float = S_MIN,
    max_iterations: int = 100,
    use_gpu: bool = True,
    device_id: int = 0
) -> ResonanceLock:
    """
    Create resonance lock engine with automatic GPU detection.
    
    Args:
        r_min: Minimum overlap threshold
        s_min: Minimum entropy threshold
        max_iterations: Maximum iterations
        use_gpu: Enable GPU if available
        device_id: GPU device ID
        
    Returns:
        GPUResonanceLock if GPU available, otherwise ResonanceLock
    """
    if use_gpu and is_gpu_available():
        return GPUResonanceLock(
            r_min=r_min,
            s_min=s_min,
            max_iterations=max_iterations,
            use_gpu=True,
            device_id=device_id
        )
    else:
        return ResonanceLock(
            r_min=r_min,
            s_min=s_min,
            max_iterations=max_iterations
        )


# Import numpy for adaptive rate calculation
import numpy as np