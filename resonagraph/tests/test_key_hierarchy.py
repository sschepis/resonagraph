"""
Tests for key hierarchy and rotation.

Tests HKDF key derivation, key rotation, and version management
as specified in NEXT_STEPS.md 6.1.
"""

import time
import pytest

from resonagraph.core.phase_key import PhaseKey
from resonagraph.security.key_hierarchy import (
    KeyHierarchy,
    KeyRotationScheduler,
    KeyVersion
)


class TestKeyHierarchy:
    """Test KeyHierarchy functionality."""
    
    def test_initialization_with_root_key(self):
        """Test initialization with provided root key."""
        root_key = PhaseKey.generate()
        hierarchy = KeyHierarchy(root_key)
        
        assert hierarchy.get_root_key() == root_key
    
    def test_initialization_without_root_key(self):
        """Test initialization generates root key if not provided."""
        hierarchy = KeyHierarchy()
        
        root_key = hierarchy.get_root_key()
        assert root_key is not None
        assert len(root_key.get_bytes()) == PhaseKey.KEY_SIZE
    
    def test_derive_key_deterministic(self):
        """Test that key derivation is deterministic."""
        root_key = PhaseKey.generate()
        hierarchy = KeyHierarchy(root_key)
        
        salt = b"test_salt"
        key1 = hierarchy.derive_key("test_context", "test_purpose", 1, salt)
        key2 = hierarchy.derive_key("test_context", "test_purpose", 1, salt)
        
        assert key1 == key2
    
    def test_derive_key_different_contexts(self):
        """Test that different contexts produce different keys."""
        root_key = PhaseKey.generate()
        hierarchy = KeyHierarchy(root_key)
        
        salt = b"test_salt"
        key1 = hierarchy.derive_key("context1", "purpose", 1, salt)
        key2 = hierarchy.derive_key("context2", "purpose", 1, salt)
        
        assert key1 != key2
    
    def test_derive_key_different_purposes(self):
        """Test that different purposes produce different keys."""
        root_key = PhaseKey.generate()
        hierarchy = KeyHierarchy(root_key)
        
        salt = b"test_salt"
        key1 = hierarchy.derive_key("context", "purpose1", 1, salt)
        key2 = hierarchy.derive_key("context", "purpose2", 1, salt)
        
        assert key1 != key2
    
    def test_derive_key_different_versions(self):
        """Test that different versions produce different keys."""
        root_key = PhaseKey.generate()
        hierarchy = KeyHierarchy(root_key)
        
        salt = b"test_salt"
        key1 = hierarchy.derive_key("context", "purpose", 1, salt)
        key2 = hierarchy.derive_key("context", "purpose", 2, salt)
        
        assert key1 != key2
    
    def test_derive_topic_key(self):
        """Test topic key derivation with metadata."""
        hierarchy = KeyHierarchy()
        
        key_version = hierarchy.derive_topic_key("test_topic", version=1)
        
        assert isinstance(key_version, KeyVersion)
        assert isinstance(key_version.key, PhaseKey)
        assert key_version.version == 1
        assert key_version.purpose == "topic:test_topic"
        assert key_version.expires_at > key_version.created_at
    
    def test_derive_topic_key_caching(self):
        """Test that topic keys are cached."""
        hierarchy = KeyHierarchy()
        
        key_version1 = hierarchy.derive_topic_key("test_topic", version=1)
        key_version2 = hierarchy.derive_topic_key("test_topic", version=1)
        
        # Should return the same cached instance
        assert key_version1 is key_version2
    
    def test_derive_topic_key_expiry(self):
        """Test that expired keys are regenerated."""
        hierarchy = KeyHierarchy()
        
        # Create key with very short TTL
        key_version1 = hierarchy.derive_topic_key("test_topic", version=1, ttl_seconds=0.1)
        
        # Wait for expiry
        time.sleep(0.2)
        
        # Should generate new key (different instance)
        key_version2 = hierarchy.derive_topic_key("test_topic", version=1, ttl_seconds=86400)
        
        # Keys should be different instances (different created_at)
        assert key_version1.created_at != key_version2.created_at
    
    def test_derive_role_key(self):
        """Test role-based key derivation."""
        hierarchy = KeyHierarchy()
        
        admin_key = hierarchy.derive_role_key("admin", "resource1", version=1)
        user_key = hierarchy.derive_role_key("user", "resource1", version=1)
        
        assert isinstance(admin_key, PhaseKey)
        assert isinstance(user_key, PhaseKey)
        assert admin_key != user_key
    
    def test_rotate_root_key(self):
        """Test root key rotation."""
        hierarchy = KeyHierarchy()
        
        old_root = hierarchy.get_root_key()
        
        # Derive a topic key
        old_topic_key = hierarchy.derive_topic_key("test_topic", version=1)
        
        # Rotate root key
        new_root = PhaseKey.generate()
        hierarchy.rotate_root_key(new_root)
        
        assert hierarchy.get_root_key() == new_root
        assert hierarchy.get_root_key() != old_root
        
        # Derived keys should be different after rotation
        new_topic_key = hierarchy.derive_topic_key("test_topic", version=1)
        assert new_topic_key.key != old_topic_key.key


