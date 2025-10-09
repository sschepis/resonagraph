"""
Phase 7.1 Demo: GPU Acceleration for ResonaGraph

Demonstrates cross-platform GPU acceleration using PyTorch:
- Automatic backend detection (CUDA, MPS, CPU)
- GPU-accelerated probe synthesis and locking
- Performance comparison: CPU vs GPU
- Batch processing capabilities
"""

import time
import numpy as np
from typing import List

# Import standard modules
from resonagraph.resonance.probe import ProbeSynthesizer, ProbeState
from resonagraph.resonance.locking import ResonanceLock

# Import GPU-accelerated modules
try:
    from resonagraph.acceleration import (
        get_available_backend,
        is_gpu_available,
        create_accelerator
    )
    from resonagraph.resonance.probe_gpu import GPUProbeSynthesizer
    from resonagraph.resonance.locking_gpu import GPUResonanceLock, create_lock_engine
    GPU_AVAILABLE = True
except ImportError as e:
    print(f"GPU modules not available: {e}")
    print("Install PyTorch: pip install torch")
    GPU_AVAILABLE = False
    exit(1)


def demo_backend_detection():
    """Demonstrate GPU backend detection."""
    print("=" * 70)
    print("GPU Backend Detection")
    print("=" * 70)
    
    backend = get_available_backend()
    print(f"Available backend: {backend.value}")
    
    gpu_available = is_gpu_available()
    print(f"GPU available: {gpu_available}")
    
    if gpu_available:
        accelerator = create_accelerator(prefer_gpu=True)
        print(f"Accelerator: {accelerator}")
        
        # Get memory stats
        stats = accelerator.get_memory_stats()
        print(f"\nMemory stats:")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f} MB")
            else:
                print(f"  {key}: {value}")
    else:
        print("Using CPU fallback")
    
    print()


def demo_probe_synthesis():
    """Demonstrate GPU-accelerated probe synthesis."""
    print("=" * 70)
    print("GPU-Accelerated Probe Synthesis")
    print("=" * 70)
    
    # Create test data
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53]
    phases = [i * 0.1 for i in range(len(primes))]
    
    # CPU synthesizer
    print("\nCPU Probe Synthesis:")
    cpu_synth = ProbeSynthesizer(taper_alpha=0.1)
    
    start = time.perf_counter()
    cpu_probe = cpu_synth.synthesize_probe(primes, phases, use_tapered=True)
    cpu_time = time.perf_counter() - start
    
    print(f"  Time: {cpu_time*1000:.3f}ms")
    print(f"  Probe: {cpu_probe}")
    
    # GPU synthesizer
    if GPU_AVAILABLE:
        print("\nGPU Probe Synthesis:")
        gpu_synth = GPUProbeSynthesizer(taper_alpha=0.1, use_gpu=True)
        
        start = time.perf_counter()
        gpu_probe = gpu_synth.synthesize_probe(primes, phases, use_tapered=True)
        gpu_time = time.perf_counter() - start
        
        print(f"  Time: {gpu_time*1000:.3f}ms")
        print(f"  Probe: {gpu_probe}")
        print(f"  Speedup: {cpu_time/gpu_time:.2f}x")
        
        # Get acceleration stats
        stats = gpu_synth.get_acceleration_stats()
        print(f"  Acceleration: {stats['backend']}")
    
    print()


