"""
Index structures for ResonaGraph storage.

Provides primary and secondary indexes for efficient queries.
"""

import pickle
from typing import Optional, List, Set, Iterator, Tuple, Any
from abc import ABC, abstractmethod
import logging

from .backend import StorageBackend

logger = logging.getLogger(__name__)


class Index(ABC):
    """Abstract base class for indexes."""
    
    @abstractmethod
    def put(self, key: bytes, value: Any) -> None:
        """Add entry to index."""
        pass
    
    @abstractmethod
    def delete(self, key: bytes) -> None:
        """Remove entry from index."""
        pass
    
    @abstractmethod
    def get(self, key: bytes) -> Optional[Any]:
        """Get value by key."""
        pass
    
    @abstractmethod
    def scan(self, prefix: Optional[bytes] = None) -> Iterator[Tuple[bytes, Any]]:
        """Scan index with optional prefix."""
        pass


class PrimaryIndex(Index):
    """
    Primary index for direct key-value storage.
    
    Uses a key prefix namespace to separate from other data.
    """
    
    def __init__(self, backend: StorageBackend, namespace: bytes = b'primary:'):
        """
        Initialize primary index.
        
        Args:
            backend: Storage backend
            namespace: Key prefix for this index
        """
        self.backend = backend
        self.namespace = namespace
    
    def _make_key(self, key: bytes) -> bytes:
        """Create namespaced key."""
        return self.namespace + key
    
    def put(self, key: bytes, value: Any) -> None:
        """Store value at key."""
        full_key = self._make_key(key)
        serialized = pickle.dumps(value)
        self.backend.put(full_key, serialized)
    
    def delete(self, key: bytes) -> None:
        """Delete key from index."""
        full_key = self._make_key(key)
        self.backend.delete(full_key)
    
    def get(self, key: bytes) -> Optional[Any]:
        """Get value by key."""
        full_key = self._make_key(key)
        data = self.backend.get(full_key)
        
        if data is None:
            return None
        
        return pickle.loads(data)
    
    def exists(self, key: bytes) -> bool:
        """Check if key exists."""
        full_key = self._make_key(key)
        return self.backend.exists(full_key)
    
    def scan(self, prefix: Optional[bytes] = None) -> Iterator[Tuple[bytes, Any]]:
        """Scan index with optional prefix."""
        if prefix is not None:
            scan_prefix = self._make_key(prefix)
        else:
            scan_prefix = self.namespace
        
        for key, value in self.backend.iterator(scan_prefix):
            # Remove namespace prefix
            original_key = key[len(self.namespace):]
            
            # If user specified prefix, only return matching keys
            if prefix is not None and not original_key.startswith(prefix):
                continue
            
            try:
                deserialized = pickle.loads(value)
                yield (original_key, deserialized)
            except Exception as e:
                logger.warning(f"Failed to deserialize value for key {original_key}: {e}")
                continue


class SecondaryIndex(Index):
    """
    Secondary index for lookups by alternate keys.
    
    Stores mapping from secondary key -> primary key.
    Requires separate storage of actual values in primary index.
    """
    
    def __init__(
        self,
        backend: StorageBackend,
        namespace: bytes = b'secondary:',
        name: str = "unnamed"
    ):
        """
        Initialize secondary index.
        
        Args:
            backend: Storage backend
            namespace: Key prefix for this index
            name: Index name for logging
        """
        self.backend = backend
        self.namespace = namespace
        self.name = name
    
    def _make_key(self, secondary_key: bytes) -> bytes:
        """Create namespaced key."""
        return self.namespace + secondary_key
    
    def _make_reverse_key(self, primary_key: bytes) -> bytes:
        """Create reverse lookup key."""
        return self.namespace + b'reverse:' + primary_key
    
    def put(self, secondary_key: bytes, primary_key: bytes) -> None:
        """
        Map secondary key to primary key.
        
        Args:
            secondary_key: Secondary lookup key
            primary_key: Primary key to map to
        """
        # Forward mapping: secondary -> primary
        full_key = self._make_key(secondary_key)
        self.backend.put(full_key, primary_key)
        
        # Reverse mapping: primary -> set of secondaries
        # (for cleanup when primary is deleted)
        reverse_key = self._make_reverse_key(primary_key)
        existing = self.backend.get(reverse_key)
        
        if existing is not None:
            secondary_keys = pickle.loads(existing)
        else:
            secondary_keys = set()
        
        secondary_keys.add(secondary_key)
        self.backend.put(reverse_key, pickle.dumps(secondary_keys))
    
    def delete(self, secondary_key: bytes) -> None:
        """
        Remove secondary key mapping.
        
        Args:
            secondary_key: Secondary key to remove
        """
        # Get primary key first
        full_key = self._make_key(secondary_key)
        primary_key = self.backend.get(full_key)
        
        if primary_key is None:
            return
        
        # Delete forward mapping
        self.backend.delete(full_key)
        
        # Update reverse mapping
        reverse_key = self._make_reverse_key(primary_key)
        existing = self.backend.get(reverse_key)
        
        if existing is not None:
            secondary_keys = pickle.loads(existing)
            secondary_keys.discard(secondary_key)
            
            if secondary_keys:
                self.backend.put(reverse_key, pickle.dumps(secondary_keys))
            else:
                self.backend.delete(reverse_key)
    
    def delete_by_primary(self, primary_key: bytes) -> None:
        """
        Remove all secondary keys mapped to a primary key.
        
        Args:
            primary_key: Primary key
        """
        reverse_key = self._make_reverse_key(primary_key)
        existing = self.backend.get(reverse_key)
        
        if existing is None:
            return
        
        secondary_keys = pickle.loads(existing)
        
        # Delete all forward mappings
        for secondary_key in secondary_keys:
            full_key = self._make_key(secondary_key)
            self.backend.delete(full_key)
        
        # Delete reverse mapping
        self.backend.delete(reverse_key)
    
    def get(self, secondary_key: bytes) -> Optional[bytes]:
        """
        Get primary key by secondary key.
        
        Args:
            secondary_key: Secondary lookup key
            
        Returns:
            Primary key or None
        """
        full_key = self._make_key(secondary_key)
        return self.backend.get(full_key)
    
    def scan(self, prefix: Optional[bytes] = None) -> Iterator[Tuple[bytes, bytes]]:
        """
        Scan secondary index with optional prefix.
        
        Args:
            prefix: Optional prefix for secondary keys
            
        Yields:
            Tuples of (secondary_key, primary_key)
        """
        if prefix is not None:
            scan_prefix = self._make_key(prefix)
        else:
            scan_prefix = self.namespace
        
        for key, value in self.backend.iterator(scan_prefix):
            # Skip reverse mappings
            if b'reverse:' in key:
                continue
            
            # Remove namespace prefix
            original_key = key[len(self.namespace):]
            
            # If user specified prefix, only return matching keys
            if prefix is not None and not original_key.startswith(prefix):
                continue
            
            yield (original_key, value)
    
    def get_secondary_keys(self, primary_key: bytes) -> Set[bytes]:
        """
        Get all secondary keys mapped to a primary key.
        
        Args:
            primary_key: Primary key
            
        Returns:
            Set of secondary keys
        """
        reverse_key = self._make_reverse_key(primary_key)
        existing = self.backend.get(reverse_key)
        
        if existing is None:
            return set()
        
        return pickle.loads(existing)