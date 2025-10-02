"""
Tests for signature management and Ed25519 operations.

Tests signature key generation, rotation, verification, and trust management
as specified in NEXT_STEPS.md 6.2.
"""

import time
import pytest

from resonagraph.security.signatures import SignatureKeyManager, SignatureKeyPair
from cryptography.hazmat.primitives.asymmetric import ed25519


class TestSignatureKeyManager:
    """Test SignatureKeyManager functionality."""
    
    def test_initialization(self):
        """Test key manager initialization."""
        manager = SignatureKeyManager("node1")
        
        assert manager.node_id == "node1"
        assert manager.rotation_interval == 86400 * 30  # 30 days
        assert manager._current_key is None
        assert manager._previous_key is None
    
    def test_generate_key_pair(self):
        """Test Ed25519 key pair generation."""
        manager = SignatureKeyManager("node1")
        key_pair = manager.generate_key_pair()
        
        assert isinstance(key_pair, SignatureKeyPair)
        assert isinstance(key_pair.private_key, ed25519.Ed25519PrivateKey)
        assert isinstance(key_pair.public_key, ed25519.Ed25519PublicKey)
        assert key_pair.key_id.startswith("node1:")
        assert key_pair.expires_at > key_pair.created_at
    
    def test_get_signing_key_auto_generates(self):
        """Test that get_signing_key auto-generates if none exists."""
        manager = SignatureKeyManager("node1")
        
        signing_key = manager.get_signing_key()
        
        assert isinstance(signing_key, ed25519.Ed25519PrivateKey)
        assert manager._current_key is not None
    
    def test_get_current_key_id(self):
        """Test getting current key ID."""
        manager = SignatureKeyManager("node1")
        
        key_id = manager.get_current_key_id()
        
        assert isinstance(key_id, str)
        assert key_id.startswith("node1:")
    
    def test_rotate_key(self):
        """Test key rotation."""
        manager = SignatureKeyManager("node1")
        
        # Get initial key
        key1_id = manager.get_current_key_id()
        
        # Rotate
        time.sleep(0.01)  # Ensure different timestamp
        new_key = manager.rotate_key()
        
        assert new_key.key_id != key1_id
        assert manager.get_current_key_id() == new_key.key_id
        assert manager._previous_key is not None
        assert manager._previous_key.key_id == key1_id
    
    def test_rotated_key_in_trusted_keys(self):
        """Test that rotated keys are added to trusted keys."""
        manager = SignatureKeyManager("node1")
        
        # Generate initial key
        key1_id = manager.get_current_key_id()
        
        # Rotate
        manager.rotate_key()
        key2_id = manager.get_current_key_id()
        
        # Both keys should be trusted
        trusted = manager.get_trusted_keys()
        assert key1_id in trusted
        assert key2_id in trusted
    
    def test_add_trusted_key(self):
        """Test adding trusted keys from other nodes."""
        manager = SignatureKeyManager("node1")
        
        # Generate a key from another "node"
        other_key = ed25519.Ed25519PrivateKey.generate()
        other_public = other_key.public_key()
        
        # Add to trusted keys
        manager.add_trusted_key("node2:123456", other_public)
        
        trusted = manager.get_trusted_keys()
        assert "node2:123456" in trusted
    
    def test_revoke_key(self):
        """Test key revocation."""
        manager = SignatureKeyManager("node1")
        
        key_id = manager.get_current_key_id()
        
        # Key should be valid initially
        assert manager.is_key_valid(key_id)
        
        # Revoke key
        manager.revoke_key(key_id)
        
        # Key should no longer be valid
        assert not manager.is_key_valid(key_id)
        assert key_id not in manager.get_trusted_keys()
    
    def test_verify_signature_with_current_key(self):
        """Test signature verification with current key."""
        manager = SignatureKeyManager("node1")
        
        # Sign a message
        message = b"test message"
        signing_key = manager.get_signing_key()
        signature = signing_key.sign(message)
        
        # Verify with key ID
        key_id = manager.get_current_key_id()
        assert manager.verify_signature(message, signature, key_id=key_id)
    
    def test_verify_signature_with_public_key(self):
        """Test signature verification with explicit public key."""
        manager = SignatureKeyManager("node1")
        
        # Sign a message
        message = b"test message"
        signing_key = manager.get_signing_key()
        signature = signing_key.sign(message)
        public_key = manager._current_key.public_key
        
        # Verify with public key directly
        assert manager.verify_signature(message, signature, public_key=public_key)
    
    def test_verify_signature_fails_wrong_message(self):
        """Test that signature verification fails with wrong message."""
        manager = SignatureKeyManager("node1")
        
        # Sign a message
        message = b"test message"
        signing_key = manager.get_signing_key()
        signature = signing_key.sign(message)
        
        # Verify with different message
        key_id = manager.get_current_key_id()
        assert not manager.verify_signature(b"wrong message", signature, key_id=key_id)
    
    def test_verify_signature_fails_revoked_key(self):
        """Test that signature verification fails for revoked keys."""
        manager = SignatureKeyManager("node1")
        
        # Sign a message
        message = b"test message"
        signing_key = manager.get_signing_key()
        signature = signing_key.sign(message)
        key_id = manager.get_current_key_id()
        
        # Revoke key
        manager.revoke_key(key_id)
        
        # Verification should fail
        assert not manager.verify_signature(message, signature, key_id=key_id)
    
    def test_export_import_public_key(self):
        """Test public key export and import."""
        manager1 = SignatureKeyManager("node1")
        manager2 = SignatureKeyManager("node2")
        
        # Export node1's public key
        key_id = manager1.get_current_key_id()
        pem_data = manager1.export_public_key()
        
        # Import into node2
        manager2.import_public_key(key_id, pem_data)
        
        # Sign with node1, verify with node2
        message = b"test message"
        signing_key = manager1.get_signing_key()
        signature = signing_key.sign(message)
        
        assert manager2.verify_signature(message, signature, key_id=key_id)
    
    def test_auto_rotation_on_expiry(self):
        """Test automatic key rotation when key expires."""
        # Very short rotation interval for testing
        manager = SignatureKeyManager("node1", rotation_interval=0.1)
        
        # Get initial key
        key1_id = manager.get_current_key_id()
        
        # Wait for expiry
        time.sleep(0.15)
        
        # Getting signing key should trigger rotation
        signing_key = manager.get_signing_key()
        key2_id = manager.get_current_key_id()
        
        assert key1_id != key2_id
        assert manager._previous_key is not None
    
    def test_verify_with_previous_key_during_rotation(self):
        """Test that previous key remains valid during rotation."""
        manager = SignatureKeyManager("node1")
        
        # Sign with initial key
        message = b"test message"
        signing_key1 = manager.get_signing_key()
        signature1 = signing_key1.sign(message)
        key1_id = manager.get_current_key_id()
        
        # Rotate key
        time.sleep(0.01)
        manager.rotate_key()
        
        # Sign with new key
        signing_key2 = manager.get_signing_key()
        signature2 = signing_key2.sign(message)
        key2_id = manager.get_current_key_id()
        
        # Both signatures should verify
        assert manager.verify_signature(message, signature1, key_id=key1_id)
        assert manager.verify_signature(message, signature2, key_id=key2_id)
