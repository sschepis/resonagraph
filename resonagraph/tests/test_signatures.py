"""
Test suite for Ed25519 signature management system.

Tests the signature key manager, beacon signer, and signature verification
components according to Phase 6B security specifications.
"""

import pytest
import time
import secrets
from typing import Dict, Any
from unittest.mock import Mock, patch

from resonagraph.security.signatures import (
    SignatureKeyManager, BeaconSigner,
    create_signature_manager
)
from resonagraph.security.audit import AuditLogger
from resonagraph.security.key_hierarchy import KeyHierarchy


class TestSignatureKeyManager:
    """Test the signature key manager."""
    
    @pytest.fixture
    def audit_logger(self):
        """Create a mock audit logger."""
        return Mock(spec=AuditLogger)
    
    @pytest.fixture
    def key_hierarchy(self):
        """Create a mock key hierarchy."""
        mock = Mock(spec=KeyHierarchy)
        mock.derive_role_key.return_value = secrets.token_bytes(32)
        return mock
    
    def test_init(self, audit_logger):
        """Test manager initialization."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        assert manager.audit_logger is audit_logger
        assert manager.node_id == "test_node"
    
    def test_generate_signing_key(self, audit_logger):
        """Test signing key generation."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        key_id = manager.generate_key_pair()
        
        # Verify key was generated
        assert key_id is not None
        assert "test_node" in key_id
        
        # Verify key can be retrieved
        key_info = manager.get_key_info()
        assert key_info is not None
        assert key_info.key_id == key_id
        
        # Verify audit log was called
        audit_logger.log_security_event.assert_called()
    
    def test_import_public_key(self, audit_logger):
        """Test importing public key from another node."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        # Generate a test key to get PEM format
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        
        test_key = ed25519.Ed25519PrivateKey.generate()
        public_key_pem = test_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Import the public key
        manager.import_public_key("remote_node:123", public_key_pem)
        
        # Verify key was imported
        known_keys = manager.list_known_keys()
        assert "remote_node:123" in known_keys
        
        # Verify audit log
        audit_logger.log_security_event.assert_called()
    
    def test_export_public_key(self, audit_logger):
        """Test public key export."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        # Generate a key
        key_id = manager.generate_key_pair()
        
        # Export public key
        public_key_pem = manager.export_public_key()
        assert public_key_pem is not None
        assert "BEGIN PUBLIC KEY" in public_key_pem
    
    def test_rotate_key(self, audit_logger):
        """Test key rotation."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        # Generate initial key
        old_key_id = manager.generate_key_pair()
        old_key_info = manager.get_key_info()
        
        # Sleep briefly to ensure different timestamp
        import time
        time.sleep(1)
        
        # Rotate key
        new_key_id = manager.rotate_key()
        
        # Verify new key was created
        assert new_key_id != old_key_id
        new_key_info = manager.get_key_info()
        assert new_key_info is not None
        assert new_key_info.key_id == new_key_id
        
        # Verify keys are different
        assert old_key_info.public_key_pem != new_key_info.public_key_pem
        
        # Verify audit logging
        assert audit_logger.log_security_event.call_count >= 2
    
    def test_revoke_key(self, audit_logger):
        """Test key revocation."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        # Import a key to revoke
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        
        test_key = ed25519.Ed25519PrivateKey.generate()
        public_key_pem = test_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        key_id = "revokable_key"
        manager.import_public_key(key_id, public_key_pem)
        
        # Revoke key
        manager.revoke_key(key_id)
        
        # Verify key is marked as revoked
        known_keys = manager.list_known_keys()
        assert known_keys[key_id].revoked is True
        
        # Verify audit logging
        audit_logger.log_security_event.assert_called()
    
    def test_cleanup_expired_keys(self, audit_logger):
        """Test cleanup of expired keys."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        # Import keys with different expiry times
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        
        current_time = time.time()
        
        # Import expired key
        test_key = ed25519.Ed25519PrivateKey.generate()
        public_key_pem = test_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        manager.import_public_key("expired_key", public_key_pem, current_time - 3600)
        manager.import_public_key("valid_key", public_key_pem, current_time + 3600)
        
        # Run cleanup
        cleaned_count = manager.cleanup_expired_keys()
        
        # Verify expired key was removed
        assert cleaned_count == 1
        known_keys = manager.list_known_keys()
        assert "expired_key" not in known_keys
        assert "valid_key" in known_keys
    
    def test_performance_metrics(self, audit_logger):
        """Test performance metrics collection."""
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        # Perform some operations
        key_id = manager.generate_key_pair()
        data = b"test data"
        signature = manager.sign_data(data)
        
        # Check stats
        stats = manager.get_stats()
        assert stats["keys_rotated"] >= 1
        assert stats["signatures_created"] >= 1


class TestBeaconSigner:
    """Test the beacon signing component."""
    
    @pytest.fixture
    def signature_manager(self):
        """Create a signature manager for testing."""
        audit_logger = Mock(spec=AuditLogger)
        manager = SignatureKeyManager(node_id="test_node", audit_logger=audit_logger)
        
        # Generate a test key
        key_id = manager.generate_key_pair()
        
        # Import our own public key for verification testing
        public_key_pem = manager.export_public_key()
        manager.import_public_key(key_id, public_key_pem)
        
        return manager
    
    def test_init(self, signature_manager):
        """Test signer initialization."""
        signer = BeaconSigner(signature_manager)
        assert signer.signature_manager is signature_manager
    
    def test_sign_beacon_data(self, signature_manager):
        """Test beacon data signing."""
        signer = BeaconSigner(signature_manager)
        
        # Test data
        beacon_key = "test_beacon"
        primes = [2, 3, 5, 7]
        phase_fingerprint = 0x123456789ABCDEF0
        epoch = time.time()
        
        # Sign the data
        signature, key_id = signer.sign_beacon_data(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch
        )
        
        # Verify signature was created
        assert signature is not None
        assert len(signature) == 64  # Ed25519 signature length
        assert key_id is not None
    
    def test_verify_beacon_signature(self, signature_manager):
        """Test beacon signature verification."""
        signer = BeaconSigner(signature_manager)
        
        # Test data
        beacon_key = "test_beacon"
        primes = [2, 3, 5, 7]
        phase_fingerprint = 0x123456789ABCDEF0
        epoch = time.time()
        
        # Sign the data
        signature, key_id = signer.sign_beacon_data(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch
        )
        
        # Verify the signature
        is_valid = signer.verify_beacon_signature(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch,
            signature=signature,
            signer_key_id=key_id
        )
        
        assert is_valid is True
    
    def test_verify_invalid_signature(self, signature_manager):
        """Test verification of invalid signature."""
        signer = BeaconSigner(signature_manager)
        
        # Test data
        beacon_key = "test_beacon"
        primes = [2, 3, 5, 7]
        phase_fingerprint = 0x123456789ABCDEF0
        epoch = time.time()
        
        # Create invalid signature
        invalid_signature = secrets.token_bytes(64)
        key_id = signature_manager.get_key_info().key_id
        
        # Verify should fail
        is_valid = signer.verify_beacon_signature(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch,
            signature=invalid_signature,
            signer_key_id=key_id
        )
        
        assert is_valid is False
    
    def test_sign_with_additional_data(self, signature_manager):
        """Test signing with additional authenticated data."""
        signer = BeaconSigner(signature_manager)
        
        # Test data
        beacon_key = "test_beacon"
        primes = [2, 3, 5, 7]
        phase_fingerprint = 0x123456789ABCDEF0
        epoch = time.time()
        additional_data = {"node_id": "test_node", "version": "1.0"}
        
        # Sign with additional data
        signature, key_id = signer.sign_beacon_data(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch,
            additional_data=additional_data
        )
        
        # Verify with same additional data
        is_valid = signer.verify_beacon_signature(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch,
            signature=signature,
            signer_key_id=key_id,
            additional_data=additional_data
        )
        
        assert is_valid is True
        
        # Verify should fail with different additional data
        is_valid_wrong = signer.verify_beacon_signature(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch,
            signature=signature,
            signer_key_id=key_id,
            additional_data={"node_id": "different_node"}
        )
        
        assert is_valid_wrong is False
    
    def test_performance_tracking(self, signature_manager):
        """Test performance tracking in signer."""
        signer = BeaconSigner(signature_manager)
        
        # Perform multiple operations
        for i in range(5):
            beacon_key = f"beacon_{i}"
            primes = [2, 3, 5, 7]
            phase_fingerprint = i
            epoch = time.time()
            
            signature, key_id = signer.sign_beacon_data(
                beacon_key=beacon_key,
                primes=primes,
                phase_fingerprint=phase_fingerprint,
                epoch=epoch
            )
            
            signer.verify_beacon_signature(
                beacon_key=beacon_key,
                primes=primes,
                phase_fingerprint=phase_fingerprint,
                epoch=epoch,
                signature=signature,
                signer_key_id=key_id
            )
        
        # Check that metrics were updated
        stats = signature_manager.get_stats()
        assert stats["signatures_created"] >= 5
        assert stats["signatures_verified"] >= 5


class TestFactoryFunction:
    """Test the factory function for creating signature managers."""
    
    def test_create_signature_manager_basic(self):
        """Test basic signature manager creation."""
        audit_logger = Mock(spec=AuditLogger)
        
        manager = create_signature_manager(node_id="test_node", audit_logger=audit_logger)
        
        assert isinstance(manager, SignatureKeyManager)
        assert manager.audit_logger is audit_logger
        assert manager.node_id == "test_node"
    
    def test_create_signature_manager_with_auto_key(self):
        """Test signature manager creation with auto key generation."""
        audit_logger = Mock(spec=AuditLogger)
        
        manager = create_signature_manager(
            node_id="test_node",
            audit_logger=audit_logger,
            auto_generate_key=True
        )
        
        assert isinstance(manager, SignatureKeyManager)
        assert manager.audit_logger is audit_logger
        assert manager.get_key_info() is not None
    
    def test_create_signature_manager_no_auto_key(self):
        """Test signature manager creation without auto key generation."""
        audit_logger = Mock(spec=AuditLogger)
        
        manager = create_signature_manager(
            node_id="test_node",
            audit_logger=audit_logger,
            auto_generate_key=False
        )
        
        assert isinstance(manager, SignatureKeyManager)
        assert manager.get_key_info() is None


class TestSignatureIntegration:
    """Integration tests for the complete signature system."""
    
    def test_end_to_end_signing_workflow(self):
        """Test complete signing workflow."""
        # Create audit logger
        audit_logger = Mock(spec=AuditLogger)
        
        # Create signature manager
        manager = create_signature_manager(node_id="test_node", audit_logger=audit_logger)
        
        # Create signer
        signer = BeaconSigner(manager)
        
        # Sign beacon data
        beacon_key = "integration_test_beacon"
        primes = [2, 3, 5, 7, 11, 13]
        phase_fingerprint = 0xDEADBEEFCAFEBABE
        epoch = time.time()
        
        signature, returned_key_id = signer.sign_beacon_data(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch
        )
        
        # Import our own public key for verification
        public_key_pem = manager.export_public_key()
        manager.import_public_key(returned_key_id, public_key_pem)
        
        # Verify signature
        is_valid = signer.verify_beacon_signature(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch,
            signature=signature,
            signer_key_id=returned_key_id
        )
        
        assert is_valid is True
        
        # Rotate key and verify old signatures still work
        new_key_id = manager.rotate_key()
        
        # Old signature should still verify
        is_still_valid = signer.verify_beacon_signature(
            beacon_key=beacon_key,
            primes=primes,
            phase_fingerprint=phase_fingerprint,
            epoch=epoch,
            signature=signature,
            signer_key_id=returned_key_id
        )
        
        assert is_still_valid is True
    
    def test_concurrent_signing_operations(self):
        """Test concurrent signing operations."""
        import threading
        import concurrent.futures
        
        audit_logger = Mock(spec=AuditLogger)
        manager = create_signature_manager(node_id="test_node", audit_logger=audit_logger)
        signer = BeaconSigner(manager)
        
        # Import our own public key for verification
        public_key_pem = manager.export_public_key()
        key_id = manager.get_key_info().key_id
        manager.import_public_key(key_id, public_key_pem)
        
        def sign_beacon(index):
            """Sign a beacon in a thread."""
            beacon_key = f"concurrent_beacon_{index}"
            primes = [2, 3, 5, 7]
            phase_fingerprint = index
            epoch = time.time()
            
            signature, returned_key_id = signer.sign_beacon_data(
                beacon_key=beacon_key,
                primes=primes,
                phase_fingerprint=phase_fingerprint,
                epoch=epoch
            )
            
            # Verify immediately
            is_valid = signer.verify_beacon_signature(
                beacon_key=beacon_key,
                primes=primes,
                phase_fingerprint=phase_fingerprint,
                epoch=epoch,
                signature=signature,
                signer_key_id=returned_key_id
            )
            
            return is_valid
        
        # Run concurrent signing operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(sign_beacon, i) for i in range(10)]
            results = [future.result() for future in futures]
        
        # All signatures should be valid
        assert all(results)
