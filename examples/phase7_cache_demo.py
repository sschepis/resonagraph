"""
Phase 7.3 Cache Demo - Caching and Performance Tuning

Demonstrates the ResonaGraph caching subsystem with:
- Beacon cache for fingerprint lookups
- Probe cache for query results
- Encoding cache for phase vectors
- Cache manager for unified statistics
- Performance improvements from caching
"""

import time
import numpy as np
from typing import List

from resonagraph.cache import (
    BeaconCache,
    ProbeCache,
    EncodingCache,
    CacheManager
)
from resonagraph.core.phase_encoding import PhaseEncoder


def demo_beacon_cache():
    """Demonstrate beacon caching."""
    print("\n" + "="*60)
    print("BEACON CACHE DEMO")
    print("="*60)
    
    # Create beacon cache
    cache = BeaconCache(max_size=100, ttl=300)
    
    print("\n1. Adding beacons to cache...")
    
    # Simulate beacon storage
    beacons = []
    for i in range(10):
        key = f"beacon_{i}"
        fingerprint = f"fingerprint_{i}".encode()
        epoch = int(time.time()) + i
        primes = [2, 3, 5, 7, 11][i % 5:]
        
        cache.put(key, fingerprint, epoch, primes)
        beacons.append(key)
    
    print(f"   Added {len(beacons)} beacons")
    
    # Demonstrate cache hits
    print("\n2. Cache hits (looking up existing beacons)...")
    start = time.time()
    for key in beacons[:5]:
        beacon = cache.get(key)
        print(f"   {key}: epoch={beacon.epoch}, primes={beacon.primes}")
    hit_time = time.time() - start
    
    # Demonstrate cache misses
    print("\n3. Cache misses (looking up non-existent beacons)...")
    start = time.time()
    for i in range(5):
        beacon = cache.get(f"missing_{i}")
        if beacon is None:
            print(f"   missing_{i}: Not found")
    miss_time = time.time() - start
    
    # Show statistics
    print("\n4. Cache statistics:")
    stats = cache.get_stats()
    print(f"   Size: {stats['size']}/{stats['max_size']}")
    print(f"   Hit rate: {stats['hit_rate']:.1%}")
    print(f"   Hits: {stats['hits']}, Misses: {stats['misses']}")
    print(f"   Evictions: {stats['evictions']}, Expirations: {stats['expirations']}")
    print(f"   Average hit time: {hit_time/5*1000:.2f}ms")
    print(f"   Average miss time: {miss_time/5*1000:.2f}ms")


def demo_probe_cache():
    """Demonstrate probe caching."""
    print("\n" + "="*60)
    print("PROBE CACHE DEMO")
    print("="*60)
    
    # Create probe cache
    cache = ProbeCache(max_size=50, ttl=600)
    
    print("\n1. Simulating probe queries...")
    
    # Simulate queries
    queries = [
        "What is quantum computing?",
        "How do neural networks work?",
        "Explain machine learning",
        "What is quantum computing?",  # Duplicate
        "Deep learning basics"
    ]
    
    for query in queries:
        # Compute query hash
        query_hash = ProbeCache.compute_query_hash(query, [2, 3, 5], 10)
        
        # Check cache
        cached = cache.get(query_hash)
        
        if cached is not None:
            print(f"   CACHE HIT: '{query}'")
            print(f"     Overlap: {cached.overlap:.3f}, Entropy: {cached.entropy:.3f}")
        else:
            print(f"   CACHE MISS: '{query}'")
            # Simulate probe computation
            probe_state = np.random.randn(64)
            overlap = 0.75 + np.random.random() * 0.2
            entropy = 1.0 + np.random.random() * 0.5
            
            # Cache the result
            cache.put(query_hash, probe_state, overlap, entropy, {'query': query})
            print(f"     Computed and cached: Overlap={overlap:.3f}, Entropy={entropy:.3f}")
    
    # Show statistics
    print("\n2. Cache statistics:")
    stats = cache.get_stats()
    print(f"   Size: {stats['size']}/{stats['max_size']}")
    print(f"   Hit rate: {stats['hit_rate']:.1%}")
    print(f"   Memory usage: {stats['memory_mb']:.2f} MB")