def demo_overlap_computation():
    """Demonstrate GPU-accelerated overlap computation."""
    print("=" * 70)
    print("GPU-Accelerated Overlap Computation")
    print("=" * 70)
    
    # Create test data
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    probe_phases = [0.1] * len(primes)
    address_phases = {p: [0.15] for p in primes}
    
    # CPU overlap
    print("\nCPU Overlap Computation:")
    cpu_synth = ProbeSynthesizer()
    cpu_probe = cpu_synth.synthesize_probe(primes, probe_phases)
    
    start = time.perf_counter()
    for _ in range(1000):
        cpu_overlap = cpu_synth.compute_overlap(cpu_probe, address_phases)
    cpu_time = time.perf_counter() - start
    
    print(f"  1000 overlaps in {cpu_time:.3f}s ({1000/cpu_time:.1f} ops/s)")
    print(f"  Overlap value: {cpu_overlap:.4f}")
    
    # GPU overlap
    if GPU_AVAILABLE:
        print("\nGPU Overlap Computation:")
        gpu_synth = GPUProbeSynthesizer(use_gpu=True)
        gpu_probe = gpu_synth.synthesize_probe(primes, probe_phases)
        
        start = time.perf_counter()
        for _ in range(1000):
            gpu_overlap = gpu_synth.compute_overlap(gpu_probe, address_phases)
        gpu_time = time.perf_counter() - start
        
        print(f"  1000 overlaps in {gpu_time:.3f}s ({1000/gpu_time:.1f} ops/s)")
        print(f"  Overlap value: {gpu_overlap:.4f}")
        print(f"  Speedup: {cpu_time/gpu_time:.2f}x")
        print(f"  Result difference: {abs(cpu_overlap - gpu_overlap):.6f}")
    
    print()


def demo_resonance_locking():
    """Demonstrate GPU-accelerated resonance locking."""
    print("=" * 70)
    print("GPU-Accelerated Resonance Locking")
    print("=" * 70)
    
    # Create test data
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    initial_phases = [0.5] * len(primes)
    target_phases = {p: [0.1] for p in primes}
    
    # CPU locking
    print("\nCPU Resonance Locking:")
    cpu_lock = ResonanceLock(max_iterations=50, r_min=0.95, s_min=0.01)
    cpu_probe = cpu_lock.synthesizer.synthesize_probe(primes, initial_phases)
    
    start = time.perf_counter()
    cpu_locked, cpu_metrics = cpu_lock.lock(cpu_probe, target_phases)
    cpu_time = time.perf_counter() - start
    
    print(f"  Time: {cpu_time:.3f}s")
    print(f"  Converged: {cpu_metrics.converged}")
    print(f"  Iterations: {cpu_metrics.iterations}")
    print(f"  Final overlap: {cpu_metrics.final_overlap:.4f}")
    print(f"  Final entropy: {cpu_metrics.final_entropy:.6f}")
    
    # GPU locking
    if GPU_AVAILABLE:
        print("\nGPU Resonance Locking:")
        gpu_lock = create_lock_engine(
            max_iterations=50,
            r_min=0.95,
            s_min=0.01,
            use_gpu=True
        )
        gpu_probe = gpu_lock.synthesizer.synthesize_probe(primes, initial_phases)
        
        start = time.perf_counter()
        gpu_locked, gpu_metrics = gpu_lock.lock(gpu_probe, target_phases)
        gpu_time = time.perf_counter() - start
        
        print(f"  Time: {gpu_time:.3f}s")
        print(f"  Converged: {gpu_metrics.converged}")
        print(f"  Iterations: {gpu_metrics.iterations}")
        print(f"  Final overlap: {gpu_metrics.final_overlap:.4f}")
        print(f"  Final entropy: {gpu_metrics.final_entropy:.6f}")
        print(f"  Speedup: {cpu_time/gpu_time:.2f}x")
        
        # Performance stats
        perf_stats = gpu_lock.get_performance_stats()
        print(f"  Backend: {perf_stats.get('backend', 'N/A')}")
    
    print()


