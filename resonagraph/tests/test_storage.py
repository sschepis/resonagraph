"""
Tests for ResonaGraph storage subsystem.

Tests backends, indexes, and storage manager.
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path

from resonagraph.storage import (
    StorageBackend,
    InMemoryBackend,
    create_storage_backend,
    StorageManager,
    PrimaryIndex,
    SecondaryIndex
)

# Check if RocksDB is available
try:
    from resonagraph.storage.backend import RocksDBBackend, ROCKSDB_AVAILABLE
except ImportError:
    ROCKSDB_AVAILABLE = False


class TestInMemoryBackend(unittest.TestCase):
    """Test in-memory storage backend."""
    
    def setUp(self):
        """Set up test backend."""
        self.backend = InMemoryBackend()
    
    def tearDown(self):
        """Clean up backend."""
        self.backend.close()
    
    def test_put_and_get(self):
        """Test basic put and get operations."""
        self.backend.put(b"key1", b"value1")
        self.assertEqual(self.backend.get(b"key1"), b"value1")
    
    def test_get_nonexistent(self):
        """Test get on nonexistent key."""
        self.assertIsNone(self.backend.get(b"missing"))
    
    def test_delete(self):
        """Test delete operation."""
        self.backend.put(b"key1", b"value1")
        self.backend.delete(b"key1")
        self.assertIsNone(self.backend.get(b"key1"))
    
    def test_exists(self):
        """Test exists check."""
        self.assertFalse(self.backend.exists(b"key1"))
        self.backend.put(b"key1", b"value1")
        self.assertTrue(self.backend.exists(b"key1"))
    
    def test_iterator(self):
        """Test iterator without prefix."""
        # Put some keys
        self.backend.put(b"key1", b"value1")
        self.backend.put(b"key2", b"value2")
        self.backend.put(b"key3", b"value3")
        
        # Iterate all
        items = list(self.backend.iterator())
        self.assertEqual(len(items), 3)
        
        # Check sorted order
        keys = [k for k, v in items]
        self.assertEqual(keys, [b"key1", b"key2", b"key3"])
    
    def test_iterator_with_prefix(self):
        """Test iterator with prefix."""
        self.backend.put(b"user:1", b"alice")
        self.backend.put(b"user:2", b"bob")
        self.backend.put(b"post:1", b"hello")
        
        # Iterate with prefix
        users = list(self.backend.iterator(prefix=b"user:"))
        self.assertEqual(len(users), 2)
        
        posts = list(self.backend.iterator(prefix=b"post:"))
        self.assertEqual(len(posts), 1)
    
    def test_batch_write(self):
        """Test batch write operations."""
        with self.backend.batch_write() as batch:
            batch.put(b"key1", b"value1")
            batch.put(b"key2", b"value2")
            batch.delete(b"key3")  # No-op, key doesn't exist
        
        # Check results
        self.assertEqual(self.backend.get(b"key1"), b"value1")
        self.assertEqual(self.backend.get(b"key2"), b"value2")
    
    def test_batch_write_rollback(self):
        """Test batch write rollback on exception."""
        try:
            with self.backend.batch_write() as batch:
                batch.put(b"key1", b"value1")
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Key should not be written
        self.assertIsNone(self.backend.get(b"key1"))
    
    def test_stats(self):
        """Test statistics."""
        self.backend.put(b"key1", b"value1")
        self.backend.put(b"key2", b"value2")
        
        stats = self.backend.get_stats()
        
        self.assertEqual(stats['backend'], 'in-memory')
        self.assertEqual(stats['entries'], 2)
        self.assertGreater(stats['memory_bytes'], 0)
    
    def test_close(self):
        """Test closing backend."""
        self.backend.put(b"key1", b"value1")
        self.backend.close()
        
        # Operations after close should fail
        with self.assertRaises(RuntimeError):
            self.backend.get(b"key1")


@unittest.skipUnless(ROCKSDB_AVAILABLE, "RocksDB not available")
class TestRocksDBBackend(unittest.TestCase):
    """Test RocksDB storage backend."""
    
    def setUp(self):
        """Set up test backend."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.backend = RocksDBBackend(self.db_path)
    
    def tearDown(self):
        """Clean up backend."""
        self.backend.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_put_and_get(self):
        """Test basic put and get operations."""
        self.backend.put(b"key1", b"value1")
        self.assertEqual(self.backend.get(b"key1"), b"value1")
    
    def test_persistence(self):
        """Test data persistence."""
        # Write data
        self.backend.put(b"key1", b"value1")
        self.backend.close()
        
        # Reopen database
        self.backend = RocksDBBackend(self.db_path)
        
        # Data should still be there
        self.assertEqual(self.backend.get(b"key1"), b"value1")
    
    def test_batch_write(self):
        """Test batch write operations."""
        with self.backend.batch_write() as batch:
            batch.put(b"key1", b"value1")
            batch.put(b"key2", b"value2")
        
        self.assertEqual(self.backend.get(b"key1"), b"value1")
        self.assertEqual(self.backend.get(b"key2"), b"value2")
    
    def test_iterator(self):
        """Test iterator."""
        self.backend.put(b"a", b"1")
        self.backend.put(b"b", b"2")
        self.backend.put(b"c", b"3")
        
        items = list(self.backend.iterator())
        self.assertEqual(len(items), 3)
    
    def test_stats(self):
        """Test statistics."""
        self.backend.put(b"key1", b"value1")
        
        stats = self.backend.get_stats()
        
        self.assertEqual(stats['backend'], 'rocksdb')
        self.assertEqual(stats['path'], self.db_path)
        self.assertIn('num_keys', stats)