def demo_encoding_cache():
    """Demonstrate encoding caching."""
    print("\n" + "="*60)
    print("ENCODING CACHE DEMO")
    print("="*60)
    
    # Create encoding cache
    cache = EncodingCache(max_size=200, ttl=1800)
    
    print("\n1. Encoding with cache...")
    
    # Sample content
    contents = [
        b"Hello, world!",
        b"ResonaGraph is awesome",
        b"Caching improves performance",
        b"Hello, world!",  # Duplicate
        b"Phase encoding with primes"
    ]
    
    primes = [2, 3, 5, 7]
    depth = 8
    
    # Mock encoding function
    def mock_encode(content: bytes, primes: List[int], depth: int) -> np.ndarray:
        """Mock encoding function."""
        time.sleep(0.01)  # Simulate computation
        return np.random.randn(len(primes) * depth)
    
    total_compute_time = 0
    total_cache_time = 0
    
    for content in contents:
        content_hash = EncodingCache.compute_content_hash(content, primes, depth)
        
        start = time.time()
        phases, was_cached = cache.get_or_compute(content, primes, depth, mock_encode)
        elapsed = time.time() - start
        
        if was_cached:
            total_cache_time += elapsed
            print(f"   CACHED: '{content.decode()}' ({elapsed*1000:.2f}ms)")
        else:
            total_compute_time += elapsed
            print(f"   COMPUTED: '{content.decode()}' ({elapsed*1000:.2f}ms)")
    
    # Show statistics
    print("\n2. Performance comparison:")
    print(f"   Average compute time: {total_compute_time*1000:.2f}ms")
    print(f"   Average cache time: {total_cache_time*1000:.2f}ms")
    if total_compute_time > 0:
        speedup = total_compute_time / total_cache_time if total_cache_time > 0 else float('inf')
        print(f"   Speedup from caching: {speedup:.1f}x")
    
    stats = cache.get_stats()
    print("\n3. Cache statistics:")
    print(f"   Size: {stats['size']}/{stats['max_size']}")
    print(f"   Hit rate: {stats['hit_rate']:.1%}")
    print(f"   Memory usage: {stats['memory_mb']:.2f} MB")


def demo_cache_manager():
    """Demonstrate unified cache management."""
    print("\n" + "="*60)
    print("CACHE MANAGER DEMO")
    print("="*60)
    
    # Create cache manager
    print("\n1. Creating cache manager...")
    manager = CacheManager(
        beacon_max_size=100,
        beacon_ttl=300,
        probe_max_size=50,
        probe_ttl=600,
        encoding_max_size=200,
        encoding_ttl=1800,
        auto_cleanup=True,
        cleanup_interval=60
    )
    
    print("   Cache manager created with auto-cleanup enabled")
    
    # Add data to all caches
    print("\n2. Populating all caches...")
    
    # Add beacons
    for i in range(20):
        manager.beacon_cache.put(
            f"beacon_{i}",
            f"fp_{i}".encode(),
            int(time.time()),
            [2, 3, 5]
        )
    print(f"   Added 20 beacons")
    
    # Add probes
    for i in range(10):
        query_hash = ProbeCache.compute_query_hash(f"query_{i}")
        manager.probe_cache.put(
            query_hash,
            np.random.randn(32),
            0.8 + np.random.random() * 0.15,
            1.0 + np.random.random() * 0.5
        )
    print(f"   Added 10 probes")
    
    # Add encodings
    for i in range(30):
        content_hash = EncodingCache.compute_content_hash(
            f"content_{i}".encode(),
            [2, 3],
            5
        )
        manager.encoding_cache.put(
            content_hash,
            np.random.randn(10),
            [2, 3],
            5
        )
    print(f"   Added 30 encodings")
    
    # Show aggregated statistics
    print("\n3. Aggregated statistics:")
    stats = manager.get_all_stats()
    
    print(f"\n   Overall:")
    print(f"     Total entries: {stats['overall']['total_size']}")
    print(f"     Total memory: {stats['overall']['total_memory_mb']:.2f} MB")
    
    print(f"\n   Beacon Cache:")
    print(f"     Size: {stats['beacon']['size']}/{stats['beacon']['max_size']}")
    print(f"     TTL: {stats['beacon']['ttl']}s")
    
    print(f"\n   Probe Cache:")
    print(f"     Size: {stats['probe']['size']}/{stats['probe']['max_size']}")
    print(f"     Memory: {stats['probe']['memory_mb']:.2f} MB")
    
    print(f"\n   Encoding Cache:")
    print(f"     Size: {stats['encoding']['size']}/{stats['encoding']['max_size']}")
    print(f"     Memory: {stats['encoding']['memory_mb']:.2f} MB")
    
    # Show summary
    print("\n4. Cache summary:")
    print(manager.get_summary())
    
    # Cleanup
    manager.stop_cleanup()