class TestKeyRotationScheduler:
    """Test KeyRotationScheduler functionality."""
    
    def test_initialization(self):
        """Test scheduler initialization."""
        hierarchy = KeyHierarchy()
        scheduler = KeyRotationScheduler(hierarchy)
        
        assert scheduler.key_hierarchy is hierarchy
        assert scheduler.rotation_interval == 86400  # 24 hours
        assert scheduler.overlap_period == 3600  # 1 hour
    
    def test_get_current_version_initial(self):
        """Test getting current version for new topic."""
        hierarchy = KeyHierarchy()
        scheduler = KeyRotationScheduler(hierarchy)
        
        version = scheduler.get_current_version("test_topic")
        assert version == 1
    
    def test_get_active_keys_single(self):
        """Test getting active keys when only one version exists."""
        hierarchy = KeyHierarchy()
        scheduler = KeyRotationScheduler(hierarchy, rotation_interval=3600)
        
        current, previous = scheduler.get_active_keys("test_topic")
        
        assert isinstance(current, KeyVersion)
        assert current.version == 1
        assert previous is None  # No previous version
    
    def test_should_rotate_initial(self):
        """Test that new keys don't need immediate rotation."""
        hierarchy = KeyHierarchy()
        scheduler = KeyRotationScheduler(hierarchy, rotation_interval=3600)
        
        # Get a key to initialize
        scheduler.get_active_keys("test_topic")
        
        # Should not need rotation immediately
        assert not scheduler.should_rotate("test_topic")
    
    def test_should_rotate_after_interval(self):
        """Test that keys need rotation after interval."""
        hierarchy = KeyHierarchy()
        # Very short rotation interval for testing
        scheduler = KeyRotationScheduler(hierarchy, rotation_interval=0.1, overlap_period=0.05)
        
        # Get initial key
        scheduler.get_active_keys("test_topic")
        
        # Wait past rotation interval
        time.sleep(0.15)
        
        # Should need rotation now
        assert scheduler.should_rotate("test_topic")
    
    def test_rotate_key(self):
        """Test manual key rotation."""
        hierarchy = KeyHierarchy()
        scheduler = KeyRotationScheduler(hierarchy)
        
        # Get initial version
        initial_version = scheduler.get_current_version("test_topic")
        assert initial_version == 1
        
        # Rotate
        new_key = scheduler.rotate_key("test_topic")
        
        assert new_key.version == 2
        assert scheduler.get_current_version("test_topic") == 2
    
    def test_auto_rotate_if_needed_no_rotation(self):
        """Test auto-rotation when not needed."""
        hierarchy = KeyHierarchy()
        scheduler = KeyRotationScheduler(hierarchy, rotation_interval=3600)
        
        # Get initial key
        scheduler.get_active_keys("test_topic")
        
        # Try auto-rotation (should not rotate)
        result = scheduler.auto_rotate_if_needed("test_topic")
        
        assert result is None
        assert scheduler.get_current_version("test_topic") == 1
    
    def test_auto_rotate_if_needed_with_rotation(self):
        """Test auto-rotation when needed."""
        hierarchy = KeyHierarchy()
        # Very short rotation interval for testing
        scheduler = KeyRotationScheduler(hierarchy, rotation_interval=0.1, overlap_period=0.05)
        
        # Get initial key
        scheduler.get_active_keys("test_topic")
        
        # Wait past rotation interval
        time.sleep(0.15)
        
        # Try auto-rotation (should rotate)
        result = scheduler.auto_rotate_if_needed("test_topic")
        
        assert result is not None
        assert result.version == 2
        assert scheduler.get_current_version("test_topic") == 2
    
    def test_overlap_period(self):
        """Test that both keys are valid during overlap period."""
        hierarchy = KeyHierarchy()
        # Short intervals for testing
        scheduler = KeyRotationScheduler(
            hierarchy,
            rotation_interval=0.2,
            overlap_period=0.1
        )
        
        # Get initial key
        current1, previous1 = scheduler.get_active_keys("test_topic")
        assert current1.version == 1
        assert previous1 is None
        
        # Wait and rotate
        time.sleep(0.25)
        scheduler.rotate_key("test_topic")
        
        # During overlap period, should have both keys
        current2, previous2 = scheduler.get_active_keys("test_topic")
        assert current2.version == 2
        assert previous2 is not None
        assert previous2.version == 1