def demo_batch_processing():
    """Demonstrate batch GPU processing."""
    print("=" * 70)
    print("Batch GPU Processing")
    print("=" * 70)
    
    if not GPU_AVAILABLE:
        print("GPU not available for batch processing")
        return
    
    # Create multiple probes
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    num_probes = 20
    
    print(f"\nProcessing {num_probes} probes:")
    
    gpu_synth = GPUProbeSynthesizer(use_gpu=True)
    
    # Create probe batch
    probes = []
    for i in range(num_probes):
        phases = [float(i) * 0.05] * len(primes)
        probe = gpu_synth.synthesize_probe(primes, phases)
        probes.append(probe)
    
    address_phases = {p: [0.5] for p in primes}
    
    # Sequential processing
    print("\nSequential Processing:")
    start = time.perf_counter()
    sequential_overlaps = [
        gpu_synth.compute_overlap(p, address_phases) for p in probes
    ]
    sequential_time = time.perf_counter() - start
    print(f"  Time: {sequential_time:.3f}s")
    
    # Batch processing
    print("\nBatch Processing:")
    start = time.perf_counter()
    batch_overlaps = gpu_synth.batch_compute_overlap(probes, address_phases)
    batch_time = time.perf_counter() - start
    print(f"  Time: {batch_time:.3f}s")
    print(f"  Speedup: {sequential_time/batch_time:.2f}x")
    
    # Verify results match
    max_diff = max(abs(s - b) for s, b in zip(sequential_overlaps, batch_overlaps))
    print(f"  Max difference: {max_diff:.6f}")
    
    print()


def demo_adaptive_locking():
    """Demonstrate adaptive learning rate locking."""
    print("=" * 70)
    print("Adaptive Learning Rate Locking")
    print("=" * 70)
    
    if not GPU_AVAILABLE:
        print("GPU not available")
        return
    
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    initial_phases = [1.0] * len(primes)
    target_phases = {p: [0.0] for p in primes}
    
    gpu_lock = GPUResonanceLock(max_iterations=100, use_gpu=True)
    probe = gpu_lock.synthesizer.synthesize_probe(primes, initial_phases)
    
    # Standard locking
    print("\nStandard Locking:")
    start = time.perf_counter()
    std_locked, std_metrics = gpu_lock.lock(probe, target_phases, learning_rate=0.1)
    std_time = time.perf_counter() - start
    
    print(f"  Time: {std_time:.3f}s")
    print(f"  Iterations: {std_metrics.iterations}")
    print(f"  Final overlap: {std_metrics.final_overlap:.4f}")
    
    # Adaptive locking
    print("\nAdaptive Locking:")
    probe = gpu_lock.synthesizer.synthesize_probe(primes, initial_phases)
    
    start = time.perf_counter()
    adp_locked, adp_metrics = gpu_lock.adaptive_lock(
        probe, target_phases, initial_learning_rate=0.1
    )
    adp_time = time.perf_counter() - start
    
    print(f"  Time: {adp_time:.3f}s")
    print(f"  Iterations: {adp_metrics.iterations}")
    print(f"  Final overlap: {adp_metrics.final_overlap:.4f}")
    print(f"  Time improvement: {(std_time - adp_time)/std_time * 100:.1f}%")
    
    print()


def demo_memory_management():
    """Demonstrate GPU memory management."""
    print("=" * 70)
    print("GPU Memory Management")
    print("=" * 70)
    
    if not GPU_AVAILABLE:
        print("GPU not available")
        return
    
    accelerator = create_accelerator(prefer_gpu=True)
    
    print("\nInitial Memory State:")
    stats = accelerator.get_memory_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f} MB")
        else:
            print(f"  {key}: {value}")
    
    # Create large tensors
    print("\nCreating large tensors...")
    large_arrays = []
    for _ in range(10):
        array = np.random.randn(10000).astype(np.float32)
        tensor = accelerator.to_tensor(array)
        large_arrays.append(tensor)
    
    print("After tensor creation:")
    stats = accelerator.get_memory_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f} MB")
        else:
            print(f"  {key}: {value}")
    
    # Clear cache
    print("\nClearing GPU cache...")
    accelerator.clear_cache()
    
    print("After cache clear:")
    stats = accelerator.get_memory_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f} MB")
        else:
            print(f"  {key}: {value}")
    
    print()


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("ResonaGraph Phase 7.1: GPU Acceleration Demo")
    print("=" * 70 + "\n")
    
    demo_backend_detection()
    demo_probe_synthesis()
    demo_overlap_computation()
    demo_resonance_locking()
    demo_batch_processing()
    demo_adaptive_locking()
    demo_memory_management()
    
    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()