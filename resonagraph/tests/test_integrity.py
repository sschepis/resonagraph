"""
Tests for integrity verification, MACs, and replay detection.

Tests phase MACs, replay detection, and combined integrity verification
as specified in NEXT_STEPS.md 6.2.
"""

import time
import pytest

from resonagraph.security.integrity import PhaseMAC, ReplayDetector, IntegrityVerifier
from resonagraph.security.signatures import SignatureKeyManager


class TestPhaseMAC:
    """Test PhaseMAC functionality."""
    
    def test_compute_chunk_mac(self):
        """Test HMAC computation for phase chunks."""
        chunk_data = b"test phase data"
        chunk_index = 0
        prime = 7
        key = b"test_key_32_bytes_long_000000"
        
        mac = PhaseMAC.compute_chunk_mac(chunk_data, chunk_index, prime, key)
        
        assert isinstance(mac, bytes)
        assert len(mac) == 32  # SHA256 produces 32 bytes
    
    def test_compute_chunk_mac_deterministic(self):
        """Test that MAC computation is deterministic."""
        chunk_data = b"test phase data"
        chunk_index = 0
        prime = 7
        key = b"test_key_32_bytes_long_000000"
        
        mac1 = PhaseMAC.compute_chunk_mac(chunk_data, chunk_index, prime, key)
        mac2 = PhaseMAC.compute_chunk_mac(chunk_data, chunk_index, prime, key)
        
        assert mac1 == mac2
    
    def test_compute_chunk_mac_different_inputs(self):
        """Test that different inputs produce different MACs."""
        key = b"test_key_32_bytes_long_000000"
        
        mac1 = PhaseMAC.compute_chunk_mac(b"data1", 0, 7, key)
        mac2 = PhaseMAC.compute_chunk_mac(b"data2", 0, 7, key)
        mac3 = PhaseMAC.compute_chunk_mac(b"data1", 1, 7, key)
        mac4 = PhaseMAC.compute_chunk_mac(b"data1", 0, 11, key)
        
        assert mac1 != mac2  # Different data
        assert mac1 != mac3  # Different index
        assert mac1 != mac4  # Different prime
    
    def test_verify_chunk_mac_valid(self):
        """Test MAC verification with valid MAC."""
        chunk_data = b"test phase data"
        chunk_index = 0
        prime = 7
        key = b"test_key_32_bytes_long_000000"
        
        mac = PhaseMAC.compute_chunk_mac(chunk_data, chunk_index, prime, key)
        
        assert PhaseMAC.verify_chunk_mac(chunk_data, chunk_index, prime, mac, key)
    
    def test_verify_chunk_mac_invalid(self):
        """Test MAC verification with invalid MAC."""
        chunk_data = b"test phase data"
        chunk_index = 0
        prime = 7
        key = b"test_key_32_bytes_long_000000"
        
        # Wrong MAC
        wrong_mac = b'\x00' * 32
        
        assert not PhaseMAC.verify_chunk_mac(chunk_data, chunk_index, prime, wrong_mac, key)
    
    def test_batch_verify_macs_all_valid(self):
        """Test batch MAC verification with all valid MACs."""
        key = b"test_key_32_bytes_long_000000"
        
        chunks = [
            (b"data1", 0, 7, PhaseMAC.compute_chunk_mac(b"data1", 0, 7, key)),
            (b"data2", 1, 11, PhaseMAC.compute_chunk_mac(b"data2", 1, 11, key)),
            (b"data3", 2, 13, PhaseMAC.compute_chunk_mac(b"data3", 2, 13, key)),
        ]
        
        assert PhaseMAC.batch_verify_macs(chunks, key)
    
    def test_batch_verify_macs_one_invalid(self):
        """Test batch MAC verification with one invalid MAC."""
        key = b"test_key_32_bytes_long_000000"
        
        chunks = [
            (b"data1", 0, 7, PhaseMAC.compute_chunk_mac(b"data1", 0, 7, key)),
            (b"data2", 1, 11, b'\x00' * 32),  # Invalid MAC
            (b"data3", 2, 13, PhaseMAC.compute_chunk_mac(b"data3", 2, 13, key)),
        ]
        
        assert not PhaseMAC.batch_verify_macs(chunks, key)


