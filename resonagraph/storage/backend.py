"""
Storage backends for ResonaGraph.

Provides RocksDB backend for persistent storage with in-memory fallback.
"""

import os
import pickle
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any, Iterator, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Try to import RocksDB - prefer rocksdict, fallback to python-rocksdb
ROCKSDB_AVAILABLE = False
ROCKSDB_LIBRARY = None

try:
    import rocksdict
    ROCKSDB_AVAILABLE = True
    ROCKSDB_LIBRARY = 'rocksdict'
    logger.info("Using rocksdict for RocksDB backend")
except ImportError:
    try:
        import rocksdb
        ROCKSDB_AVAILABLE = True
        ROCKSDB_LIBRARY = 'python-rocksdb'
        logger.info("Using python-rocksdb for RocksDB backend")
    except ImportError:
        logger.warning("RocksDB not available (neither rocksdict nor python-rocksdb), falling back to in-memory storage")


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def get(self, key: bytes) -> Optional[bytes]:
        """Get value for key."""
        pass
    
    @abstractmethod
    def put(self, key: bytes, value: bytes) -> None:
        """Put key-value pair."""
        pass
    
    @abstractmethod
    def delete(self, key: bytes) -> None:
        """Delete key."""
        pass
    
    @abstractmethod
    def exists(self, key: bytes) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    def iterator(self, prefix: Optional[bytes] = None) -> Iterator[Tuple[bytes, bytes]]:
        """Iterate over keys with optional prefix."""
        pass
    
    @abstractmethod
    def batch_write(self) -> 'BatchContext':
        """Context manager for batch writes."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the storage backend."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        pass


class BatchContext(ABC):
    """Abstract context for batch operations."""
    
    @abstractmethod
    def put(self, key: bytes, value: bytes) -> None:
        """Add put operation to batch."""
        pass
    
    @abstractmethod
    def delete(self, key: bytes) -> None:
        """Add delete operation to batch."""
        pass
    
    @abstractmethod
    def __enter__(self):
        """Enter batch context."""
        pass
    
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit batch context."""
        pass


class InMemoryBatch(BatchContext):
    """In-memory batch implementation."""
    
    def __init__(self, backend: 'InMemoryBackend'):
        """
        Initialize batch.
        
        Args:
            backend: Parent backend
        """
        self.backend = backend
        self.operations: List[Tuple[str, bytes, Optional[bytes]]] = []
    
    def put(self, key: bytes, value: bytes) -> None:
        """Add put operation."""
        self.operations.append(('put', key, value))
    
    def delete(self, key: bytes) -> None:
        """Add delete operation."""
        self.operations.append(('delete', key, None))
    
    def __enter__(self):
        """Enter context."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Execute batch on exit."""
        if exc_type is None:
            for op, key, value in self.operations:
                if op == 'put':
                    self.backend.put(key, value)
                elif op == 'delete':
                    self.backend.delete(key)
        return False


class InMemoryBackend(StorageBackend):
    """
    In-memory storage backend.
    
    Fallback when RocksDB is not available.
    """
    
    def __init__(self):
        """Initialize in-memory backend."""
        self._data: Dict[bytes, bytes] = {}
        self._closed = False
    
    def get(self, key: bytes) -> Optional[bytes]:
        """Get value for key."""
        if self._closed:
            raise RuntimeError("Storage backend is closed")
        return self._data.get(key)
    
    def put(self, key: bytes, value: bytes) -> None:
        """Put key-value pair."""
        if self._closed:
            raise RuntimeError("Storage backend is closed")
        self._data[key] = value
    
    def delete(self, key: bytes) -> None:
        """Delete key."""
        if self._closed:
            raise RuntimeError("Storage backend is closed")
        self._data.pop(key, None)
    
    def exists(self, key: bytes) -> bool:
        """Check if key exists."""
        if self._closed:
            raise RuntimeError("Storage backend is closed")
        return key in self._data
    
    def iterator(self, prefix: Optional[bytes] = None) -> Iterator[Tuple[bytes, bytes]]:
        """Iterate over keys with optional prefix."""
        if self._closed:
            raise RuntimeError("Storage backend is closed")
        
        for key, value in sorted(self._data.items()):
            if prefix is None or key.startswith(prefix):
                yield (key, value)
    
    def batch_write(self) -> BatchContext:
        """Context manager for batch writes."""
        return InMemoryBatch(self)
    
    def close(self) -> None:
        """Close backend."""
        self._closed = True
        self._data.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return {
            'backend': 'in-memory',
            'entries': len(self._data),
            'memory_bytes': sum(len(k) + len(v) for k, v in self._data.items())
        }


