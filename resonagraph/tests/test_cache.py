"""
Tests for ResonaGraph caching subsystem.

Tests beacon, probe, and encoding caches along with cache manager.
"""

import unittest
import time
import numpy as np
from threading import Thread

from resonagraph.cache import (
    BeaconCache,
    ProbeCache,
    EncodingCache,
    CacheManager,
    create_cache_manager
)


class TestBeaconCache(unittest.TestCase):
    """Test beacon cache functionality."""
    
    def setUp(self):
        """Set up test cache."""
        self.cache = BeaconCache(max_size=3, ttl=1.0)
    
    def test_put_and_get(self):
        """Test basic put and get operations."""
        # Put beacon
        self.cache.put(
            key="beacon1",
            fingerprint=b"fingerprint1",
            epoch=12345,
            primes=[2, 3, 5]
        )
        
        # Get beacon
        beacon = self.cache.get("beacon1")
        
        self.assertIsNotNone(beacon)
        self.assertEqual(beacon.key, "beacon1")
        self.assertEqual(beacon.fingerprint, b"fingerprint1")
        self.assertEqual(beacon.epoch, 12345)
        self.assertEqual(beacon.primes, [2, 3, 5])
    
    def test_cache_miss(self):
        """Test cache miss."""
        beacon = self.cache.get("nonexistent")
        self.assertIsNone(beacon)
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['misses'], 1)
    
    def test_cache_hit(self):
        """Test cache hit."""
        self.cache.put("beacon1", b"fp1", 123, [2, 3])
        
        beacon = self.cache.get("beacon1")
        self.assertIsNotNone(beacon)
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['hits'], 1)
    
    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        # Fill cache
        self.cache.put("b1", b"fp1", 1, [2])
        self.cache.put("b2", b"fp2", 2, [3])
        self.cache.put("b3", b"fp3", 3, [5])
        
        # Access b1 to make it most recently used
        self.cache.get("b1")
        
        # Add new beacon, should evict b2 (least recently used)
        self.cache.put("b4", b"fp4", 4, [7])
        
        self.assertIsNotNone(self.cache.get("b1"))
        self.assertIsNone(self.cache.get("b2"))
        self.assertIsNotNone(self.cache.get("b3"))
        self.assertIsNotNone(self.cache.get("b4"))
    
    def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        self.cache.put("beacon1", b"fp1", 123, [2, 3])
        
        # Should be available immediately
        self.assertIsNotNone(self.cache.get("beacon1"))
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        self.assertIsNone(self.cache.get("beacon1"))
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['expirations'], 1)
    
    def test_invalidate(self):
        """Test manual invalidation."""
        self.cache.put("beacon1", b"fp1", 123, [2, 3])
        
        # Invalidate
        result = self.cache.invalidate("beacon1")
        self.assertTrue(result)
        
        # Should be gone
        self.assertIsNone(self.cache.get("beacon1"))
    
    def test_clear(self):
        """Test clearing cache."""
        self.cache.put("b1", b"fp1", 1, [2])
        self.cache.put("b2", b"fp2", 2, [3])
        
        self.cache.clear()
        
        self.assertEqual(len(self.cache), 0)
        self.assertIsNone(self.cache.get("b1"))
        self.assertIsNone(self.cache.get("b2"))
    
    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        # Add entries with short TTL
        self.cache.put("b1", b"fp1", 1, [2])
        self.cache.put("b2", b"fp2", 2, [3])
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Cleanup
        expired = self.cache.cleanup_expired()
        self.assertEqual(expired, 2)
        self.assertEqual(len(self.cache), 0)
    
    def test_statistics(self):
        """Test statistics tracking."""
        self.cache.reset_stats()
        
        # Generate activity
        self.cache.put("b1", b"fp1", 1, [2])
        self.cache.get("b1")  # Hit
        self.cache.get("b2")  # Miss
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['insertions'], 1)
        self.assertEqual(stats['hit_rate'], 0.5)
    
    def test_update_existing(self):
        """Test updating existing entry."""
        self.cache.put("b1", b"fp1", 1, [2, 3])
        
        # Update
        self.cache.put("b1", b"fp2", 2, [5, 7])
        
        beacon = self.cache.get("b1")
        self.assertEqual(beacon.fingerprint, b"fp2")
        self.assertEqual(beacon.epoch, 2)
        self.assertEqual(beacon.primes, [5, 7])
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        cache = BeaconCache(max_size=100, ttl=60.0)
        
        def worker(n):
            for i in range(10):
                cache.put(f"b{n}_{i}", f"fp{i}".encode(), i, [i])
                cache.get(f"b{n}_{i}")
        
        threads = [Thread(target=worker, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have 50 entries
        self.assertEqual(len(cache), 50)


class TestProbeCache(unittest.TestCase):
    """Test probe cache functionality."""
    
    def setUp(self):
        """Set up test cache."""
        self.cache = ProbeCache(max_size=3, ttl=1.0)
    
    def test_compute_query_hash(self):
        """Test query hash computation."""
        hash1 = ProbeCache.compute_query_hash("test query", [2, 3, 5], 10)
        hash2 = ProbeCache.compute_query_hash("test query", [2, 3, 5], 10)
        hash3 = ProbeCache.compute_query_hash("different", [2, 3, 5], 10)
        
        # Same inputs should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different inputs should produce different hash
        self.assertNotEqual(hash1, hash3)
    
    def test_put_and_get(self):
        """Test basic put and get operations."""
        query_hash = ProbeCache.compute_query_hash("query", [2, 3], 5)
        probe_state = np.random.randn(10)
        
        self.cache.put(
            query_hash=query_hash,
            probe_state=probe_state,
            overlap=0.85,
            entropy=1.2,
            metadata={'depth': 5}
        )
        
        probe = self.cache.get(query_hash)
        
        self.assertIsNotNone(probe)
        np.testing.assert_array_equal(probe.probe_state, probe_state)
        self.assertEqual(probe.overlap, 0.85)
        self.assertEqual(probe.entropy, 1.2)
        self.assertEqual(probe.metadata['depth'], 5)
    
    def test_lru_eviction(self):
        """Test LRU eviction."""
        h1 = ProbeCache.compute_query_hash("q1")
        h2 = ProbeCache.compute_query_hash("q2")
        h3 = ProbeCache.compute_query_hash("q3")
        h4 = ProbeCache.compute_query_hash("q4")
        
        # Fill cache
        for h in [h1, h2, h3]:
            self.cache.put(h, np.random.randn(5), 0.9, 1.0)
        
        # Access h1 to make it MRU
        self.cache.get(h1)
        
        # Add h4, should evict h2
        self.cache.put(h4, np.random.randn(5), 0.8, 1.1)
        
        self.assertIsNotNone(self.cache.get(h1))
        self.assertIsNone(self.cache.get(h2))
        self.assertIsNotNone(self.cache.get(h3))
        self.assertIsNotNone(self.cache.get(h4))
    
    def test_memory_statistics(self):
        """Test memory usage statistics."""
        # Add some probes
        for i in range(3):
            h = ProbeCache.compute_query_hash(f"q{i}")
            self.cache.put(h, np.random.randn(100), 0.9, 1.0)
        
        stats = self.cache.get_stats()
        
        # Should have memory usage
        self.assertGreater(stats['memory_mb'], 0)


class TestEncodingCache(unittest.TestCase):
    """Test encoding cache functionality."""
    
    def setUp(self):
        """Set up test cache."""
        self.cache = EncodingCache(max_size=3, ttl=1.0)
    
    def test_compute_content_hash(self):
        """Test content hash computation."""
        content = b"test content"
        primes = [2, 3, 5]
        depth = 10
        
        hash1 = EncodingCache.compute_content_hash(content, primes, depth)
        hash2 = EncodingCache.compute_content_hash(content, primes, depth)
        hash3 = EncodingCache.compute_content_hash(b"different", primes, depth)
        
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
    
    def test_put_and_get(self):
        """Test basic put and get operations."""
        content = b"test"
        primes = [2, 3, 5]
        depth = 5
        phases = np.random.randn(10)
        
        content_hash = EncodingCache.compute_content_hash(content, primes, depth)
        
        self.cache.put(content_hash, phases, primes, depth)
        
        encoding = self.cache.get(content_hash)
        
        self.assertIsNotNone(encoding)
        np.testing.assert_array_equal(encoding.phases, phases)
        self.assertEqual(encoding.primes, primes)
        self.assertEqual(encoding.depth, depth)
    
    def test_get_or_compute(self):
        """Test get_or_compute functionality."""
        content = b"test"
        primes = [2, 3]
        depth = 5
        
        # Mock compute function
        compute_calls = [0]
        
        def compute_fn(c, p, d):
            compute_calls[0] += 1
            return np.random.randn(10)
        
        # First call should compute
        phases1, was_cached1 = self.cache.get_or_compute(
            content, primes, depth, compute_fn
        )
        
        self.assertFalse(was_cached1)
        self.assertEqual(compute_calls[0], 1)
        
        # Second call should use cache
        phases2, was_cached2 = self.cache.get_or_compute(
            content, primes, depth, compute_fn
        )
        
        self.assertTrue(was_cached2)
        self.assertEqual(compute_calls[0], 1)  # No additional computation
        np.testing.assert_array_equal(phases1, phases2)


class TestCacheManager(unittest.TestCase):
    """Test cache manager functionality."""
    
    def setUp(self):
        """Set up test manager."""
        self.manager = CacheManager(
            beacon_max_size=10,
            beacon_ttl=1.0,
            probe_max_size=10,
            probe_ttl=1.0,
            encoding_max_size=10,
            encoding_ttl=1.0,
            auto_cleanup=False
        )
    
    def tearDown(self):
        """Clean up manager."""
        self.manager.stop_cleanup()
    
    def test_cache_creation(self):
        """Test that all caches are created."""
        self.assertIsNotNone(self.manager.beacon_cache)
        self.assertIsNotNone(self.manager.probe_cache)
        self.assertIsNotNone(self.manager.encoding_cache)
    
    def test_clear_all(self):
        """Test clearing all caches."""
        # Add data to all caches
        self.manager.beacon_cache.put("b1", b"fp1", 1, [2])
        
        h = ProbeCache.compute_query_hash("q1")
        self.manager.probe_cache.put(h, np.random.randn(5), 0.9, 1.0)
        
        ch = EncodingCache.compute_content_hash(b"test", [2], 5)
        self.manager.encoding_cache.put(ch, np.random.randn(5), [2], 5)
        
        # Clear all
        self.manager.clear_all()
        
        self.assertEqual(len(self.manager.beacon_cache), 0)
        self.assertEqual(len(self.manager.probe_cache), 0)
        self.assertEqual(len(self.manager.encoding_cache), 0)
    
    def test_aggregated_statistics(self):
        """Test aggregated statistics."""
        self.manager.reset_all_stats()
        
        # Generate activity
        self.manager.beacon_cache.put("b1", b"fp1", 1, [2])
        self.manager.beacon_cache.get("b1")  # Hit
        self.manager.beacon_cache.get("b2")  # Miss
        
        h = ProbeCache.compute_query_hash("q1")
        self.manager.probe_cache.put(h, np.random.randn(5), 0.9, 1.0)
        self.manager.probe_cache.get(h)  # Hit
        
        stats = self.manager.get_all_stats()
        
        # Check overall stats
        self.assertEqual(stats['overall']['hits'], 2)
        self.assertEqual(stats['overall']['misses'], 1)
        self.assertAlmostEqual(stats['overall']['hit_rate'], 2/3)
        
        # Check individual stats
        self.assertEqual(stats['beacon']['hits'], 1)
        self.assertEqual(stats['probe']['hits'], 1)
    
    def test_summary(self):
        """Test summary generation."""
        summary = self.manager.get_summary()
        
        self.assertIsInstance(summary, str)
        self.assertIn("Cache Summary", summary)
        self.assertIn("Beacon Cache", summary)
        self.assertIn("Probe Cache", summary)
        self.assertIn("Encoding Cache", summary)
    
    def test_auto_cleanup(self):
        """Test automatic cleanup."""
        manager = CacheManager(
            beacon_max_size=10,
            beacon_ttl=0.5,
            auto_cleanup=True,
            cleanup_interval=0.6
        )
        
        try:
            # Add beacon
            manager.beacon_cache.put("b1", b"fp1", 1, [2])
            
            # Wait for cleanup cycle
            time.sleep(1.2)
            
            # Should be cleaned up
            self.assertEqual(len(manager.beacon_cache), 0)
            
        finally:
            manager.stop_cleanup()
    
    def test_context_manager(self):
        """Test context manager usage."""
        with CacheManager(auto_cleanup=True) as manager:
            manager.beacon_cache.put("b1", b"fp1", 1, [2])
            self.assertEqual(len(manager.beacon_cache), 1)
        
        # Cleanup should be stopped after context exit


class TestCacheIntegration(unittest.TestCase):
    """Integration tests for cache system."""
    
    def test_realistic_workload(self):
        """Test with realistic workload."""
        manager = CacheManager(
            beacon_max_size=100,
            probe_max_size=50,
            encoding_max_size=200,
            auto_cleanup=False
        )
        
        try:
            # Simulate beacon lookups - use 120 unique keys to exceed max_size
            for i in range(150):
                key = f"beacon_{i % 120}"  # Some repetition, but more than max_size
                manager.beacon_cache.put(key, f"fp{i}".encode(), i, [i])
            
            # Simulate probe queries
            for i in range(100):
                query = f"query_{i % 30}"  # More repetition
                h = ProbeCache.compute_query_hash(query)
                manager.probe_cache.put(h, np.random.randn(10), 0.9, 1.0)
            
            # Simulate encoding - use 220 unique keys to exceed max_size of 200
            for i in range(250):
                content = f"content_{i % 220}".encode()
                h = EncodingCache.compute_content_hash(content, [2, 3], 5)
                manager.encoding_cache.put(h, np.random.randn(5), [2, 3], 5)
            
            stats = manager.get_all_stats()
            
            # Verify cache sizes respect max_size
            self.assertLessEqual(stats['beacon']['size'], 100)
            self.assertLessEqual(stats['probe']['size'], 50)
            self.assertLessEqual(stats['encoding']['size'], 200)
            
            # Should have evictions
            self.assertGreater(stats['beacon']['evictions'], 0)
            self.assertGreater(stats['encoding']['evictions'], 0)
            
        finally:
            manager.stop_cleanup()


if __name__ == '__main__':
    unittest.main()