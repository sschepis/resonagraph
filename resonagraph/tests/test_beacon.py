"""
Test suite for enhanced beacon with cryptographic security.

Tests the enhanced beacon class with Ed25519 signatures and HMAC-based
integrity protection according to Phase 6B security specifications.
"""

import pytest
import time
import secrets
import struct
from typing import List, Optional
from unittest.mock import Mock, patch

from resonagraph.gossip.beacon import (
    Beacon, BeaconMetadata, SecurityError,
    create_signed_beacon, create_secure_beacon
)
from resonagraph.security.signatures import SignatureKeyManager
from resonagraph.security.integrity import IntegrityManager
from resonagraph.security.audit import AuditLogger


class TestBeaconMetadata:
    """Test beacon metadata structure."""
    
    def test_init_basic(self):
        """Test basic metadata initialization."""
        metadata = BeaconMetadata(
            key="test_beacon",
            primes=[2, 3, 5],
            epoch=1640995200.0,
            phase_fingerprint=0x123456789ABCDEF0
        )
        
        assert metadata.key == "test_beacon"
        assert metadata.primes == [2, 3, 5]
        assert metadata.epoch == 1640995200.0
        assert metadata.phase_fingerprint == 0x123456789ABCDEF0
        assert metadata.signature is None
        assert metadata.signer_key_id is None
        assert metadata.chunk_macs is None
        assert metadata.node_id is None
        assert metadata.ttl == 3
        assert metadata.created_at is not None
    
    def test_init_with_security_fields(self):
        """Test metadata initialization with security fields."""
        signature = secrets.token_bytes(64)
        chunk_macs = [secrets.token_bytes(32) for _ in range(3)]
        
        metadata = BeaconMetadata(
            key="secure_beacon",
            primes=[2, 3, 5, 7],
            epoch=time.time(),
            phase_fingerprint=0xDEADBEEF,
            signature=signature,
            signer_key_id="test_key_001",
            chunk_macs=chunk_macs,
            node_id="test_node"
        )
        
        assert metadata.signature == signature
        assert metadata.signer_key_id == "test_key_001"
        assert metadata.chunk_macs == chunk_macs
        assert metadata.node_id == "test_node"


class TestBasicBeacon:
    """Test basic beacon functionality without security."""
    
    def test_init_basic(self):
        """Test basic beacon initialization."""
        key = "test_beacon"
        primes = [2, 3, 5, 7]
        phase_angles = [1.23, 4.56, 7.89, 2.34]
        
        beacon = Beacon(
            key=key,
            primes=primes,
            phase_angles=phase_angles
        )
        
        assert beacon.key == key
        assert beacon.primes == primes
        assert beacon.phase_angles == phase_angles
        assert beacon.node_id is None
        assert beacon.signature is None
        assert beacon.chunk_macs is None
        assert isinstance(beacon.epoch, float)
        assert isinstance(beacon.phase_fingerprint, int)
    
    def test_phase_fingerprint_computation(self):
        """Test phase fingerprint computation."""
        beacon1 = Beacon(
            key="test",
            primes=[2, 3],
            phase_angles=[1.0, 2.0]
        )
        
        beacon2 = Beacon(
            key="test",
            primes=[2, 3],
            phase_angles=[1.0, 2.0]
        )
        
        beacon3 = Beacon(
            key="test",
            primes=[2, 3],
            phase_angles=[1.1, 2.0]  # Slightly different
        )
        
        # Same angles should produce same fingerprint
        assert beacon1.phase_fingerprint == beacon2.phase_fingerprint
        
        # Different angles should produce different fingerprint
        assert beacon1.phase_fingerprint != beacon3.phase_fingerprint
    
    def test_size_calculation(self):
        """Test beacon size calculation."""
        beacon = Beacon(
            key="test_beacon",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0],
            node_id="test_node"
        )
        
        size = beacon.size()
        
        # Should include base fields plus node_id
        assert size > 0
        assert isinstance(size, int)
    
    def test_string_representation(self):
        """Test beacon string representation."""
        beacon = Beacon(
            key="test_beacon",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0]
        )
        
        repr_str = repr(beacon)
        
        assert "Beacon" in repr_str
        assert "test_beacon" in repr_str
        assert "primes=3" in repr_str


