"""
Storage subsystem for ResonaGraph.

Provides persistent storage with:
- RocksDB backend for high-performance persistence
- Write-Ahead Log (WAL) for durability
- Index structures for efficient queries
- Batch operations
- Backup and restore
- In-memory fallback when RocksDB unavailable
"""

from .backend import (
    StorageBackend,
    InMemoryBackend,
    create_storage_backend,
    ROCKSDB_AVAILABLE,
    ROCKSDB_LIBRARY
)

# Conditionally import RocksDBBackend
if ROCKSDB_AVAILABLE:
    from .backend import RocksDBBackend
    __all_backends__ = ['StorageBackend', 'RocksDBBackend', 'InMemoryBackend', 'create_storage_backend', 'ROCKSDB_AVAILABLE', 'ROCKSDB_LIBRARY']
else:
    __all_backends__ = ['StorageBackend', 'InMemoryBackend', 'create_storage_backend', 'ROCKSDB_AVAILABLE', 'ROCKSDB_LIBRARY']

from .manager import (
    StorageManager,
    get_storage_manager
)

from .index import (
    Index,
    PrimaryIndex,
    SecondaryIndex
)

__all__ = __all_backends__ + [
    # Manager
    'StorageManager',
    'get_storage_manager',
    
    # Indexes
    'Index',
    'PrimaryIndex',
    'SecondaryIndex'
]