class TestReplayDetector:
    """Test ReplayDetector functionality."""
    
    def test_initialization(self):
        """Test replay detector initialization."""
        detector = ReplayDetector(epoch_window=10)
        
        assert detector.epoch_window == 10
        assert len(detector._processed_epochs) == 0
    
    def test_check_epoch_valid(self):
        """Test epoch validation with valid epoch."""
        detector = ReplayDetector(epoch_window=10)
        
        current_epoch = 100
        assert detector.check_epoch("key1", 95, current_epoch)  # Within window
        assert detector.check_epoch("key1", 100, current_epoch)  # Current
        assert detector.check_epoch("key1", 101, current_epoch)  # +1 for clock skew
    
    def test_check_epoch_too_old(self):
        """Test epoch validation rejects old epochs."""
        detector = ReplayDetector(epoch_window=10)
        
        current_epoch = 100
        assert not detector.check_epoch("key1", 89, current_epoch)  # Too old
    
    def test_check_epoch_too_future(self):
        """Test epoch validation rejects far future epochs."""
        detector = ReplayDetector(epoch_window=10)
        
        current_epoch = 100
        assert not detector.check_epoch("key1", 102, current_epoch)  # Too far in future
    
    def test_check_epoch_duplicate(self):
        """Test epoch validation rejects duplicates."""
        detector = ReplayDetector(epoch_window=10)
        
        current_epoch = 100
        
        # First check should pass
        assert detector.check_epoch("key1", 95, current_epoch)
        
        # Mark as processed
        detector.mark_epoch_processed("key1", 95)
        
        # Second check should fail
        assert not detector.check_epoch("key1", 95, current_epoch)
    
    def test_check_epoch_different_keys_independent(self):
        """Test that epochs for different keys are independent."""
        detector = ReplayDetector(epoch_window=10)
        
        current_epoch = 100
        
        # Process epoch for key1
        detector.mark_epoch_processed("key1", 95)
        
        # Same epoch for key2 should be valid
        assert detector.check_epoch("key2", 95, current_epoch)
    
    def test_check_nonce_new(self):
        """Test nonce checking with new nonce."""
        detector = ReplayDetector()
        
        nonce = b"unique_nonce_123"
        assert detector.check_nonce("key1", nonce)
    
    def test_check_nonce_duplicate(self):
        """Test nonce checking rejects duplicates."""
        detector = ReplayDetector()
        
        nonce = b"unique_nonce_123"
        
        # First check should pass
        assert detector.check_nonce("key1", nonce)
        
        # Mark as used
        detector.mark_nonce_used("key1", nonce)
        
        # Second check should fail
        assert not detector.check_nonce("key1", nonce)
    
    def test_nonce_different_keys_independent(self):
        """Test that nonces for different keys are independent."""
        detector = ReplayDetector()
        
        nonce = b"same_nonce"
        
        # Use nonce for key1
        detector.mark_nonce_used("key1", nonce)
        
        # Same nonce for key2 should be valid
        assert detector.check_nonce("key2", nonce)
    
    def test_validate_beacon_valid(self):
        """Test beacon validation with valid inputs."""
        detector = ReplayDetector(epoch_window=10)
        
        valid, reason = detector.validate_beacon("key1", 95, 100, b"nonce1")
        
        assert valid
        assert reason == "Valid"
    
    def test_validate_beacon_invalid_epoch(self):
        """Test beacon validation with invalid epoch."""
        detector = ReplayDetector(epoch_window=10)
        
        valid, reason = detector.validate_beacon("key1", 80, 100)
        
        assert not valid
        assert "epoch" in reason.lower()
    
    def test_validate_beacon_duplicate_nonce(self):
        """Test beacon validation with duplicate nonce."""
        detector = ReplayDetector(epoch_window=10)
        
        nonce = b"nonce1"
        
        # First validation should pass
        valid1, _ = detector.validate_beacon("key1", 95, 100, nonce)
        assert valid1
        
        # Accept the beacon
        detector.accept_beacon("key1", 95, nonce)
        
        # Second validation with same nonce should fail
        valid2, reason2 = detector.validate_beacon("key1", 96, 100, nonce)
        assert not valid2
        assert "nonce" in reason2.lower()
    
    def test_accept_beacon(self):
        """Test accepting a beacon marks epoch and nonce."""
        detector = ReplayDetector(epoch_window=10)
        
        detector.accept_beacon("key1", 95, b"nonce1")
        
        # Epoch should be marked
        assert not detector.check_epoch("key1", 95, 100)
        
        # Nonce should be marked
        assert not detector.check_nonce("key1", b"nonce1")
    
    def test_cleanup_old_data(self):
        """Test cleanup of old epoch data."""
        detector = ReplayDetector(epoch_window=10)
        
        # Process some old epochs
        for epoch in range(50, 60):
            detector.mark_epoch_processed("key1", epoch)
        
        # Cleanup (current epoch is 100, should remove epochs < 80)
        detector.cleanup_old_data(100)
        
        # Old epochs should be removed
        assert 50 not in detector._processed_epochs.get("key1", set())
        
    def test_nonce_bounded_memory(self):
        """Test that nonce storage is bounded."""
        detector = ReplayDetector(max_nonces_per_key=100)
        
        # Add more nonces than the limit
        for i in range(150):
            nonce = f"nonce_{i}".encode()
            detector.mark_nonce_used("key1", nonce)
        
        # Deque should be bounded to 100
        assert len(detector._nonces["key1"]) == 100


