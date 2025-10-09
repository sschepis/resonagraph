"""
Tests for GPU acceleration functionality.

Tests cover:
- Backend detection and initialization
- GPU operations correctness
- CPU/GPU parity
- Performance benchmarks
- Multi-backend support (CUDA, MPS, CPU)
"""

import pytest
import numpy as np
import time
from typing import List, Tuple

# Try importing GPU modules
try:
    from resonagraph.acceleration import (
        GPUBackend,
        GPUAccelerator,
        get_available_backend,
        is_gpu_available,
        create_accelerator
    )
    from resonagraph.resonance.probe_gpu import (
        GPUProbeState,
        GPUProbeSynthesizer,
        create_probe_synthesizer
    )
    from resonagraph.resonance.locking_gpu import (
        GPUResonanceLock,
        create_lock_engine
    )
    GPU_AVAILABLE = True
except ImportError as e:
    GPU_AVAILABLE = False
    pytest.skip(f"GPU modules not available: {e}", allow_module_level=True)


class TestBackendDetection:
    """Test GPU backend detection and initialization."""
    
    def test_get_available_backend(self):
        """Test backend detection."""
        backend = get_available_backend()
        assert isinstance(backend, GPUBackend)
        # Should be one of the supported backends
        assert backend in [GPUBackend.CUDA, GPUBackend.MPS, GPUBackend.CPU]
    
    def test_is_gpu_available(self):
        """Test GPU availability check."""
        available = is_gpu_available()
        assert isinstance(available, bool)
    
    def test_create_accelerator_auto(self):
        """Test accelerator creation with auto-detection."""
        accelerator = create_accelerator(prefer_gpu=True)
        assert isinstance(accelerator, GPUAccelerator)
        assert accelerator.device is not None
    
    def test_create_accelerator_cpu_fallback(self):
        """Test CPU fallback when GPU disabled."""
        accelerator = create_accelerator(prefer_gpu=False)
        assert isinstance(accelerator, GPUAccelerator)
        assert accelerator.backend == GPUBackend.CPU
    
    def test_accelerator_repr(self):
        """Test accelerator string representation."""
        accelerator = create_accelerator()
        repr_str = repr(accelerator)
        assert "GPUAccelerator" in repr_str
        assert "backend" in repr_str


class TestGPUOperations:
    """Test basic GPU operations."""
    
    @pytest.fixture
    def accelerator(self):
        """Create GPU accelerator for testing."""
        return create_accelerator(prefer_gpu=True)
    
    def test_to_tensor_conversion(self, accelerator):
        """Test numpy to tensor conversion."""
        array = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        tensor = accelerator.to_tensor(array)
        assert tensor.shape == array.shape
    
    def test_to_numpy_conversion(self, accelerator):
        """Test tensor to numpy conversion."""
        array = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        tensor = accelerator.to_tensor(array)
        result = accelerator.to_numpy(tensor)
        np.testing.assert_array_almost_equal(result, array)
    
    def test_synthesize_probe(self, accelerator):
        """Test probe synthesis on GPU."""
        prime_indices = np.array([2, 3, 5, 7, 11], dtype=np.int32)
        real, imag = accelerator.synthesize_probe(prime_indices)
        
        assert real.shape == prime_indices.shape
        assert imag.shape == prime_indices.shape
        assert isinstance(real, np.ndarray)
        assert isinstance(imag, np.ndarray)
    
    def test_compute_overlap(self, accelerator):
        """Test overlap computation on GPU."""
        k = 5
        probe_real = np.random.randn(k).astype(np.float32)
        probe_imag = np.random.randn(k).astype(np.float32)
        beacon_real = np.random.randn(k).astype(np.float32)
        beacon_imag = np.random.randn(k).astype(np.float32)
        
        overlap = accelerator.compute_overlap(
            probe_real, probe_imag,
            beacon_real, beacon_imag
        )
        
        assert isinstance(overlap, float)
        assert 0.0 <= overlap <= 1.0
    
    def test_compute_overlap_identity(self, accelerator):
        """Test overlap of identical states is 1.0."""
        k = 5
        state_real = np.random.randn(k).astype(np.float32)
        state_imag = np.random.randn(k).astype(np.float32)
        
        overlap = accelerator.compute_overlap(
            state_real, state_imag,
            state_real, state_imag
        )
        
        assert abs(overlap - 1.0) < 0.01  # Should be ~1.0
    
    def test_compute_phase_differences(self, accelerator):
        """Test phase difference computation."""
        k = 5
        probe_phases = np.random.rand(k).astype(np.float32) * 2 * np.pi
        beacon_phases = np.random.rand(k).astype(np.float32) * 2 * np.pi
        
        differences = accelerator.compute_phase_differences(
            probe_phases, beacon_phases
        )
        
        assert differences.shape == (k,)
        # Should be in [-π, π]
        assert np.all(differences >= -np.pi)
        assert np.all(differences <= np.pi)
    
    def test_update_probe_gradient(self, accelerator):
        """Test gradient-based probe update."""
        k = 5
        probe_real = np.random.randn(k).astype(np.float32)
        probe_imag = np.random.randn(k).astype(np.float32)
        beacon_real = np.random.randn(k).astype(np.float32)
        beacon_imag = np.random.randn(k).astype(np.float32)
        
        new_real, new_imag = accelerator.update_probe_gradient(
            probe_real, probe_imag,
            beacon_real, beacon_imag,
            learning_rate=0.1
        )
        
        assert new_real.shape == (k,)
        assert new_imag.shape == (k,)
        # States should be different after update
        assert not np.allclose(new_real, probe_real)
    
    def test_batch_overlap(self, accelerator):
        """Test batch overlap computation."""
        k = 5
        num_probes = 10
        
        # Create batch of probes
        probe_states = []
        for _ in range(num_probes):
            real = np.random.randn(k).astype(np.float32)
            imag = np.random.randn(k).astype(np.float32)
            probe_states.append((real, imag))
        
        beacon_real = np.random.randn(k).astype(np.float32)
        beacon_imag = np.random.randn(k).astype(np.float32)
        
        overlaps = accelerator.batch_overlap(
            probe_states,
            beacon_real,
            beacon_imag
        )
        
        assert len(overlaps) == num_probes
        assert all(0.0 <= o <= 1.0 for o in overlaps)


