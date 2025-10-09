"""
Encoding caching for ResonaGraph.

Implements cache for phase encodings to avoid redundant
computation of phase vectors for frequently used data.
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
class CachedEncoding:
    """Cached encoding entry with phase data."""
    content_hash: str
    phases: np.ndarray
    primes: list
    depth: int
    cached_at: float
    access_count: int = 0
    last_accessed: float = 0.0
    
    def __post_init__(self):
        if self.last_accessed == 0.0:
            self.last_accessed = self.cached_at


class EncodingCache:
    """
    Cache for phase encodings.
    
    Features:
    - LRU eviction when cache is full
    - TTL-based expiration
    - Content hash-based lookup
    - Thread-safe operations
    - Statistics tracking
    """
    
    DEFAULT_MAX_SIZE = 2000
    DEFAULT_TTL = 1800  # 30 minutes
    
    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        ttl: float = DEFAULT_TTL
    ):
        """
        Initialize encoding cache.
        
        Args:
            max_size: Maximum number of cached encodings
            ttl: Time-to-live in seconds
        """
        self.max_size = max_size
        self.ttl = ttl
        
        # LRU cache using OrderedDict
        self._cache: OrderedDict[str, CachedEncoding] = OrderedDict()
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
    def compute_content_hash(
        content: bytes,
        primes: list,
        depth: int
    ) -> str:
        """
        Compute hash for encoding parameters.
        
        Args:
            content: Content bytes
            primes: Prime indices
            depth: Encoding depth
            
        Returns:
            Hash string
        """
        hasher = hashlib.sha256()
        hasher.update(content)
        hasher.update(str(sorted(primes)).encode('utf-8'))
        hasher.update(str(depth).encode('utf-8'))
        return hasher.hexdigest()
    
    def get(self, content_hash: str) -> Optional[CachedEncoding]:
        """
        Get cached encoding by content hash.
        
        Args:
            content_hash: Content hash
            
        Returns:
            Cached encoding if found and not expired, None otherwise
        """
        with self._lock:
            if content_hash not in self._cache:
                self._stats['misses'] += 1
                return None
            
            encoding = self._cache[content_hash]
            
            # Check if expired
            if self._is_expired(encoding):
                self._remove(content_hash)
                self._stats['expirations'] += 1
                self._stats['misses'] += 1
                return None
            
            # Update access statistics
            encoding.access_count += 1
            encoding.last_accessed = time.time()
            
            # Move to end (most recently used)
            self._cache.move_to_end(content_hash)
            
            self._stats['hits'] += 1
            return encoding
    
    def put(
        self,
        content_hash: str,
        phases: np.ndarray,
        primes: list,
        depth: int
    ) -> None:
        """
        Cache a phase encoding.
        
        Args:
            content_hash: Content hash
            phases: Phase vector
            primes: Prime indices used
            depth: Encoding depth
        """
        with self._lock:
            now = time.time()
            
            # If hash exists, update it
            if content_hash in self._cache:
                encoding = self._cache[content_hash]
                encoding.phases = phases.copy()
                encoding.primes = list(primes)
                encoding.depth = depth
                encoding.cached_at = now
                encoding.last_accessed = now
                self._cache.move_to_end(content_hash)
                return
            
            # Create new entry
            encoding = CachedEncoding(
                content_hash=content_hash,
                phases=phases.copy(),
                primes=list(primes),
                depth=depth,
                cached_at=now,
                last_accessed=now
            )
            
            # Check if cache is full
            if len(self._cache) >= self.max_size:
                self._evict_lru()
            
            self._cache[content_hash] = encoding
            self._stats['insertions'] += 1
    
    def get_or_compute(
        self,
        content: bytes,
        primes: list,
        depth: int,
        compute_fn: callable
    ) -> Tuple[np.ndarray, bool]:
        """
        Get cached encoding or compute if not found.
        
        Args:
            content: Content bytes
            primes: Prime indices
            depth: Encoding depth
            compute_fn: Function to compute encoding if not cached
            
        Returns:
            Tuple of (phases, was_cached)
        """
        content_hash = self.compute_content_hash(content, primes, depth)
        
        # Try to get from cache
        cached = self.get(content_hash)
        if cached is not None:
            return cached.phases, True
        
        # Compute new encoding
        phases = compute_fn(content, primes, depth)
        
        # Cache the result
        self.put(content_hash, phases, primes, depth)
        
        return phases, False
    
    def invalidate(self, content_hash: str) -> bool:
        """
        Invalidate (remove) cached encoding.
        
        Args:
            content_hash: Content hash
            
        Returns:
            True if encoding was cached and removed
        """
        with self._lock:
            if content_hash in self._cache:
                self._remove(content_hash)
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
                content_hash for content_hash, encoding in self._cache.items()
                if self._is_expired(encoding)
            ]
            
            for content_hash in expired_hashes:
                self._remove(content_hash)
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
                encoding.phases.nbytes
                for encoding in self._cache.values()
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
    
    def _is_expired(self, encoding: CachedEncoding) -> bool:
        """Check if encoding has expired."""
        return (time.time() - encoding.cached_at) > self.ttl
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            # Remove first item (least recently used)
            content_hash, _ = self._cache.popitem(last=False)
            self._stats['evictions'] += 1
            logger.debug(f"Evicted encoding: {content_hash[:16]}...")
    
    def _remove(self, content_hash: str) -> None:
        """Remove entry from cache."""
        if content_hash in self._cache:
            del self._cache[content_hash]
    
    def __len__(self) -> int:
        """Get cache size."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, content_hash: str) -> bool:
        """Check if content hash is in cache (doesn't update access stats)."""
        with self._lock:
            if content_hash not in self._cache:
                return False
            return not self._is_expired(self._cache[content_hash])


# Global cache instance
_default_cache: Optional[EncodingCache] = None


def create_encoding_cache(
    max_size: int = EncodingCache.DEFAULT_MAX_SIZE,
    ttl: float = EncodingCache.DEFAULT_TTL
) -> EncodingCache:
    """
    Create or get default encoding cache.
    
    Args:
        max_size: Maximum cache size
        ttl: Time-to-live in seconds
        
    Returns:
        EncodingCache instance
    """
    global _default_cache
    if _default_cache is None:
        _default_cache = EncodingCache(max_size=max_size, ttl=ttl)
    return _default_cache