class TestPrimaryIndex(unittest.TestCase):
    """Test primary index."""
    
    def setUp(self):
        """Set up test index."""
        self.backend = InMemoryBackend()
        self.index = PrimaryIndex(self.backend, namespace=b"test:")
    
    def tearDown(self):
        """Clean up."""
        self.backend.close()
    
    def test_put_and_get(self):
        """Test storing and retrieving values."""
        data = {"name": "Alice", "age": 30}
        self.index.put(b"user:1", data)
        
        retrieved = self.index.get(b"user:1")
        self.assertEqual(retrieved, data)
    
    def test_get_nonexistent(self):
        """Test get on nonexistent key."""
        self.assertIsNone(self.index.get(b"missing"))
    
    def test_delete(self):
        """Test delete operation."""
        self.index.put(b"key1", "value1")
        self.index.delete(b"key1")
        
        self.assertIsNone(self.index.get(b"key1"))
    
    def test_exists(self):
        """Test exists check."""
        self.assertFalse(self.index.exists(b"key1"))
        
        self.index.put(b"key1", "value1")
        self.assertTrue(self.index.exists(b"key1"))
    
    def test_scan(self):
        """Test scanning index."""
        self.index.put(b"user:1", {"name": "Alice"})
        self.index.put(b"user:2", {"name": "Bob"})
        self.index.put(b"post:1", {"title": "Hello"})
        
        # Scan all
        all_items = list(self.index.scan())
        self.assertEqual(len(all_items), 3)
        
        # Scan with prefix
        users = list(self.index.scan(prefix=b"user:"))
        self.assertEqual(len(users), 2)
    
    def test_namespace_isolation(self):
        """Test that namespace isolates data."""
        index1 = PrimaryIndex(self.backend, namespace=b"ns1:")
        index2 = PrimaryIndex(self.backend, namespace=b"ns2:")
        
        index1.put(b"key1", "value1")
        index2.put(b"key1", "value2")
        
        self.assertEqual(index1.get(b"key1"), "value1")
        self.assertEqual(index2.get(b"key1"), "value2")


class TestSecondaryIndex(unittest.TestCase):
    """Test secondary index."""
    
    def setUp(self):
        """Set up test index."""
        self.backend = InMemoryBackend()
        self.index = SecondaryIndex(self.backend, namespace=b"test:")
    
    def tearDown(self):
        """Clean up."""
        self.backend.close()
    
    def test_put_and_get(self):
        """Test mapping secondary to primary key."""
        self.index.put(b"email:alice@example.com", b"user:1")
        
        primary_key = self.index.get(b"email:alice@example.com")
        self.assertEqual(primary_key, b"user:1")
    
    def test_delete(self):
        """Test deleting secondary key."""
        self.index.put(b"email:alice@example.com", b"user:1")
        self.index.delete(b"email:alice@example.com")
        
        self.assertIsNone(self.index.get(b"email:alice@example.com"))
    
    def test_delete_by_primary(self):
        """Test deleting all secondaries for a primary key."""
        # Map multiple secondaries to same primary
        self.index.put(b"email:alice@example.com", b"user:1")
        self.index.put(b"username:alice", b"user:1")
        
        # Delete by primary
        self.index.delete_by_primary(b"user:1")
        
        # All secondaries should be gone
        self.assertIsNone(self.index.get(b"email:alice@example.com"))
        self.assertIsNone(self.index.get(b"username:alice"))
    
    def test_get_secondary_keys(self):
        """Test getting all secondaries for a primary."""
        self.index.put(b"email:alice@example.com", b"user:1")
        self.index.put(b"username:alice", b"user:1")
        
        secondaries = self.index.get_secondary_keys(b"user:1")
        
        self.assertEqual(len(secondaries), 2)
        self.assertIn(b"email:alice@example.com", secondaries)
        self.assertIn(b"username:alice", secondaries)
    
    def test_scan(self):
        """Test scanning secondary index."""
        self.index.put(b"email:alice@example.com", b"user:1")
        self.index.put(b"email:bob@example.com", b"user:2")
        self.index.put(b"username:alice", b"user:1")
        
        # Scan with prefix
        emails = list(self.index.scan(prefix=b"email:"))
        self.assertEqual(len(emails), 2)