class TestIntegrityVerifier:
    """Test IntegrityVerifier functionality."""
    
    def test_initialization(self):
        """Test integrity verifier initialization."""
        sig_manager = SignatureKeyManager("node1")
        verifier = IntegrityVerifier(sig_manager)
        
        assert verifier.signature_key_manager is sig_manager
        assert isinstance(verifier.replay_detector, ReplayDetector)
    
    def test_verify_beacon_integrity_valid(self):
        """Test beacon integrity verification with valid inputs."""
        sig_manager = SignatureKeyManager("node1")
        verifier = IntegrityVerifier(sig_manager)
        
        # Create signed message
        payload = b"beacon payload"
        signing_key = sig_manager.get_signing_key()
        signature = signing_key.sign(payload)
        key_id = sig_manager.get_current_key_id()
        
        # Create MAC
        mac_key = b"mac_key_32_bytes_long_0000000"
        import hmac
        import hashlib
        mac = hmac.new(mac_key, payload, hashlib.sha256).digest()
        
        # Verify
        valid, reason = verifier.verify_beacon_integrity(
            payload, signature, mac,
            key="beacon_key", epoch=95, current_epoch=100,
            key_id=key_id, mac_key=mac_key
        )
        
        assert valid
        assert reason == "Valid"
    
    def test_verify_beacon_integrity_invalid_signature(self):
        """Test beacon integrity verification with invalid signature."""
        sig_manager = SignatureKeyManager("node1")
        verifier = IntegrityVerifier(sig_manager)
        
        payload = b"beacon payload"
        wrong_signature = b'\x00' * 64
        key_id = sig_manager.get_current_key_id()
        
        valid, reason = verifier.verify_beacon_integrity(
            payload, wrong_signature, b'\x00' * 32,
            key="beacon_key", epoch=95, current_epoch=100,
            key_id=key_id
        )
        
        assert not valid
        assert "signature" in reason.lower()
    
    def test_verify_beacon_integrity_replay_attack(self):
        """Test beacon integrity verification detects replay attacks."""
        sig_manager = SignatureKeyManager("node1")
        verifier = IntegrityVerifier(sig_manager)
        
        payload = b"beacon payload"
        signing_key = sig_manager.get_signing_key()
        signature = signing_key.sign(payload)
        key_id = sig_manager.get_current_key_id()
        
        # First verification should pass
        valid1, _ = verifier.verify_beacon_integrity(
            payload, signature, b'\x00' * 32,
            key="beacon_key", epoch=95, current_epoch=100,
            key_id=key_id
        )
        assert valid1
        
        # Accept beacon
        verifier.accept_verified_beacon("beacon_key", 95)
        
        # Second verification with same epoch should fail
        valid2, reason2 = verifier.verify_beacon_integrity(
            payload, signature, b'\x00' * 32,
            key="beacon_key", epoch=95, current_epoch=100,
            key_id=key_id
        )
        assert not valid2
        assert "replay" in reason2.lower()
    
    def test_accept_verified_beacon(self):
        """Test accepting a verified beacon."""
        sig_manager = SignatureKeyManager("node1")
        verifier = IntegrityVerifier(sig_manager)
        
        verifier.accept_verified_beacon("beacon_key", 95, b"nonce1")
        
        # Replay detector should have marked epoch and nonce
        assert not verifier.replay_detector.check_epoch("beacon_key", 95, 100)
        assert not verifier.replay_detector.check_nonce("beacon_key", b"nonce1")
