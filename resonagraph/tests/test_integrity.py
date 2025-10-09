"""
Test suite for HMAC-based integrity protection and replay attack prevention.

Tests the integrity manager, MAC computation, replay detection, and beacon
integrity verification according to Phase 6B security specifications.
"""

import pytest
import time
import secrets
import struct
from typing import List, Tuple, Dict, Any
from unittest.mock import Mock, patch

from resonagraph.security.integrity import (
    IntegrityManager, ReplayDetector,
    create_integrity_manager
)
from resonagraph.security.audit import AuditLogger


class TestReplayDetector:
    """Test the replay detector component."""
    
    @pytest.fixture
    def audit_logger(self):
        """Create a mock audit logger."""
        return Mock(spec=AuditLogger)
    
    def test_init(self, audit_logger):
        """Test detector initialization."""
        detector = ReplayDetector(
            audit_logger=audit_logger,
            window_size=100,
            max_age=300
        )
        
        assert detector.audit_logger is audit_logger
        assert detector.window_size == 100
        assert detector.max_age == 300
    
    def test_check_replay_new_epoch(self, audit_logger):
        """Test replay check for new epoch."""
        detector = ReplayDetector(audit_logger=audit_logger)
        
        current_time = time.time()
        
        # Should not be a replay
        is_replay = detector.check_replay(
            timestamp=current_time,
            beacon_key="test_beacon",
            node_id="test_node"
        )
        
        assert is_replay is False
        
        # Audit logger should not log replay event
        audit_logger.log_event.assert_not_called()
    
    def test_check_replay_duplicate_epoch(self, audit_logger):
        """Test replay check for duplicate epoch."""
        detector = ReplayDetector(audit_logger=audit_logger)
        
        current_time = time.time()
        beacon_key = "test_beacon"
        node_id = "test_node"
        
        # First check - should be OK
        is_replay_1 = detector.check_replay(current_time, beacon_key, node_id)
        assert is_replay_1 is False
        
        # Second check with same timestamp - should be replay
        is_replay_2 = detector.check_replay(current_time, beacon_key, node_id)
        assert is_replay_2 is True
        
        # Audit logger should log replay event
        audit_logger.log_event.assert_called()
    
    def test_check_replay_old_timestamp(self, audit_logger):
        """Test replay check for old timestamp."""
        detector = ReplayDetector(audit_logger=audit_logger)
        
        current_time = time.time()
        old_time = current_time - 3600  # 1 hour ago
        
        # Old timestamp should be detected as replay
        is_replay = detector.check_replay(
            timestamp=old_time,
            beacon_key="test_beacon",
            node_id="test_node"
        )
        
        assert is_replay is True
        audit_logger.log_event.assert_called()
    
    def test_cleanup_old_entries(self, audit_logger):
        """Test cleanup of old replay detection entries."""
        detector = ReplayDetector(audit_logger=audit_logger, window_size=10)
        
        # Add many entries
        current_time = time.time()
        for i in range(15):
            detector.check_replay(
                timestamp=current_time + i,
                beacon_key=f"beacon_{i}",
                node_id="test_node"
            )
        
        # Window should have been cleaned up
        assert len(detector.window.seen_epochs) <= 10
    
    def test_get_statistics(self, audit_logger):
        """Test statistics collection."""
        detector = ReplayDetector(audit_logger=audit_logger)
        
        current_time = time.time()
        
        # Generate some events
        detector.check_replay(current_time, "beacon1", "node1")
        detector.check_replay(current_time, "beacon1", "node1")  # Replay
        detector.check_replay(current_time + 1, "beacon2", "node2")
        
        stats = detector.get_statistics()
        
        assert "total_checks" in stats
        assert "replays_detected" in stats
        assert "window_size" in stats
        assert stats["total_checks"] >= 3
        assert stats["replays_detected"] >= 1


