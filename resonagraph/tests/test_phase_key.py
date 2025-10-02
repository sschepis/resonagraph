"""
Tests for phase key management.

According to copilot-instructions.md Section 5:
- Test key derivation (HKDF)
- Test constant-time comparison
"""

import unittest
from resonagraph.core.phase_key import PhaseKey


class TestPhaseKey(unittest.TestCase):
    """Test phase key functionality."""
    
    def test_from_secret(self):
        """Test creating key from secret."""
        secret = b"my-secret-key"
        key = PhaseKey.from_secret(secret)
        
        # Should create valid key
        self.assertEqual(len(key.get_bytes()), 32)
        
        # Should be deterministic
        key2 = PhaseKey.from_secret(secret)
        self.assertEqual(key, key2)
    
    def test_generate(self):
        """Test generating random key."""
        key1 = PhaseKey.generate()
        key2 = PhaseKey.generate()
        
        # Should be different
        self.assertNotEqual(key1, key2)
        
        # Should be correct size
        self.assertEqual(len(key1.get_bytes()), 32)
        self.assertEqual(len(key2.get_bytes()), 32)
    
    def test_key_size_validation(self):
        """Test that key size is validated."""
        # Too short
        with self.assertRaises(ValueError):
            PhaseKey(b"short")
        
        # Too long
        with self.assertRaises(ValueError):
            PhaseKey(b"x" * 64)
        
        # Just right
        key = PhaseKey(b"x" * 32)
        self.assertEqual(len(key.get_bytes()), 32)
    
    def test_derive_topic_key(self):
        """Test topic key derivation via HKDF."""
        root_key = PhaseKey.generate()
        
        # Derive topic keys
        topic1_key = PhaseKey.derive_topic_key(root_key, "topic1")
        topic2_key = PhaseKey.derive_topic_key(root_key, "topic2")
        
        # Should be different from root
        self.assertNotEqual(topic1_key, root_key)
        self.assertNotEqual(topic2_key, root_key)
        
        # Different topics should have different keys
        self.assertNotEqual(topic1_key, topic2_key)
        
        # Should be correct size
        self.assertEqual(len(topic1_key.get_bytes()), 32)
    
    def test_equality(self):
        """Test key equality comparison."""
        secret = b"test-secret"
        key1 = PhaseKey.from_secret(secret)
        key2 = PhaseKey.from_secret(secret)
        key3 = PhaseKey.from_secret(b"different")
        
        # Same secret should be equal
        self.assertEqual(key1, key2)
        
        # Different secret should not be equal
        self.assertNotEqual(key1, key3)
        
        # Not equal to non-PhaseKey
        self.assertNotEqual(key1, "not a key")
    
    def test_repr(self):
        """Test string representation doesn't reveal key."""
        key = PhaseKey.generate()
        repr_str = repr(key)
        
        # Should not contain actual key bytes
        self.assertIn("PhaseKey", repr_str)
        self.assertIn("hidden", repr_str)
        
        # Should not contain hex representation of key
        key_hex = key.get_bytes().hex()
        self.assertNotIn(key_hex, repr_str)
    
    def test_hash(self):
        """Test that keys can be hashed (for use in sets/dicts)."""
        key1 = PhaseKey.generate()
        key2 = PhaseKey.generate()
        
        # Should be hashable
        key_set = {key1, key2}
        self.assertEqual(len(key_set), 2)
        
        # Same key should have same hash
        secret = b"test"
        key3 = PhaseKey.from_secret(secret)
        key4 = PhaseKey.from_secret(secret)
        self.assertEqual(hash(key3), hash(key4))


if __name__ == '__main__':
    unittest.main()
