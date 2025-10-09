"""
Storage manager for ResonaGraph.

Provides unified interface for persistent storage with indexes.
"""

import os
import logging
from typing import Optional, Dict, Any, List, Iterator, Tuple

from .backend import StorageBackend, create_storage_backend
from .index import PrimaryIndex, SecondaryIndex

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Unified storage manager for ResonaGraph.
    
    Features:
    - Manages storage backend (RocksDB or in-memory)
    - Primary and secondary indexes
    - Batch operations
    - Statistics and monitoring
    """
    
    def __init__(
        self,
        backend: Optional[StorageBackend] = None,
        backend_type: str = 'auto',
        path: Optional[str] = None,
        **backend_kwargs
    ):
        """
        Initialize storage manager.
        
        Args:
            backend: Existing backend (or None to create)
            backend_type: 'rocksdb', 'memory', or 'auto'
            path: Database path for persistent storage
            **backend_kwargs: Additional backend options
        """
        # Create or use provided backend
        if backend is not None:
            self.backend = backend
            self.owns_backend = False
        else:
            self.backend = create_storage_backend(
                backend_type=backend_type,
                path=path,
                **backend_kwargs
            )
            self.owns_backend = True
        
        # Create indexes
        self._primary_indexes: Dict[str, PrimaryIndex] = {}
        self._secondary_indexes: Dict[str, SecondaryIndex] = {}
        
        logger.info(f"Storage manager initialized with {self.backend.__class__.__name__}")
    
    def create_primary_index(self, name: str, namespace: Optional[bytes] = None) -> PrimaryIndex:
        """
        Create a primary index.
        
        Args:
            name: Index name
            namespace: Optional custom namespace
            
        Returns:
            PrimaryIndex instance
        """
        if name in self._primary_indexes:
            raise ValueError(f"Primary index '{name}' already exists")
        
        if namespace is None:
            namespace = f"primary:{name}:".encode()
        
        index = PrimaryIndex(self.backend, namespace=namespace)
        self._primary_indexes[name] = index
        
        logger.info(f"Created primary index: {name}")
        return index
    
    def get_primary_index(self, name: str) -> Optional[PrimaryIndex]:
        """
        Get primary index by name.
        
        Args:
            name: Index name
            
        Returns:
            PrimaryIndex or None
        """
        return self._primary_indexes.get(name)
    
    def create_secondary_index(
        self,
        name: str,
        namespace: Optional[bytes] = None
    ) -> SecondaryIndex:
        """
        Create a secondary index.
        
        Args:
            name: Index name
            namespace: Optional custom namespace
            
        Returns:
            SecondaryIndex instance
        """
        if name in self._secondary_indexes:
            raise ValueError(f"Secondary index '{name}' already exists")
        
        if namespace is None:
            namespace = f"secondary:{name}:".encode()
        
        index = SecondaryIndex(self.backend, namespace=namespace, name=name)
        self._secondary_indexes[name] = index
        
        logger.info(f"Created secondary index: {name}")
        return index
    
    def get_secondary_index(self, name: str) -> Optional[SecondaryIndex]:
        """
        Get secondary index by name.
        
        Args:
            name: Index name
            
        Returns:
            SecondaryIndex or None
        """
        return self._secondary_indexes.get(name)
    
    def batch_write(self):
        """
        Context manager for batch writes.
        
        Returns:
            Batch context
            
        Example:
            with manager.batch_write() as batch:
                batch.put(key1, value1)
                batch.put(key2, value2)
        """
        return self.backend.batch_write()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self.backend.get_stats()
        
        stats['indexes'] = {
            'primary': list(self._primary_indexes.keys()),
            'secondary': list(self._secondary_indexes.keys())
        }
        
        return stats
    
    def close(self) -> None:
        """Close storage manager."""
        if self.owns_backend:
            self.backend.close()
            logger.info("Storage manager closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


# Global storage manager instance
_default_manager: Optional[StorageManager] = None


def get_storage_manager(
    backend_type: str = 'auto',
    path: Optional[str] = None,
    **kwargs
) -> StorageManager:
    """
    Get or create the default storage manager.
    
    Args:
        backend_type: 'rocksdb', 'memory', or 'auto'
        path: Database path
        **kwargs: Additional backend options
        
    Returns:
        StorageManager instance
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = StorageManager(
            backend_type=backend_type,
            path=path,
            **kwargs
        )
    return _default_manager