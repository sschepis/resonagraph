"""
Cache manager for ResonaGraph.

Coordinates beacon, probe, and encoding caches with unified
initialization, cleanup, and statistics.
"""

import time
import threading
from typing import Dict, Any, Optional
import logging

from .beacon_cache import BeaconCache, create_beacon_cache
from .probe_cache import ProbeCache, create_probe_cache
from .encoding_cache import EncodingCache, create_encoding_cache

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Unified cache manager for all ResonaGraph caches.
    
    Features:
    - Manages beacon, probe, and encoding caches
    - Automatic cleanup of expired entries
    - Aggregated statistics
    - Thread-safe operations
    """
    
    DEFAULT_CLEANUP_INTERVAL = 300  # 5 minutes
    
    def __init__(
        self,
        beacon_max_size: int = BeaconCache.DEFAULT_MAX_SIZE,
        beacon_ttl: float = BeaconCache.DEFAULT_TTL,
        probe_max_size: int = ProbeCache.DEFAULT_MAX_SIZE,
        probe_ttl: float = ProbeCache.DEFAULT_TTL,
        encoding_max_size: int = EncodingCache.DEFAULT_MAX_SIZE,
        encoding_ttl: float = EncodingCache.DEFAULT_TTL,
        auto_cleanup: bool = True,
        cleanup_interval: float = DEFAULT_CLEANUP_INTERVAL
    ):
        """
        Initialize cache manager.
        
        Args:
            beacon_max_size: Max size for beacon cache
            beacon_ttl: TTL for beacon cache
            probe_max_size: Max size for probe cache
            probe_ttl: TTL for probe cache
            encoding_max_size: Max size for encoding cache
            encoding_ttl: TTL for encoding cache
            auto_cleanup: Enable automatic cleanup
            cleanup_interval: Cleanup interval in seconds
        """
        # Create caches
        self.beacon_cache = BeaconCache(
            max_size=beacon_max_size,
            ttl=beacon_ttl
        )
        
        self.probe_cache = ProbeCache(
            max_size=probe_max_size,
            ttl=probe_ttl
        )
        
        self.encoding_cache = EncodingCache(
            max_size=encoding_max_size,
            ttl=encoding_ttl
        )
        
        # Auto cleanup
        self.auto_cleanup = auto_cleanup
        self.cleanup_interval = cleanup_interval
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_stop_event = threading.Event()
        
        if auto_cleanup:
            self.start_cleanup()
    
    def start_cleanup(self) -> None:
        """Start automatic cleanup thread."""
        if self._cleanup_thread is not None:
            logger.warning("Cleanup thread already running")
            return
        
        self._cleanup_stop_event.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="CacheCleanup"
        )
        self._cleanup_thread.start()
        logger.info("Started cache cleanup thread")
    
    def stop_cleanup(self) -> None:
        """Stop automatic cleanup thread."""
        if self._cleanup_thread is None:
            return
        
        self._cleanup_stop_event.set()
        self._cleanup_thread.join(timeout=5.0)
        self._cleanup_thread = None
        logger.info("Stopped cache cleanup thread")
    
    def _cleanup_loop(self) -> None:
        """Cleanup loop for automatic expiration."""
        while not self._cleanup_stop_event.is_set():
            try:
                # Cleanup all caches
                beacon_expired = self.beacon_cache.cleanup_expired()
                probe_expired = self.probe_cache.cleanup_expired()
                encoding_expired = self.encoding_cache.cleanup_expired()
                
                total_expired = beacon_expired + probe_expired + encoding_expired
                
                if total_expired > 0:
                    logger.debug(
                        f"Cleaned up {total_expired} expired entries "
                        f"(beacon: {beacon_expired}, probe: {probe_expired}, "
                        f"encoding: {encoding_expired})"
                    )
                
                # Wait for next cleanup
                self._cleanup_stop_event.wait(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                # Continue on error
                self._cleanup_stop_event.wait(60.0)
    
    def clear_all(self) -> None:
        """Clear all caches."""
        self.beacon_cache.clear()
        self.probe_cache.clear()
        self.encoding_cache.clear()
        logger.info("Cleared all caches")
    
    def reset_all_stats(self) -> None:
        """Reset statistics for all caches."""
        self.beacon_cache.reset_stats()
        self.probe_cache.reset_stats()
        self.encoding_cache.reset_stats()
        logger.info("Reset all cache statistics")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get aggregated statistics from all caches.
        
        Returns:
            Dictionary with cache statistics
        """
        beacon_stats = self.beacon_cache.get_stats()
        probe_stats = self.probe_cache.get_stats()
        encoding_stats = self.encoding_cache.get_stats()
        
        # Calculate totals
        total_hits = (
            beacon_stats['hits'] +
            probe_stats['hits'] +
            encoding_stats['hits']
        )
        
        total_misses = (
            beacon_stats['misses'] +
            probe_stats['misses'] +
            encoding_stats['misses']
        )
        
        total_requests = total_hits + total_misses
        overall_hit_rate = (
            total_hits / total_requests
            if total_requests > 0 else 0.0
        )
        
        return {
            'overall': {
                'hits': total_hits,
                'misses': total_misses,
                'hit_rate': overall_hit_rate,
                'total_size': (
                    len(self.beacon_cache) +
                    len(self.probe_cache) +
                    len(self.encoding_cache)
                ),
                'total_memory_mb': (
                    probe_stats.get('memory_mb', 0.0) +
                    encoding_stats.get('memory_mb', 0.0)
                )
            },
            'beacon': beacon_stats,
            'probe': probe_stats,
            'encoding': encoding_stats
        }
    
    def get_summary(self) -> str:
        """
        Get human-readable cache summary.
        
        Returns:
            Summary string
        """
        stats = self.get_all_stats()
        overall = stats['overall']
        beacon = stats['beacon']
        probe = stats['probe']
        encoding = stats['encoding']
        
        lines = [
            "Cache Summary:",
            f"  Overall Hit Rate: {overall['hit_rate']:.1%}",
            f"  Total Entries: {overall['total_size']}",
            f"  Total Memory: {overall['total_memory_mb']:.2f} MB",
            "",
            f"Beacon Cache:",
            f"  Size: {beacon['size']}/{beacon['max_size']}",
            f"  Hit Rate: {beacon['hit_rate']:.1%}",
            f"  Hits: {beacon['hits']}, Misses: {beacon['misses']}",
            f"  Evictions: {beacon['evictions']}, Expirations: {beacon['expirations']}",
            "",
            f"Probe Cache:",
            f"  Size: {probe['size']}/{probe['max_size']}",
            f"  Hit Rate: {probe['hit_rate']:.1%}",
            f"  Hits: {probe['hits']}, Misses: {probe['misses']}",
            f"  Memory: {probe['memory_mb']:.2f} MB",
            "",
            f"Encoding Cache:",
            f"  Size: {encoding['size']}/{encoding['max_size']}",
            f"  Hit Rate: {encoding['hit_rate']:.1%}",
            f"  Hits: {encoding['hits']}, Misses: {encoding['misses']}",
            f"  Memory: {encoding['memory_mb']:.2f} MB"
        ]
        
        return "\n".join(lines)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_cleanup()
        return False


