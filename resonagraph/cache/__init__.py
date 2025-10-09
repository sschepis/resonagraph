"""
Caching subsystem for ResonaGraph.

Provides LRU caches with TTL for:
- Beacon fingerprints and metadata
- Probe states from resonance locking
- Phase encodings

Features:
- Thread-safe LRU eviction
- TTL-based expiration
- Automatic cleanup
- Statistics tracking
- Unified cache management
"""

from .beacon_cache import (
    BeaconCache,
    CachedBeacon,
    create_beacon_cache
)

from .probe_cache import (
    ProbeCache,
    CachedProbe,
    create_probe_cache
)

from .encoding_cache import (
    EncodingCache,
    CachedEncoding,
    create_encoding_cache
)

from .manager import (
    CacheManager,
    create_cache_manager,
    get_cache_manager
)

__all__ = [
    # Beacon cache
    'BeaconCache',
    'CachedBeacon',
    'create_beacon_cache',
    
    # Probe cache
    'ProbeCache',
    'CachedProbe',
    'create_probe_cache',
    
    # Encoding cache
    'EncodingCache',
    'CachedEncoding',
    'create_encoding_cache',
    
    # Manager
    'CacheManager',
    'create_cache_manager',
    'get_cache_manager'
]