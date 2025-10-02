"""
Tests for beacon structure implementation.

Tests beacon serialization, deserialization, and cryptographic features
according to copilot-instructions.md Section 7 (Testing Strategies).
"""

import pytest
import time
from cryptography.hazmat.primitives.asymmetric import ed25519

from resonagraph.gossip.beacon import (
    Beacon,
    BeaconMetadata,
    TAU_EPOCH,
    MIN_BEACON_SIZE,
    MAX_BEACON_SIZE
)


class TestBeacon:
    """Test beacon structure and operations."""
    
    def test_beacon_initialization(self):
        """Test basic beacon creation."""
        key = "vertex:user_123"
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
        phase_angles = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
        
        beacon = Beacon(key, primes, phase_angles)
        
        assert beacon.key == key
        assert beacon.primes == primes
        assert beacon.phase_angles == phase_angles
        assert beacon.epoch > 0
        assert beacon.phase_fingerprint > 0
    
    def test_epoch_computation(self):
        """Test epoch timestamp computation."""
        epoch = Beacon._compute_epoch()
        current_time = int(time.time())
        expected_epoch = current_time // TAU_EPOCH
        
        assert epoch == expected_epoch
        
        # Epoch should be stable within τ window
        time.sleep(0.1)
        epoch2 = Beacon._compute_epoch()
        assert epoch2 == epoch  # Should be same within small time window
    
    def test_phase_fingerprint_deterministic(self):
        """Test that phase fingerprint is deterministic."""
        key = "vertex:test"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        beacon1 = Beacon(key, primes, phase_angles)
        beacon2 = Beacon(key, primes, phase_angles)
        
        assert beacon1.phase_fingerprint == beacon2.phase_fingerprint
    
    def test_phase_fingerprint_different_phases(self):
        """Test that different phases produce different fingerprints."""
        key = "vertex:test"
        primes = [2, 3, 5, 7]
        
        beacon1 = Beacon(key, primes, [1.0, 2.0, 3.0, 4.0])
        beacon2 = Beacon(key, primes, [1.1, 2.1, 3.1, 4.1])
        
        # Different phases should produce different fingerprints
        # (Though there's a small chance of collision)
        assert beacon1.phase_fingerprint != beacon2.phase_fingerprint
    
    def test_beacon_serialization_size(self):
        """Test that beacon serialization produces correct size."""
        key = "vertex:user_123"
        primes = [2, 3, 5, 7, 11, 13, 17, 19]
        phase_angles = [0.1 * i for i in range(8)]
        
        beacon = Beacon(key, primes, phase_angles)
        serialized = beacon.serialize()
        
        # Should be at least minimum size
        assert len(serialized) >= MIN_BEACON_SIZE
        # Should not exceed maximum size
        assert len(serialized) <= MAX_BEACON_SIZE
        # Default implementation should be exactly header size
        assert len(serialized) == Beacon.HEADER_SIZE
    
    def test_beacon_serialization_deserialization(self):
        """Test beacon round-trip serialization."""
        key = "vertex:user_123"
        primes = [2, 3, 5, 7, 11, 13, 17, 19]
        phase_angles = [0.1 * i for i in range(8)]
        
        beacon1 = Beacon(key, primes, phase_angles)
        serialized = beacon1.serialize()
        beacon2 = Beacon.deserialize(serialized)
        
        # Check that key properties are preserved
        assert beacon2.epoch == beacon1.epoch
        assert beacon2.phase_fingerprint == beacon1.phase_fingerprint
        assert beacon2.signature == beacon1.signature
        assert beacon2.mac == beacon1.mac
    
    def test_beacon_with_ed25519_signature(self):
        """Test beacon with Ed25519 signature."""
        # Generate Ed25519 key pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        key = "vertex:user_123"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        # Create beacon with signature
        beacon = Beacon(key, primes, phase_angles, signing_key=private_key)
        
        # Signature should not be all zeros
        assert beacon.signature != b'\x00' * 64
        
        # Serialize and deserialize
        serialized = beacon.serialize()
        deserialized = Beacon.deserialize(serialized, verify_key=public_key)
        
        # Should succeed without raising exception
        assert deserialized.signature == beacon.signature
    
    def test_beacon_signature_verification_fails_with_wrong_key(self):
        """Test that signature verification fails with wrong public key."""
        # Generate two different key pairs
        private_key1 = ed25519.Ed25519PrivateKey.generate()
        private_key2 = ed25519.Ed25519PrivateKey.generate()
        public_key2 = private_key2.public_key()
        
        key = "vertex:user_123"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        # Create beacon with first key
        beacon = Beacon(key, primes, phase_angles, signing_key=private_key1)
        serialized = beacon.serialize()
        
        # Try to verify with second key (should fail)
        with pytest.raises(ValueError, match="Signature verification failed"):
            Beacon.deserialize(serialized, verify_key=public_key2)
    
    def test_beacon_with_hmac(self):
        """Test beacon with HMAC."""
        mac_key = b'test_mac_key_32_bytes_long_key!!'
        
        key = "vertex:user_123"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        beacon = Beacon(key, primes, phase_angles, mac_key=mac_key)
        
        # MAC should not be all zeros
        assert beacon.mac != b'\x00' * 32
    
    def test_beacon_metadata_conversion(self):
        """Test conversion to metadata."""
        key = "vertex:user_123"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        beacon = Beacon(key, primes, phase_angles)
        metadata = beacon.to_metadata()
        
        assert isinstance(metadata, BeaconMetadata)
        assert metadata.key == key
        assert metadata.primes == primes
        assert metadata.epoch == beacon.epoch
        assert metadata.phase_fingerprint == beacon.phase_fingerprint
        assert metadata.version == Beacon.VERSION
    
    def test_beacon_size_method(self):
        """Test beacon size() method."""
        key = "vertex:user_123"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        beacon = Beacon(key, primes, phase_angles)
        size = beacon.size()
        
        assert size == len(beacon.serialize())
        assert size == Beacon.HEADER_SIZE
    
    def test_beacon_repr(self):
        """Test beacon string representation."""
        key = "vertex:user_123"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        beacon = Beacon(key, primes, phase_angles)
        repr_str = repr(beacon)
        
        assert "Beacon" in repr_str
        assert key in repr_str
        assert str(len(primes)) in repr_str
    
    def test_delta_encode_primes(self):
        """Test prime delta encoding."""
        key = "vertex:test"
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
        phase_angles = [0.1] * 10
        
        beacon = Beacon(key, primes, phase_angles)
        delta_encoded = beacon._delta_encode_primes()
        
        # Should produce 16 bytes (128 bits)
        assert len(delta_encoded) == 16
        
        # Should be deterministic
        beacon2 = Beacon(key, primes, phase_angles)
        delta_encoded2 = beacon2._delta_encode_primes()
        assert delta_encoded == delta_encoded2
    
    def test_deserialization_invalid_version(self):
        """Test that deserialization rejects invalid version."""
        key = "vertex:test"
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        beacon = Beacon(key, primes, phase_angles)
        serialized = beacon.serialize()
        
        # Corrupt the version byte (it's in the high byte of the first 4-byte word)
        corrupted = bytearray(serialized)
        corrupted[3] = 0xFF  # Set the version byte to invalid
        
        with pytest.raises(ValueError, match="Unsupported beacon version"):
            Beacon.deserialize(bytes(corrupted))
    
    def test_deserialization_too_short(self):
        """Test that deserialization rejects too-short data."""
        short_data = b'x' * 50  # Less than HEADER_SIZE
        
        with pytest.raises(ValueError, match="Beacon data too short"):
            Beacon.deserialize(short_data)
    
    def test_multiple_beacons_different_keys(self):
        """Test creating beacons for different keys."""
        primes = [2, 3, 5, 7]
        phase_angles = [1.0, 2.0, 3.0, 4.0]
        
        beacon1 = Beacon("vertex:user_1", primes, phase_angles)
        beacon2 = Beacon("vertex:user_2", primes, phase_angles)
        
        # Different keys should produce different payload hashes
        # but same epoch (if created within same window)
        assert beacon1.epoch == beacon2.epoch
        assert beacon1.key != beacon2.key