class TestIntegrityManager:
    """Test the main integrity manager."""
    
    @pytest.fixture
    def audit_logger(self):
        """Create a mock audit logger."""
        return Mock(spec=AuditLogger)
    
    @pytest.fixture
    def mac_key(self):
        """Create a test MAC key."""
        return secrets.token_bytes(32)
    
    def test_init(self, mac_key, audit_logger):
        """Test manager initialization."""
        manager = IntegrityManager(
            mac_key=mac_key,
            audit_logger=audit_logger
        )
        
        assert manager.mac_key == mac_key
        assert manager.audit_logger is audit_logger
        assert isinstance(manager.replay_detector, ReplayDetector)
        assert isinstance(manager.metrics, PerformanceMetrics)
    
    def test_create_protected_chunks(self, mac_key, audit_logger):
        """Test creation of MAC-protected chunks."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Test data
        beacon_key = "test_beacon"
        epoch = time.time()
        phase_chunks = [
            (b"chunk1", 0, 2),
            (b"chunk2", 1, 3),
            (b"chunk3", 2, 5)
        ]
        
        # Create protected chunks
        chunk_macs = manager.create_protected_chunks(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks
        )
        
        # Verify MACs were created
        assert len(chunk_macs) == 3
        assert all(len(mac) == 32 for mac in chunk_macs)  # SHA256 length
        
        # Verify MACs are different
        assert chunk_macs[0] != chunk_macs[1]
        assert chunk_macs[1] != chunk_macs[2]
    
    def test_verify_chunk_macs(self, mac_key, audit_logger):
        """Test verification of chunk MACs."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Test data
        beacon_key = "test_beacon"
        epoch = time.time()
        phase_chunks = [
            (b"chunk1", 0, 2),
            (b"chunk2", 1, 3)
        ]
        
        # Create MACs
        chunk_macs = manager.create_protected_chunks(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks
        )
        
        # Verify MACs
        is_valid = manager.verify_chunk_macs(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs
        )
        
        assert is_valid is True
    
    def test_verify_invalid_macs(self, mac_key, audit_logger):
        """Test verification of invalid MACs."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Test data
        beacon_key = "test_beacon"
        epoch = time.time()
        phase_chunks = [(b"chunk1", 0, 2)]
        
        # Create invalid MACs
        invalid_macs = [secrets.token_bytes(32)]
        
        # Verification should fail
        is_valid = manager.verify_chunk_macs(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks,
            chunk_macs=invalid_macs
        )
        
        assert is_valid is False
        
        # Audit logger should log failure
        audit_logger.log_event.assert_called()
    
    def test_verify_beacon_integrity(self, mac_key, audit_logger):
        """Test complete beacon integrity verification."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Test data
        beacon_key = "integrity_test_beacon"
        epoch = time.time()
        phase_chunks = [
            (struct.pack('>f', 1.23), 0, 2),
            (struct.pack('>f', 4.56), 1, 3),
            (struct.pack('>f', 7.89), 2, 5)
        ]
        node_id = "test_node"
        signature_key_id = "test_key_001"
        
        # Create protected chunks
        chunk_macs = manager.create_protected_chunks(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks
        )
        
        # Verify integrity
        is_valid = manager.verify_beacon_integrity(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs,
            node_id=node_id,
            signature_key_id=signature_key_id
        )
        
        assert is_valid is True
    
    def test_verify_beacon_integrity_replay(self, mac_key, audit_logger):
        """Test beacon integrity verification with replay attack."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Test data
        beacon_key = "replay_test_beacon"
        epoch = time.time()
        phase_chunks = [(struct.pack('>f', 1.23), 0, 2)]
        node_id = "test_node"
        signature_key_id = "test_key_001"
        
        # Create protected chunks
        chunk_macs = manager.create_protected_chunks(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks
        )
        
        # First verification should succeed
        is_valid_1 = manager.verify_beacon_integrity(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs,
            node_id=node_id,
            signature_key_id=signature_key_id
        )
        
        assert is_valid_1 is True
        
        # Second verification with same epoch should fail (replay)
        is_valid_2 = manager.verify_beacon_integrity(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs,
            node_id=node_id,
            signature_key_id=signature_key_id
        )
        
        assert is_valid_2 is False
    
    def test_rotate_mac_key(self, mac_key, audit_logger):
        """Test MAC key rotation."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        old_key = manager.mac_key
        
        # Rotate key
        new_key = manager.rotate_mac_key()
        
        # Verify key changed
        assert manager.mac_key != old_key
        assert manager.mac_key == new_key
        assert len(new_key) == 32
        
        # Verify audit logging
        audit_logger.log_event.assert_called()
    
    def test_get_performance_metrics(self, mac_key, audit_logger):
        """Test performance metrics collection."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Perform some operations
        beacon_key = "metrics_test_beacon"
        epoch = time.time()
        phase_chunks = [(b"chunk1", 0, 2)]
        
        # Create and verify chunks multiple times
        for i in range(3):
            chunk_macs = manager.create_protected_chunks(
                beacon_key=f"{beacon_key}_{i}",
                epoch=epoch + i,
                phase_chunks=phase_chunks
            )
            
            manager.verify_chunk_macs(
                beacon_key=f"{beacon_key}_{i}",
                epoch=epoch + i,
                phase_chunks=phase_chunks,
                chunk_macs=chunk_macs
            )
        
        # Check metrics
        metrics = manager.get_performance_metrics()
        
        assert "macs_created" in metrics
        assert "macs_verified" in metrics
        assert "replay_checks" in metrics
        assert "avg_mac_time_ms" in metrics
        assert metrics["macs_created"] >= 3
        assert metrics["macs_verified"] >= 3
    
    def test_mac_key_derivation(self, mac_key, audit_logger):
        """Test MAC key derivation for different contexts."""
        manager = IntegrityManager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Derive keys for different contexts
        key1 = manager._derive_mac_key("beacon_key_1", 1000.0)
        key2 = manager._derive_mac_key("beacon_key_2", 1000.0)
        key3 = manager._derive_mac_key("beacon_key_1", 2000.0)
        
        # Keys should be different for different inputs
        assert key1 != key2  # Different beacon keys
        assert key1 != key3  # Different epochs
        assert len(key1) == 32
        assert len(key2) == 32
        assert len(key3) == 32
        
        # Same inputs should produce same key
        key1_repeat = manager._derive_mac_key("beacon_key_1", 1000.0)
        assert key1 == key1_repeat


class TestFactoryFunction:
    """Test the factory function for creating integrity managers."""
    
    def test_create_integrity_manager_basic(self):
        """Test basic integrity manager creation."""
        mac_key = secrets.token_bytes(32)
        audit_logger = Mock(spec=AuditLogger)
        
        manager = create_integrity_manager(
            mac_key=mac_key,
            audit_logger=audit_logger
        )
        
        assert isinstance(manager, IntegrityManager)
        assert manager.mac_key == mac_key
        assert manager.audit_logger is audit_logger
    
    def test_create_integrity_manager_with_kwargs(self):
        """Test integrity manager creation with additional kwargs."""
        mac_key = secrets.token_bytes(32)
        audit_logger = Mock(spec=AuditLogger)
        
        manager = create_integrity_manager(
            mac_key=mac_key,
            audit_logger=audit_logger,
            replay_window_size=200,
            epoch_duration=30.0
        )
        
        assert isinstance(manager, IntegrityManager)
        assert manager.replay_detector.window.size == 200
        assert manager.replay_detector.window.epoch_duration == 30.0


class TestIntegrityIntegration:
    """Integration tests for the complete integrity system."""
    
    def test_end_to_end_integrity_workflow(self):
        """Test complete integrity protection workflow."""
        # Create components
        mac_key = secrets.token_bytes(32)
        audit_logger = Mock(spec=AuditLogger)
        
        manager = create_integrity_manager(
            mac_key=mac_key,
            audit_logger=audit_logger
        )
        
        # Create test beacon data
        beacon_key = "integration_beacon"
        epoch = time.time()
        
        # Simulate phase angles converted to bytes
        phase_angles = [1.23, 4.56, 7.89]
        primes = [2, 3, 5]
        
        phase_chunks = []
        for i, (angle, prime) in enumerate(zip(phase_angles, primes)):
            angle_bytes = struct.pack('>f', angle)
            phase_chunks.append((angle_bytes, i, prime))
        
        # Create integrity protection
        chunk_macs = manager.create_protected_chunks(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks
        )
        
        # Verify integrity (first time - should succeed)
        is_valid = manager.verify_beacon_integrity(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs,
            node_id="integration_test_node",
            signature_key_id="test_sig_key"
        )
        
        assert is_valid is True
        
        # Test replay protection (second verification with same epoch)
        is_replay = manager.verify_beacon_integrity(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs,
            node_id="integration_test_node",
            signature_key_id="test_sig_key"
        )
        
        assert is_replay is False  # Should be rejected as replay
        
        # Test with tampered data
        tampered_chunks = phase_chunks.copy()
        tampered_chunks[0] = (b"tampered", 0, 2)
        
        is_tampered = manager.verify_chunk_macs(
            beacon_key=beacon_key,
            epoch=epoch,
            phase_chunks=tampered_chunks,
            chunk_macs=chunk_macs
        )
        
        assert is_tampered is False  # Should fail MAC verification
    
    def test_concurrent_integrity_operations(self):
        """Test concurrent integrity operations."""
        import threading
        import concurrent.futures
        
        mac_key = secrets.token_bytes(32)
        audit_logger = Mock(spec=AuditLogger)
        manager = create_integrity_manager(mac_key=mac_key, audit_logger=audit_logger)
        
        def process_beacon(index):
            """Process a beacon in a thread."""
            beacon_key = f"concurrent_beacon_{index}"
            epoch = time.time() + index  # Slightly different epochs
            phase_chunks = [(struct.pack('>f', float(index)), 0, 2)]
            
            # Create and verify integrity
            chunk_macs = manager.create_protected_chunks(
                beacon_key=beacon_key,
                epoch=epoch,
                phase_chunks=phase_chunks
            )
            
            is_valid = manager.verify_beacon_integrity(
                beacon_key=beacon_key,
                epoch=epoch,
                phase_chunks=phase_chunks,
                chunk_macs=chunk_macs,
                node_id=f"node_{index}",
                signature_key_id=f"key_{index}"
            )
            
            return is_valid
        
        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_beacon, i) for i in range(10)]
            results = [future.result() for future in futures]
        
        # All operations should succeed
        assert all(results)
        
        # Check that metrics were updated correctly
        metrics = manager.get_performance_metrics()
        assert metrics["macs_created"] >= 10
        assert metrics["replay_checks"] >= 10
    
    def test_key_rotation_during_operations(self):
        """Test key rotation while operations are ongoing."""
        mac_key = secrets.token_bytes(32)
        audit_logger = Mock(spec=AuditLogger)
        manager = create_integrity_manager(mac_key=mac_key, audit_logger=audit_logger)
        
        # Create some protected chunks with original key
        beacon_key = "rotation_test_beacon"
        epoch1 = time.time()
        phase_chunks = [(b"chunk1", 0, 2)]
        
        chunk_macs_old = manager.create_protected_chunks(
            beacon_key=beacon_key,
            epoch=epoch1,
            phase_chunks=phase_chunks
        )
        
        # Rotate the MAC key
        new_key = manager.rotate_mac_key()
        
        # Create new protected chunks with new key
        epoch2 = time.time() + 1
        chunk_macs_new = manager.create_protected_chunks(
            beacon_key=beacon_key,
            epoch=epoch2,
            phase_chunks=phase_chunks
        )
        
        # Old chunks should still verify with old derived key
        # (since derivation includes beacon context)
        is_old_valid = manager.verify_chunk_macs(
            beacon_key=beacon_key,
            epoch=epoch1,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs_old
        )
        
        # New chunks should verify with new derived key
        is_new_valid = manager.verify_chunk_macs(
            beacon_key=beacon_key,
            epoch=epoch2,
            phase_chunks=phase_chunks,
            chunk_macs=chunk_macs_new
        )
        
        # Both should be valid (key derivation is deterministic)
        assert is_old_valid is True
        assert is_new_valid is True
        
        # But MACs should be different
        assert chunk_macs_old != chunk_macs_new
