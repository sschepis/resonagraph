"""
Beacon caching for ResonaGraph.

Implements LRU cache with TTL for beacon fingerprints and metadata.
Improves performance by avoiding redundant beacon lookups in gossip network.
"""

import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from collections import OrderedDict
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class CachedBeacon:
    """Cached beacon entry with metadata."""
    key: str
    fingerprint: bytes
    epoch: int
    primes: list
    cached_at: float
    access_count: int = 0
    last_accessed: float = 0.0
    
    def __post_init__(self):
        if self.last_accessed == 0.0:
            self.last_accessed = self.cached_at


class BeaconCache:
    """
    LRU cache for beacon fingerprints with TTL expiration.
    
    Features:
    - LRU eviction when cache is full
    - TTL-based expiration for stale entries
    - Thread-safe operations
    - Cache statistics tracking
    """
    
    DEFAULT_MAX_SIZE = 1000
    DEFAULT_TTL = 300  # 5 minutes
    
    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        ttl: float = DEFAULT_TTL
    ):
        """
        Initialize beacon cache.
        
        Args:
            max_size: Maximum number of cached beacons
            ttl: Time-to-live in seconds
        """
        self.max_size = max_size
        self.ttl = ttl
        
        # LRU cache using OrderedDict
        self._cache: OrderedDict[str, CachedBeacon] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'insertions': 0
        }
    
    def get(self, key: str) -> Optional[CachedBeacon]:
        """
        Get cached beacon by key.
        
        Args:
            key: Beacon key
            
        Returns:
            Cached beacon if found and not expired, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            beacon = self._cache[key]
            
            # Check if expired
            if self._is_expired(beacon):
                self._remove(key)
                self._stats['expirations'] += 1
                self._stats['misses'] += 1
                return None
            
            # Update access statistics
            beacon.access_count += 1
            beacon.last_accessed = time.time()
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            self._stats['hits'] += 1
            return beacon
    
    def put(
        self,
        key: str,
        fingerprint: bytes,
        epoch: int,
        primes: list
    ) -> None:
        """
        Cache a beacon.
        
        Args:
            key: Beacon key
            fingerprint: Beacon fingerprint
            epoch: Epoch timestamp
            primes: Prime indices
        """
        with self._lock:
            now = time.time()
            
            # If key exists, update it
            if key in self._cache:
                beacon = self._cache[key]
                beacon.fingerprint = fingerprint
                beacon.epoch = epoch
                beacon.primes = primes
                beacon.cached_at = now
                beacon.last_accessed = now
                self._cache.move_to_end(key)
                return
            
            # Create new entry
            beacon = CachedBeacon(
                key=key,
                fingerprint=fingerprint,
                epoch=epoch,
                primes=primes,
                cached_at=now,
                last_accessed=now
            )
            
            # Check if cache is full
            if len(self._cache) >= self.max_size:
                self._evict_lru()
            
            self._cache[key] = beacon
            self._stats['insertions'] += 1
    
    def invalidate(self, key: str) -> bool:
        """
        Invalidate (remove) cached beacon.
        
        Args:
            key: Beacon key
            
        Returns:
            True if beacon was cached and removed
        """
        with self._lock:
            if key in self._cache:
                self._remove(key)
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
            expired_keys = [
                key for key, beacon in self._cache.items()
                if self._is_expired(beacon)
            ]
            
            for key in expired_keys:
                self._remove(key)
                self._stats['expirations'] += 1
            
            return len(expired_keys)
    
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
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self._stats['evictions'],
                'expirations': self._stats['expirations'],
                'insertions': self._stats['insertions'],
                'ttl': self.ttl
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
    
    def _is_expired(self, beacon: CachedBeacon) -> bool:
        """Check if beacon has expired."""
        return (time.time() - beacon.cached_at) > self.ttl
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            # Remove first item (least recently used)
            key, _ = self._cache.popitem(last=False)
            self._stats['evictions'] += 1
            logger.debug(f"Evicted beacon: {key}")
    
    def _remove(self, key: str) -> None:
        """Remove entry from cache."""
        if key in self._cache:
            del self._cache[key]
    
    def __len__(self) -> int:
        """Get cache size."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key is in cache (doesn't update access stats)."""
        with self._lock:
            if key not in self._cache:
                return False
            return not self._is_expired(self._cache[key])


# Global cache instance
_default_cache: Optional[BeaconCache] = None


def create_beacon_cache(
    max_size: int = BeaconCache.DEFAULT_MAX_SIZE,
    ttl: float = BeaconCache.DEFAULT_TTL
) -> BeaconCache:
    """
    Create or get default beacon cache.
    
    Args:
        max_size: Maximum cache size
        ttl: Time-to-live in seconds
        
    Returns:
        BeaconCache instance
    """
    global _default_cache
    if _default_cache is None:
        _default_cache = BeaconCache(max_size=max_size, ttl=ttl)
    return _default_cache