def demo_performance_comparison():
    """Compare performance with and without caching."""
    print("\n" + "="*60)
    print("PERFORMANCE COMPARISON")
    print("="*60)
    
    # Test data
    queries = [f"query_{i % 10}" for i in range(50)]  # 10 unique, repeated 5x each
    
    print("\n1. Testing WITHOUT cache...")
    
    # Without cache
    start = time.time()
    for query in queries:
        # Simulate expensive operation
        _ = np.random.randn(64)
        time.sleep(0.001)  # 1ms per operation
    no_cache_time = time.time() - start
    
    print(f"   Total time: {no_cache_time*1000:.2f}ms")
    print(f"   Average per query: {no_cache_time/len(queries)*1000:.2f}ms")
    
    print("\n2. Testing WITH cache...")
    
    # With cache
    cache = ProbeCache(max_size=20, ttl=300)
    
    start = time.time()
    cache_hits = 0
    cache_misses = 0
    
    for query in queries:
        query_hash = ProbeCache.compute_query_hash(query)
        cached = cache.get(query_hash)
        
        if cached is not None:
            cache_hits += 1
        else:
            cache_misses += 1
            # Simulate expensive operation
            probe_state = np.random.randn(64)
            time.sleep(0.001)  # 1ms per operation
            cache.put(query_hash, probe_state, 0.9, 1.2)
    
    with_cache_time = time.time() - start
    
    print(f"   Total time: {with_cache_time*1000:.2f}ms")
    print(f"   Average per query: {with_cache_time/len(queries)*1000:.2f}ms")
    print(f"   Cache hits: {cache_hits}")
    print(f"   Cache misses: {cache_misses}")
    
    # Calculate improvement
    speedup = no_cache_time / with_cache_time if with_cache_time > 0 else 0
    time_saved = no_cache_time - with_cache_time
    percent_saved = (time_saved / no_cache_time * 100) if no_cache_time > 0 else 0
    
    print("\n3. Performance improvement:")
    print(f"   Speedup: {speedup:.2f}x")
    print(f"   Time saved: {time_saved*1000:.2f}ms ({percent_saved:.1f}%)")
    print(f"   Hit rate: {cache.get_stats()['hit_rate']:.1%}")


def main():
    """Run all cache demos."""
    print("\n" + "="*60)
    print("RESONAGRAPH PHASE 7.3 - CACHE SYSTEM DEMO")
    print("="*60)
    print("\nDemonstrating LRU caching with TTL for:")
    print("- Beacon fingerprints and metadata")
    print("- Probe states from resonance locking")
    print("- Phase encodings")
    
    # Run demos
    demo_beacon_cache()
    demo_probe_cache()
    demo_encoding_cache()
    demo_cache_manager()
    demo_performance_comparison()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nKey Takeaways:")
    print("✓ LRU eviction manages memory efficiently")
    print("✓ TTL expiration prevents stale data")
    print("✓ Thread-safe operations for concurrent access")
    print("✓ Significant performance improvements from caching")
    print("✓ Unified cache manager simplifies monitoring")
    print("✓ Typical hit rates >70% with repeated queries")


if __name__ == '__main__':
    main()