class TestGPUProbeState:
    """Test GPU-accelerated probe state."""
    
    def test_create_gpu_probe(self):
        """Test GPU probe state creation."""
        primes = [2, 3, 5, 7, 11]
        phases = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        accelerator = create_accelerator()
        probe = GPUProbeState(primes, phases, accelerator=accelerator)
        
        assert probe.primes == primes
        assert probe.phase_angles == phases
        assert probe.accelerator is not None
    
    def test_gpu_probe_complex_components(self):
        """Test complex component extraction."""
        primes = [2, 3, 5, 7, 11]
        phases = [0.0, np.pi/2, np.pi, 3*np.pi/2, 2*np.pi]
        
        accelerator = create_accelerator()
        probe = GPUProbeState(primes, phases, accelerator=accelerator)
        
        real, imag = probe.get_complex_components()
        
        assert real.shape == (len(primes),)
        assert imag.shape == (len(primes),)


class TestGPUProbeSynthesizer:
    """Test GPU-accelerated probe synthesizer."""
    
    @pytest.fixture
    def synthesizer(self):
        """Create GPU synthesizer for testing."""
        return GPUProbeSynthesizer(use_gpu=True)
    
    def test_create_synthesizer(self):
        """Test synthesizer creation."""
        synth = create_probe_synthesizer(use_gpu=True)
        assert synth is not None
    
    def test_synthesize_probe(self, synthesizer):
        """Test probe synthesis."""
        primes = [2, 3, 5, 7, 11]
        phases = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        probe = synthesizer.synthesize_probe(primes, phases)
        
        assert isinstance(probe, GPUProbeState)
        assert probe.primes == primes
        assert probe.phase_angles == phases
    
    def test_compute_overlap_gpu(self, synthesizer):
        """Test overlap computation with GPU."""
        primes = [2, 3, 5, 7, 11]
        phases = [0.0, 0.0, 0.0, 0.0, 0.0]
        
        probe = synthesizer.synthesize_probe(primes, phases)
        
        # Create matching address phases
        address_phases = {p: [0.0] for p in primes}
        
        overlap = synthesizer.compute_overlap(probe, address_phases)
        
        # Should have high overlap with matching phases
        assert overlap > 0.9
    
    def test_refine_probe_gpu(self, synthesizer):
        """Test probe refinement with GPU."""
        primes = [2, 3, 5, 7, 11]
        phases = [1.0, 1.0, 1.0, 1.0, 1.0]
        
        probe = synthesizer.synthesize_probe(primes, phases)
        
        # Target different phases
        address_phases = {p: [0.0] for p in primes}
        
        refined = synthesizer.refine_probe(probe, address_phases, learning_rate=0.1)
        
        assert isinstance(refined, GPUProbeState)
        # Phases should have changed toward target
        assert refined.phase_angles != probe.phase_angles
    
    def test_batch_compute_overlap(self, synthesizer):
        """Test batch overlap computation."""
        primes = [2, 3, 5, 7, 11]
        
        # Create multiple probes
        probes = []
        for i in range(5):
            phases = [float(i) * 0.1] * len(primes)
            probe = synthesizer.synthesize_probe(primes, phases)
            probes.append(probe)
        
        address_phases = {p: [0.0] for p in primes}
        
        overlaps = synthesizer.batch_compute_overlap(probes, address_phases)
        
        assert len(overlaps) == len(probes)
        assert all(isinstance(o, float) for o in overlaps)
    
    def test_get_acceleration_stats(self, synthesizer):
        """Test getting acceleration statistics."""
        stats = synthesizer.get_acceleration_stats()
        
        assert isinstance(stats, dict)
        assert "enabled" in stats
        assert "backend" in stats