class TestStorageManager(unittest.TestCase):
    """Test storage manager."""
    
    def setUp(self):
        """Set up test manager."""
        self.manager = StorageManager(backend_type='memory')
    
    def tearDown(self):
        """Clean up manager."""
        self.manager.close()
    
    def test_create_primary_index(self):
        """Test creating primary index."""
        index = self.manager.create_primary_index("users")
        
        self.assertIsNotNone(index)
        self.assertEqual(self.manager.get_primary_index("users"), index)
    
    def test_create_duplicate_primary_index(self):
        """Test creating duplicate primary index fails."""
        self.manager.create_primary_index("users")
        
        with self.assertRaises(ValueError):
            self.manager.create_primary_index("users")
    
    def test_create_secondary_index(self):
        """Test creating secondary index."""
        index = self.manager.create_secondary_index("emails")
        
        self.assertIsNotNone(index)
        self.assertEqual(self.manager.get_secondary_index("emails"), index)
    
    def test_batch_write(self):
        """Test batch write through manager."""
        index = self.manager.create_primary_index("test")
        
        with self.manager.batch_write() as batch:
            # Use backend directly
            batch.put(b"test:key1", b"value1")
            batch.put(b"test:key2", b"value2")
        
        # Verify through backend
        self.assertIsNotNone(self.manager.backend.get(b"test:key1"))
    
    def test_stats(self):
        """Test statistics."""
        self.manager.create_primary_index("users")
        self.manager.create_secondary_index("emails")
        
        stats = self.manager.get_stats()
        
        self.assertIn('indexes', stats)
        self.assertEqual(len(stats['indexes']['primary']), 1)
        self.assertEqual(len(stats['indexes']['secondary']), 1)
    
    def test_context_manager(self):
        """Test context manager usage."""
        with StorageManager(backend_type='memory') as manager:
            index = manager.create_primary_index("test")
            index.put(b"key1", "value1")
        
        # Manager should be closed after context


@unittest.skipUnless(ROCKSDB_AVAILABLE, "RocksDB not available")
class TestStorageManagerWithRocksDB(unittest.TestCase):
    """Test storage manager with RocksDB."""
    
    def setUp(self):
        """Set up test manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.manager = StorageManager(backend_type='rocksdb', path=self.db_path)
    
    def tearDown(self):
        """Clean up."""
        self.manager.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_persistence(self):
        """Test data persistence."""
        # Create index and store data
        index = self.manager.create_primary_index("users")
        index.put(b"user:1", {"name": "Alice"})
        self.manager.close()
        
        # Reopen with new manager
        self.manager = StorageManager(backend_type='rocksdb', path=self.db_path)
        index = self.manager.create_primary_index("users")
        
        # Data should persist
        data = index.get(b"user:1")
        self.assertEqual(data["name"], "Alice")


class TestCreateStorageBackend(unittest.TestCase):
    """Test storage backend creation."""
    
    def test_create_memory_backend(self):
        """Test creating in-memory backend."""
        backend = create_storage_backend(backend_type='memory')
        
        self.assertIsInstance(backend, InMemoryBackend)
        backend.close()
    
    def test_auto_fallback_to_memory(self):
        """Test auto fallback to memory when RocksDB unavailable."""
        # Without path, should use memory
        backend = create_storage_backend(backend_type='auto')
        
        self.assertIsInstance(backend, InMemoryBackend)
        backend.close()
    
    @unittest.skipUnless(ROCKSDB_AVAILABLE, "RocksDB not available")
    def test_create_rocksdb_backend(self):
        """Test creating RocksDB backend."""
        temp_dir = tempfile.mkdtemp()
        try:
            db_path = os.path.join(temp_dir, "test.db")
            backend = create_storage_backend(backend_type='rocksdb', path=db_path)
            
            self.assertIsInstance(backend, RocksDBBackend)
            backend.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_invalid_backend_type(self):
        """Test invalid backend type raises error."""
        with self.assertRaises(ValueError):
            create_storage_backend(backend_type='invalid')


if __name__ == '__main__':
    unittest.main()