# Global cache manager instance
_default_manager: Optional[CacheManager] = None


def create_cache_manager(
    beacon_max_size: int = BeaconCache.DEFAULT_MAX_SIZE,
    beacon_ttl: float = BeaconCache.DEFAULT_TTL,
    probe_max_size: int = ProbeCache.DEFAULT_MAX_SIZE,
    probe_ttl: float = ProbeCache.DEFAULT_TTL,
    encoding_max_size: int = EncodingCache.DEFAULT_MAX_SIZE,
    encoding_ttl: float = EncodingCache.DEFAULT_TTL,
    auto_cleanup: bool = True
) -> CacheManager:
    """
    Create or get default cache manager.
    
    Args:
        beacon_max_size: Max size for beacon cache
        beacon_ttl: TTL for beacon cache
        probe_max_size: Max size for probe cache
        probe_ttl: TTL for probe cache
        encoding_max_size: Max size for encoding cache
        encoding_ttl: TTL for encoding cache
        auto_cleanup: Enable automatic cleanup
        
    Returns:
        CacheManager instance
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = CacheManager(
            beacon_max_size=beacon_max_size,
            beacon_ttl=beacon_ttl,
            probe_max_size=probe_max_size,
            probe_ttl=probe_ttl,
            encoding_max_size=encoding_max_size,
            encoding_ttl=encoding_ttl,
            auto_cleanup=auto_cleanup
        )
    return _default_manager


def get_cache_manager() -> Optional[CacheManager]:
    """Get the default cache manager if it exists."""
    return _default_manager