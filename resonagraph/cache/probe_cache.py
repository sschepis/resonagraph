"""
Probe caching for ResonaGraph.

Implements cache for synthesized probe states to avoid redundant
resonance locking computations for repeated queries.
"""

import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from collections import OrderedDict
import threading
import hashlib
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class CachedProbe:
    """Cached probe entry with state."""
    query_hash: str
    probe_state: np.ndarray
    overlap: float
    entropy: float
    metadata: Dict[str, Any]
    cached_at: float
    access_count: int = 0
    last_accessed: float = 0.0
    
    def __post_init__(self):
        if self.last_accessed == 0.0:
            self.last_accessed = self.cached_at


class ProbeCache:
    """
    Cache for synthesized probe states.
    
    Features:
    - LRU eviction when cache is full
    - TTL-based expiration
    - Query hash-based lookup
    - Thread-safe operations
    - Statistics tracking
    """
    
    DEFAULT_MAX_SIZE = 500
    DEFAULT_TTL = 600  # 10 minutes
    
    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        ttl: float = DEFAULT_TTL
    ):
        """
        Initialize probe cache.
        
        Args:
            max_size: Maximum number of cached probes
            ttl: Time-to-live in seconds
        """
        self.max_size = max_size
        self.ttl = ttl
        
        # LRU cache using OrderedDict
        self._cache: OrderedDict[str, CachedProbe] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'insertions': 0
        }
    
    @staticmethod
    def compute_query_hash(
        query: str,
        primes: Optional[list] = None,
        depth: Optional[int] = None
    ) -> str:
        """
        Compute hash for query parameters.
        
        Args:
            query: Query string
            primes: Optional prime indices
            depth: Optional depth parameter
            
        Returns:
            Hash string
        """
        hasher = hashlib.sha256()
        hasher.update(query.encode('utf-8'))
        
        if primes is not None:
            hasher.update(str(sorted(primes)).encode('utf-8'))
        
        if depth is not None:
            hasher.update(str(depth).encode('utf-8'))
        
        return hasher.hexdigest()
    
    def get(self, query_hash: str) -> Optional[CachedProbe]:
        """
        Get cached probe by query hash.
        
        Args:
            query_hash: Query hash
            
        Returns:
            Cached probe if found and not expired, None otherwise
        """
        with self._lock:
            if query_hash not in self._cache:
                self._stats['misses'] += 1
                return None
            
            probe = self._cache[query_hash]
            
            # Check if expired
            if self._is_expired(probe):
                self._remove(query_hash)
                self._stats['expirations'] += 1
                self._stats['misses'] += 1
                return None
            
            # Update access statistics
            probe.access_count += 1
            probe.last_accessed = time.time()
            
            # Move to end (most recently used)
            self._cache.move_to_end(query_hash)
            
            self._stats['hits'] += 1
            return probe
    
    def put(
        self,
        query_hash: str,
        probe_state: np.ndarray,
        overlap: float,
        entropy: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Cache a probe state.
        
        Args:
            query_hash: Query hash
            probe_state: Probe state vector
            overlap: Resonance overlap
            entropy: Resonance entropy
            metadata: Optional metadata
        """
        with self._lock:
            now = time.time()
            
            # If hash exists, update it
            if query_hash in self._cache:
                probe = self._cache[query_hash]
                probe.probe_state = probe_state.copy()
                probe.overlap = overlap
                probe.entropy = entropy
                probe.metadata = metadata or {}
                probe.cached_at = now
                probe.last_accessed = now
                self._cache.move_to_end(query_hash)
                return
            
            # Create new entry
            probe = CachedProbe(
                query_hash=query_hash,
                probe_state=probe_state.copy(),
                overlap=overlap,
                entropy=entropy,
                metadata=metadata or {},
                cached_at=now,
                last_accessed=now
            )
            
            # Check if cache is full
            if len(self._cache) >= self.max_size:
                self._evict_lru()
            
            self._cache[query_hash] = probe
            self._stats['insertions'] += 1
    
    def invalidate(self, query_hash: str) -> bool:
        """
        Invalidate (remove) cached probe.
        
        Args:
            query_hash: Query hash
            
        Returns:
            True if probe was cached and removed
        """
        with self._lock:
            if query_hash in self._cache:
                self._remove(query_hash)
                return True
            return False
    
    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_hashes = [
                query_hash for query_hash, probe in self._cache.items()
                if self._is_expired(probe)
            ]
            
            for query_hash in expired_hashes:
                self._remove(query_hash)
                self._stats['expirations'] += 1
            
            return len(expired_hashes)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (
                self._stats['hits'] / total_requests
                if total_requests > 0 else 0.0
            )
            
            # Calculate memory usage estimate
            memory_bytes = sum(
                probe.probe_state.nbytes
                for probe in self._cache.values()
            )
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self._stats['evictions'],
                'expirations': self._stats['expirations'],
                'insertions': self._stats['insertions'],
                'ttl': self.ttl,
                'memory_mb': memory_bytes / (1024 * 1024)
            }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        with self._lock:
            self._stats = {
                'hits': 0,
                'misses': 0,
                'evictions': 0,
                'expirations': 0,
                'insertions': 0
            }
    
    def _is_expired(self, probe: CachedProbe) -> bool:
        """Check if probe has expired."""
        return (time.time() - probe.cached_at) > self.ttl
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            # Remove first item (least recently used)
            query_hash, _ = self._cache.popitem(last=False)
            self._stats['evictions'] += 1
            logger.debug(f"Evicted probe: {query_hash[:16]}...")
    
    def _remove(self, query_hash: str) -> None:
        """Remove entry from cache."""
        if query_hash in self._cache:
            del self._cache[query_hash]
    
    def __len__(self) -> int:
        """Get cache size."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, query_hash: str) -> bool:
        """Check if query hash is in cache (doesn't update access stats)."""
        with self._lock:
            if query_hash not in self._cache:
                return False
            return not self._is_expired(self._cache[query_hash])


# Global cache instance
_default_cache: Optional[ProbeCache] = None


def create_probe_cache(
    max_size: int = ProbeCache.DEFAULT_MAX_SIZE,
    ttl: float = ProbeCache.DEFAULT_TTL
) -> ProbeCache:
    """
    Create or get default probe cache.
    
    Args:
        max_size: Maximum cache size
        ttl: Time-to-live in seconds
        
    Returns:
        ProbeCache instance
    """
    global _default_cache
    if _default_cache is None:
        _default_cache = ProbeCache(max_size=max_size, ttl=ttl)
    return _default_cache