class TestBeaconWithSignatures:
    """Test beacon functionality with Ed25519 signatures."""
    
    @pytest.fixture
    def signature_manager(self):
        """Create a signature manager for testing."""
        audit_logger = Mock(spec=AuditLogger)
        manager = SignatureKeyManager(audit_logger=audit_logger)
        
        # Generate a test key
        key_id = manager.generate_signing_key(metadata={"purpose": "beacon_test"})
        manager.default_key_id = key_id
        
        return manager
    
    def test_beacon_with_signature_manager(self, signature_manager):
        """Test beacon creation with signature manager."""
        beacon = Beacon(
            key="signed_beacon",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0],
            signature_manager=signature_manager,
            node_id="test_node"
        )
        
        # Should have signature
        assert beacon.signature is not None
        assert len(beacon.signature) == 64  # Ed25519 signature length
        assert beacon.signer_key_id is not None
        
        # Size should include signature
        size_with_sig = beacon.size()
        
        # Create beacon without signature for comparison
        beacon_no_sig = Beacon(
            key="unsigned_beacon",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0]
        )
        
        size_without_sig = beacon_no_sig.size()
        assert size_with_sig > size_without_sig
    
    def test_signature_verification(self, signature_manager):
        """Test beacon signature verification."""
        beacon = Beacon(
            key="verification_test",
            primes=[2, 3, 5, 7],
            phase_angles=[1.23, 4.56, 7.89, 2.34],
            signature_manager=signature_manager
        )
        
        # Verify signature
        is_valid = beacon.verify_signature(signature_manager=signature_manager)
        assert is_valid is True
        
        # Test with wrong manager should fail
        wrong_manager = SignatureKeyManager(audit_logger=Mock())
        is_invalid = beacon.verify_signature(signature_manager=wrong_manager)
        assert is_invalid is False
    
    def test_legacy_signature_support(self):
        """Test legacy signature support."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        # Create legacy signing key
        signing_key = ed25519.Ed25519PrivateKey.generate()
        public_key = signing_key.public_key()
        
        beacon = Beacon(
            key="legacy_beacon",
            primes=[2, 3],
            phase_angles=[1.0, 2.0],
            signing_key=signing_key,
            node_id="legacy_node"
        )
        
        # Should have signature
        assert beacon.signature is not None
        assert beacon.signer_key_id.startswith("legacy:")
        
        # Should verify with public key
        is_valid = beacon.verify_signature(public_key=public_key)
        assert is_valid is True


class TestBeaconWithIntegrity:
    """Test beacon functionality with HMAC integrity protection."""
    
    @pytest.fixture
    def integrity_manager(self):
        """Create an integrity manager for testing."""
        mac_key = secrets.token_bytes(32)
        audit_logger = Mock(spec=AuditLogger)
        return IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
    
    def test_beacon_with_integrity_manager(self, integrity_manager):
        """Test beacon creation with integrity manager."""
        beacon = Beacon(
            key="integrity_beacon",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0],
            integrity_manager=integrity_manager,
            node_id="test_node"
        )
        
        # Should have MACs
        assert beacon.chunk_macs is not None
        assert len(beacon.chunk_macs) == 3  # One per phase angle
        assert all(len(mac) == 32 for mac in beacon.chunk_macs)  # SHA256 length
    
    def test_integrity_verification(self, integrity_manager):
        """Test beacon integrity verification."""
        beacon = Beacon(
            key="integrity_verification",
            primes=[2, 3, 5, 7],
            phase_angles=[1.23, 4.56, 7.89, 2.34],
            integrity_manager=integrity_manager,
            node_id="verify_node"
        )
        
        # First verification should succeed
        is_valid = beacon.verify_integrity(integrity_manager=integrity_manager)
        assert is_valid is True
        
        # Second verification should fail (replay protection)
        is_replay = beacon.verify_integrity(integrity_manager=integrity_manager)
        assert is_replay is False
    
    def test_legacy_mac_support(self):
        """Test legacy MAC support."""
        mac_key = secrets.token_bytes(32)
        
        beacon = Beacon(
            key="legacy_mac_beacon",
            primes=[2, 3],
            phase_angles=[1.0, 2.0],
            mac_key=mac_key
        )
        
        # Should have MACs
        assert beacon.chunk_macs is not None
        assert len(beacon.chunk_macs) == 2
        
        # Should verify with same MAC key
        is_valid = beacon.verify_integrity(mac_key=mac_key)
        assert is_valid is True
        
        # Should fail with wrong MAC key
        wrong_key = secrets.token_bytes(32)
        is_invalid = beacon.verify_integrity(mac_key=wrong_key)
        assert is_invalid is False


class TestSecureBeacon:
    """Test beacon with full security (signatures + integrity)."""
    
    @pytest.fixture
    def security_managers(self):
        """Create security managers for testing."""
        audit_logger = Mock(spec=AuditLogger)
        
        signature_manager = SignatureKeyManager(audit_logger=audit_logger)
        key_id = signature_manager.generate_signing_key()
        signature_manager.default_key_id = key_id
        
        mac_key = secrets.token_bytes(32)
        integrity_manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        return signature_manager, integrity_manager
    
    def test_fully_secure_beacon(self, security_managers):
        """Test beacon with both signatures and integrity protection."""
        signature_manager, integrity_manager = security_managers
        
        beacon = Beacon(
            key="fully_secure_beacon",
            primes=[2, 3, 5, 7, 11],
            phase_angles=[1.1, 2.2, 3.3, 4.4, 5.5],
            signature_manager=signature_manager,
            integrity_manager=integrity_manager,
            node_id="secure_node"
        )
        
        # Should have both security features
        assert beacon.signature is not None
        assert beacon.signer_key_id is not None
        assert beacon.chunk_macs is not None
        assert len(beacon.chunk_macs) == 5
        
        # Both should verify
        sig_valid = beacon.verify_signature(signature_manager=signature_manager)
        integrity_valid = beacon.verify_integrity(integrity_manager=integrity_manager)
        
        assert sig_valid is True
        assert integrity_valid is True
        
        # String representation should indicate security
        repr_str = repr(beacon)
        assert "signed" in repr_str
        assert "mac-protected" in repr_str


class TestBeaconSerialization:
    """Test beacon serialization and deserialization."""
    
    @pytest.fixture
    def secure_beacon(self):
        """Create a secure beacon for serialization testing."""
        audit_logger = Mock(spec=AuditLogger)
        
        signature_manager = SignatureKeyManager(audit_logger=audit_logger)
        key_id = signature_manager.generate_signing_key()
        signature_manager.default_key_id = key_id
        
        mac_key = secrets.token_bytes(32)
        integrity_manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        return Beacon(
            key="serialization_test",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0],
            signature_manager=signature_manager,
            integrity_manager=integrity_manager,
            node_id="serial_node"
        ), signature_manager, integrity_manager
    
    def test_serialize_basic_beacon(self):
        """Test serialization of basic beacon."""
        beacon = Beacon(
            key="basic_beacon",
            primes=[2, 3],
            phase_angles=[1.0, 2.0]
        )
        
        serialized = beacon.serialize()
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0
    
    def test_serialize_secure_beacon(self, secure_beacon):
        """Test serialization of secure beacon."""
        beacon, signature_manager, integrity_manager = secure_beacon
        
        serialized = beacon.serialize()
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0
    
    def test_deserialize_basic_beacon(self):
        """Test deserialization of basic beacon."""
        original = Beacon(
            key="deserial_test",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0],
            node_id="deserial_node"
        )
        
        serialized = original.serialize()
        deserialized = Beacon.deserialize(serialized)
        
        assert deserialized.key == original.key
        assert deserialized.primes == original.primes
        assert deserialized.phase_angles == original.phase_angles
        assert deserialized.node_id == original.node_id
        assert deserialized.phase_fingerprint == original.phase_fingerprint
    
    def test_deserialize_secure_beacon(self, secure_beacon):
        """Test deserialization of secure beacon."""
        original, signature_manager, integrity_manager = secure_beacon
        
        serialized = original.serialize()
        
        # Deserialize with security verification
        deserialized = Beacon.deserialize(
            serialized,
            signature_manager=signature_manager,
            integrity_manager=integrity_manager
        )
        
        assert deserialized.key == original.key
        assert deserialized.signature == original.signature
        assert deserialized.chunk_macs == original.chunk_macs
    
    def test_deserialize_with_invalid_signature(self, secure_beacon):
        """Test deserialization with invalid signature."""
        original, signature_manager, integrity_manager = secure_beacon
        
        # Tamper with signature
        original.signature = secrets.token_bytes(64)
        
        serialized = original.serialize()
        
        # Should raise SecurityError
        with pytest.raises(SecurityError):
            Beacon.deserialize(
                serialized,
                signature_manager=signature_manager,
                integrity_manager=integrity_manager
            )
    
    def test_deserialize_malformed_data(self):
        """Test deserialization of malformed data."""
        malformed_data = b"not_a_beacon"
        
        with pytest.raises(ValueError):
            Beacon.deserialize(malformed_data)


class TestFactoryFunctions:
    """Test beacon factory functions."""
    
    @pytest.fixture
    def signature_manager(self):
        """Create a signature manager."""
        audit_logger = Mock(spec=AuditLogger)
        manager = SignatureKeyManager(audit_logger=audit_logger)
        key_id = manager.generate_signing_key()
        manager.default_key_id = key_id
        return manager
    
    @pytest.fixture
    def integrity_manager(self):
        """Create an integrity manager."""
        mac_key = secrets.token_bytes(32)
        audit_logger = Mock(spec=AuditLogger)
        return IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
    
    def test_create_signed_beacon(self, signature_manager):
        """Test signed beacon factory function."""
        beacon = create_signed_beacon(
            key="factory_signed",
            primes=[2, 3, 5],
            phase_angles=[1.0, 2.0, 3.0],
            signature_manager=signature_manager,
            node_id="factory_node"
        )
        
        assert isinstance(beacon, Beacon)
        assert beacon.signature is not None
        assert beacon.signer_key_id is not None
        assert beacon.chunk_macs is None  # No integrity manager
        assert beacon.node_id == "factory_node"
    
    def test_create_secure_beacon(self, signature_manager, integrity_manager):
        """Test secure beacon factory function."""
        beacon = create_secure_beacon(
            key="factory_secure",
            primes=[2, 3, 5, 7],
            phase_angles=[1.0, 2.0, 3.0, 4.0],
            signature_manager=signature_manager,
            integrity_manager=integrity_manager,
            node_id="secure_factory_node"
        )
        
        assert isinstance(beacon, Beacon)
        assert beacon.signature is not None
        assert beacon.signer_key_id is not None
        assert beacon.chunk_macs is not None
        assert len(beacon.chunk_macs) == 4
        assert beacon.node_id == "secure_factory_node"


class TestBeaconIntegration:
    """Integration tests for beacon with ResonaGraph components."""
    
    def test_beacon_with_real_prime_selection(self):
        """Test beacon with actual prime selection logic."""
        # This would integrate with the actual prime selection module
        # For now, use realistic prime values
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
        phase_angles = [i * 0.1 for i in range(len(primes))]
        
        beacon = Beacon(
            key="integration_beacon",
            primes=primes,
            phase_angles=phase_angles
        )
        
        assert len(beacon.primes) == len(beacon.phase_angles)
        assert beacon.phase_fingerprint != 0
    
    def test_beacon_with_performance_constraints(self):
        """Test beacon performance with realistic constraints."""
        import time
        
        # Test beacon creation performance
        start_time = time.time()
        
        for i in range(100):
            beacon = Beacon(
                key=f"perf_beacon_{i}",
                primes=[2, 3, 5, 7],
                phase_angles=[1.0, 2.0, 3.0, 4.0]
            )
        
        creation_time = time.time() - start_time
        
        # Should create 100 beacons in reasonable time (< 1 second)
        assert creation_time < 1.0
        
        # Test with security enabled
        audit_logger = Mock(spec=AuditLogger)
        signature_manager = SignatureKeyManager(audit_logger=audit_logger)
        signature_manager.generate_signing_key()
        
        start_time = time.time()
        
        for i in range(10):  # Fewer iterations for signed beacons
            beacon = Beacon(
                key=f"secure_perf_beacon_{i}",
                primes=[2, 3, 5, 7],
                phase_angles=[1.0, 2.0, 3.0, 4.0],
                signature_manager=signature_manager
            )
        
        secure_creation_time = time.time() - start_time
        
        # Should still be reasonable (< 1 second for 10 signed beacons)
        assert secure_creation_time < 1.0
    
    def test_beacon_size_constraints(self):
        """Test beacon size constraints for network transmission."""
        # Test basic beacon size
        beacon = Beacon(
            key="size_test",
            primes=[2, 3, 5, 7, 11],
            phase_angles=[1.0, 2.0, 3.0, 4.0, 5.0]
        )
        
        basic_size = beacon.size()
        
        # Should be reasonable for network transmission (< 1KB)
        assert basic_size < 1024
        
        # Test with security
        audit_logger = Mock(spec=AuditLogger)
        signature_manager = SignatureKeyManager(audit_logger=audit_logger)
        signature_manager.generate_signing_key()
        
        mac_key = secrets.token_bytes(32)
        integrity_manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        secure_beacon = Beacon(
            key="secure_size_test",
            primes=[2, 3, 5, 7, 11],
            phase_angles=[1.0, 2.0, 3.0, 4.0, 5.0],
            signature_manager=signature_manager,
            integrity_manager=integrity_manager,
            node_id="size_test_node"
        )
        
        secure_size = secure_beacon.size()
        
        # Should still be reasonable even with security (< 2KB)
        assert secure_size < 2048
        assert secure_size > basic_size  # But larger than basic