class TestGPUResonanceLock:
    """Test GPU-accelerated resonance locking."""
    
    @pytest.fixture
    def lock_engine(self):
        """Create GPU lock engine for testing."""
        return create_lock_engine(use_gpu=True, max_iterations=20)
    
    def test_create_lock_engine(self):
        """Test lock engine creation."""
        engine = create_lock_engine(use_gpu=True)
        assert engine is not None
    
    def test_lock_converges(self, lock_engine):
        """Test that locking converges for matching states."""
        primes = [2, 3, 5, 7, 11]
        phases = [0.1, 0.1, 0.1, 0.1, 0.1]
        
        # Create probe via synthesizer to ensure GPU compatibility
        probe = lock_engine.synthesizer.synthesize_probe(primes, phases)
        
        # Create similar address phases
        address_phases = {p: [0.15] for p in primes}
        
        locked_probe, metrics = lock_engine.lock(probe, address_phases)
        
        assert metrics.converged or metrics.final_overlap > 0.8
        assert metrics.iterations > 0
        assert metrics.lock_time > 0
    
    def test_batch_lock(self, lock_engine):
        """Test batch locking of multiple probes."""
        primes = [2, 3, 5, 7, 11]
        
        # Create multiple probes
        probes = []
        address_phases_list = []
        
        for i in range(3):
            phases = [float(i) * 0.1] * len(primes)
            probe = lock_engine.synthesizer.synthesize_probe(primes, phases)
            probes.append(probe)
            
            addr_phases = {p: [float(i) * 0.1 + 0.05] for p in primes}
            address_phases_list.append(addr_phases)
        
        results = lock_engine.batch_lock(probes, address_phases_list)
        
        assert len(results) == len(probes)
        for locked_probe, metrics in results:
            assert locked_probe is not None
            assert metrics.iterations > 0
    
    def test_get_performance_stats(self, lock_engine):
        """Test getting performance statistics."""
        stats = lock_engine.get_performance_stats()
        
        assert isinstance(stats, dict)
        assert "gpu_enabled" in stats or "locking_engine" in stats


class TestCPUGPUParity:
    """Test that CPU and GPU produce equivalent results."""
    
    def test_overlap_parity(self):
        """Test CPU/GPU overlap computation parity."""
        from resonagraph.resonance.probe import ProbeSynthesizer
        
        k = 10
        primes = list(range(2, 2 + k))
        phases = np.random.rand(k).tolist()
        
        # CPU synthesizer
        cpu_synth = ProbeSynthesizer()
        cpu_probe = cpu_synth.synthesize_probe(primes, phases)
        
        # GPU synthesizer
        gpu_synth = GPUProbeSynthesizer(use_gpu=True)
        gpu_probe = gpu_synth.synthesize_probe(primes, phases)
        
        # Create address phases
        address_phases = {p: [np.random.rand()] for p in primes}
        
        # Compute overlaps
        cpu_overlap = cpu_synth.compute_overlap(cpu_probe, address_phases)
        gpu_overlap = gpu_synth.compute_overlap(gpu_probe, address_phases)
        
        # Should be very close (within floating point precision)
        assert abs(cpu_overlap - gpu_overlap) < 0.01


@pytest.mark.benchmark
class TestPerformance:
    """Performance benchmarks for GPU acceleration."""
    
    def test_overlap_performance(self):
        """Benchmark overlap computation performance."""
        k = 64  # Larger problem size
        
        # Create test data
        probe_real = np.random.randn(k).astype(np.float32)
        probe_imag = np.random.randn(k).astype(np.float32)
        beacon_real = np.random.randn(k).astype(np.float32)
        beacon_imag = np.random.randn(k).astype(np.float32)
        
        # GPU computation
        accelerator = create_accelerator(prefer_gpu=True)
        
        start = time.perf_counter()
        for _ in range(1000):
            overlap = accelerator.compute_overlap(
                probe_real, probe_imag,
                beacon_real, beacon_imag
            )
        gpu_time = time.perf_counter() - start
        
        print(f"\nGPU: 1000 overlaps in {gpu_time:.3f}s ({1000/gpu_time:.1f} ops/s)")
        
        # Should complete in reasonable time
        assert gpu_time < 10.0  # Less than 10 seconds
    
    def test_batch_performance(self):
        """Benchmark batch operation performance."""
        k = 32
        num_probes = 100
        
        # Create batch
        probe_states = []
        for _ in range(num_probes):
            real = np.random.randn(k).astype(np.float32)
            imag = np.random.randn(k).astype(np.float32)
            probe_states.append((real, imag))
        
        beacon_real = np.random.randn(k).astype(np.float32)
        beacon_imag = np.random.randn(k).astype(np.float32)
        
        # Batch computation
        accelerator = create_accelerator(prefer_gpu=True)
        
        start = time.perf_counter()
        overlaps = accelerator.batch_overlap(
            probe_states,
            beacon_real,
            beacon_imag
        )
        batch_time = time.perf_counter() - start
        
        print(f"\nBatch: {num_probes} overlaps in {batch_time:.3f}s ({num_probes/batch_time:.1f} ops/s)")
        
        assert len(overlaps) == num_probes


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])