if ROCKSDB_AVAILABLE:
    if ROCKSDB_LIBRARY == 'rocksdict':
        import rocksdict
        
        class RocksDBBatch(BatchContext):
            """RocksDB batch implementation using rocksdict."""
            
            def __init__(self, db: rocksdict.Rdict):
                """
                Initialize batch.
                
                Args:
                    db: RocksDB database
                """
                self.db = db
                self.batch = rocksdict.WriteBatch()
            
            def put(self, key: bytes, value: bytes) -> None:
                """Add put operation."""
                self.batch.put(key, value)
            
            def delete(self, key: bytes) -> None:
                """Add delete operation."""
                self.batch.delete(key)
            
            def __enter__(self):
                """Enter context."""
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                """Write batch on exit."""
                if exc_type is None:
                    self.db.write(self.batch)
                return False
    
    else:  # python-rocksdb
        import rocksdb
        
        class RocksDBBatch(BatchContext):
            """RocksDB batch implementation using python-rocksdb."""
            
            def __init__(self, db: rocksdb.DB):
                """
                Initialize batch.
                
                Args:
                    db: RocksDB database
                """
                self.db = db
                self.batch = rocksdb.WriteBatch()
            
            def put(self, key: bytes, value: bytes) -> None:
                """Add put operation."""
                self.batch.put(key, value)
            
            def delete(self, key: bytes) -> None:
                """Add delete operation."""
                self.batch.delete(key)
            
            def __enter__(self):
                """Enter context."""
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                """Write batch on exit."""
                if exc_type is None:
                    self.db.write(self.batch)
                return False
    
    
    class RocksDBBackend(StorageBackend):
        """
        RocksDB storage backend.
        
        Features:
        - Persistent storage with LSM tree
        - Write-Ahead Log (WAL) for durability
        - Compression (Snappy, LZ4, ZSTD)
        - Block cache for reads
        - Bloom filters for point lookups
        """
        
        def __init__(
            self,
            path: str,
            create_if_missing: bool = True,
            compression: str = 'snappy',
            block_cache_size: int = 8 * 1024 * 1024,  # 8MB
            write_buffer_size: int = 64 * 1024 * 1024,  # 64MB
            max_open_files: int = 1000
        ):
            """
            Initialize RocksDB backend.
            
            Args:
                path: Database directory path
                create_if_missing: Create DB if it doesn't exist
                compression: Compression type ('none', 'snappy', 'lz4', 'zstd')
                block_cache_size: Block cache size in bytes
                write_buffer_size: Write buffer size in bytes
                max_open_files: Maximum open files
            """
            self.path = path
            
            if ROCKSDB_LIBRARY == 'rocksdict':
                # rocksdict Options
                opts = rocksdict.Options()
                opts.create_if_missing(create_if_missing)
                opts.set_max_open_files(max_open_files)
                opts.set_write_buffer_size(write_buffer_size)
                
                # Set compression - rocksdict uses DBCompressionType
                if compression == 'lz4':
                    opts.set_compression_type(rocksdict.DBCompressionType.lz4())
                elif compression == 'zstd':
                    opts.set_compression_type(rocksdict.DBCompressionType.zstd())
                elif compression == 'snappy':
                    opts.set_compression_type(rocksdict.DBCompressionType.snappy())
                else:  # 'none'
                    opts.set_compression_type(rocksdict.DBCompressionType.none())
                
                # Open database
                self.db = rocksdict.Rdict(path, options=opts)
                
            else:  # python-rocksdb
                # Create options
                opts = rocksdb.Options()
                opts.create_if_missing = create_if_missing
                opts.max_open_files = max_open_files
                opts.write_buffer_size = write_buffer_size
                
                # Set compression
                compression_map = {
                    'none': rocksdb.CompressionType.no_compression,
                    'snappy': rocksdb.CompressionType.snappy_compression,
                    'lz4': rocksdb.CompressionType.lz4_compression,
                    'zstd': rocksdb.CompressionType.zstd_compression
                }
                opts.compression = compression_map.get(compression, rocksdb.CompressionType.snappy_compression)
                
                # Block-based table options
                table_opts = rocksdb.BlockBasedTableFactory(
                    block_cache=rocksdb.LRUCache(block_cache_size),
                    filter_policy=rocksdb.BloomFilterPolicy(10)
                )
                opts.table_factory = table_opts
                
                # Open database
                self.db = rocksdb.DB(path, opts)
            
            self._closed = False
            logger.info(f"Opened RocksDB at {path} using {ROCKSDB_LIBRARY}")
        
        def get(self, key: bytes) -> Optional[bytes]:
            """Get value for key."""
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            return self.db.get(key)
        
        def put(self, key: bytes, value: bytes) -> None:
            """Put key-value pair."""
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            self.db.put(key, value)
        
        def delete(self, key: bytes) -> None:
            """Delete key."""
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            self.db.delete(key)
        
        def exists(self, key: bytes) -> bool:
            """Check if key exists."""
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            return self.db.get(key) is not None
        
        def iterator(self, prefix: Optional[bytes] = None) -> Iterator[Tuple[bytes, bytes]]:
            """Iterate over keys with optional prefix."""
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            
            if ROCKSDB_LIBRARY == 'rocksdict':
                # rocksdict uses items() which returns an iterator
                if prefix is not None:
                    for key, value in self.db.items():
                        if key.startswith(prefix):
                            yield (key, value)
                        elif key > prefix:
                            # Keys are sorted, so we can stop when we pass the prefix
                            break
                else:
                    for key, value in self.db.items():
                        yield (key, value)
            else:
                # python-rocksdb uses iteritems()
                it = self.db.iteritems()
                
                if prefix is not None:
                    it.seek(prefix)
                    
                    for key, value in it:
                        if not key.startswith(prefix):
                            break
                        yield (key, value)
                else:
                    it.seek_to_first()
                    for key, value in it:
                        yield (key, value)
        
        def batch_write(self) -> BatchContext:
            """Context manager for batch writes."""
            return RocksDBBatch(self.db)
        
        def compact_range(self, start: Optional[bytes] = None, end: Optional[bytes] = None) -> None:
            """
            Compact a range of keys.
            
            Args:
                start: Start key (None for beginning)
                end: End key (None for end)
            """
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            
            if ROCKSDB_LIBRARY == 'rocksdict':
                # rocksdict uses compact_range method
                self.db.compact_range(start, end)
            else:
                # python-rocksdb uses compact_range method
                self.db.compact_range(start, end)
        
        def create_snapshot(self):
            """
            Create a snapshot for consistent reads.
            
            Returns:
                Snapshot object (python-rocksdb only)
            
            Note:
                rocksdict doesn't support snapshots in the same way.
                This method returns None for rocksdict.
            """
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            
            if ROCKSDB_LIBRARY == 'python-rocksdb':
                return self.db.snapshot()
            else:
                logger.warning("Snapshots not supported with rocksdict backend")
                return None
        
        def close(self) -> None:
            """Close database."""
            if not self._closed:
                self._closed = True
                if ROCKSDB_LIBRARY == 'rocksdict':
                    self.db.close()
                else:
                    del self.db
                logger.info(f"Closed RocksDB at {self.path}")
        
        def get_stats(self) -> Dict[str, Any]:
            """Get storage statistics."""
            if self._closed:
                raise RuntimeError("Storage backend is closed")
            
            stats = {
                'backend': 'rocksdb',
                'library': ROCKSDB_LIBRARY,
                'path': self.path,
            }
            
            if ROCKSDB_LIBRARY == 'rocksdict':
                # rocksdict doesn't expose RocksDB properties the same way
                # Count keys by iterating (less efficient but works)
                try:
                    num_keys = sum(1 for _ in self.db.keys())
                    stats['num_keys'] = num_keys
                except Exception as e:
                    logger.warning(f"Could not count keys: {e}")
                    stats['num_keys'] = -1
                
                # Try to get basic info
                stats['info'] = 'Limited stats available with rocksdict'
            else:
                # python-rocksdb has get_property method
                try:
                    stats['num_keys'] = int(self.db.get_property(b'rocksdb.estimate-num-keys').decode())
                    stats['total_sst_files_size'] = int(self.db.get_property(b'rocksdb.total-sst-files-size').decode())
                    stats['live_sst_files_size'] = int(self.db.get_property(b'rocksdb.live-sst-files-size').decode())
                except Exception as e:
                    logger.warning(f"Could not get RocksDB properties: {e}")
                    stats['error'] = str(e)
            
            return stats
        
        def __enter__(self):
            """Context manager entry."""
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            """Context manager exit."""
            self.close()
            return False


def create_storage_backend(
    backend_type: str = 'auto',
    path: Optional[str] = None,
    **kwargs
) -> StorageBackend:
    """
    Create a storage backend.
    
    Args:
        backend_type: 'rocksdb', 'memory', or 'auto' (auto-detect)
        path: Database path (required for rocksdb)
        **kwargs: Additional backend-specific options
        
    Returns:
        StorageBackend instance
    """
    if backend_type == 'auto':
        if ROCKSDB_AVAILABLE and path is not None:
            backend_type = 'rocksdb'
        else:
            backend_type = 'memory'
            if path is not None:
                logger.warning(
                    "RocksDB not available, using in-memory storage. "
                    "Install python-rocksdb for persistent storage."
                )
    
    if backend_type == 'rocksdb':
        if not ROCKSDB_AVAILABLE:
            raise ImportError(
                "RocksDB backend requested but python-rocksdb not installed. "
                "Install with: pip install python-rocksdb"
            )
        if path is None:
            raise ValueError("path required for RocksDB backend")
        
        return RocksDBBackend(path, **kwargs)
    
    elif backend_type == 'memory':
        return InMemoryBackend()
    
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")