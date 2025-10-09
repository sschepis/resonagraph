"""
Data integrity verification for ResonaGraph.

Implements HMAC protection for phase chunks and replay attack prevention
according to Phase 6B specifications.
"""

import hmac
import hashlib
import time
import threading
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque

from resonagraph.security.audit import AuditLogger, AuditEvent, AuditEventType


class IntegrityError(Exception):
    """Base exception for integrity violations."""
    pass


class MACVerificationError(IntegrityError):
    """Raised when MAC verification fails."""
    pass


class ReplayAttackError(IntegrityError):
    """Raised when a replay attack is detected."""
    pass


@dataclass
class MACInfo:
    """Information about a MAC-protected chunk."""
    chunk_id: str
    mac: bytes
    chunk_size: int
    created_at: float
    algorithm: str = "HMAC-SHA256"


@dataclass
class EpochRecord:
    """Record of a processed epoch for replay detection."""
    key: str
    epoch: float
    first_seen: float
    last_seen: float
    signature_key_id: Optional[str] = None
    node_id: Optional[str] = None


class ReplayDetector:
    """
    Detects and prevents replay attacks using epoch tracking.
    
    Maintains a sliding window of processed epochs per key to detect
    attempts to replay old beacons.
    """
    
    def __init__(
        self,
        window_size: int = 10,  # Number of epochs to track
        max_age: int = 300,     # Maximum age in seconds
        audit_logger: Optional[AuditLogger] = None
    ):
        """
        Initialize replay detector.
        
        Args:
            window_size: Number of epochs to track per key
            max_age: Maximum age of epochs to accept (seconds)
            audit_logger: Audit logger for replay events
        """
        self.window_size = window_size
        self.max_age = max_age
        self.audit_logger = audit_logger
        
        # Track processed epochs per key
        self._epoch_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._epoch_records: Dict[Tuple[str, float], EpochRecord] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'epochs_processed': 0,
            'replay_attempts_blocked': 0,
            'expired_epochs_rejected': 0,
            'duplicate_epochs_detected': 0
        }
    
    def check_epoch(
        self,
        key: str,
        epoch: float,
        signature_key_id: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> bool:
        """
        Check if an epoch is valid (not a replay).
        
        Args:
            key: Key associated with the epoch
            epoch: Epoch timestamp
            signature_key_id: Optional signing key ID
            node_id: Optional node ID that created the epoch
            
        Returns:
            True if epoch is valid
            
        Raises:
            ReplayAttackError: If replay is detected
        """
        with self._lock:
            current_time = time.time()
            
            # Check if epoch is too old
            if current_time - epoch > self.max_age:
                self.stats['expired_epochs_rejected'] += 1
                
                if self.audit_logger:
                    self.audit_logger.log_security_event(
                        AuditEventType.REPLAY_DETECTED,
                        key,
                        "blocked",
                        metadata={
                            "reason": "expired_epoch",
                            "epoch": epoch,
                            "age": current_time - epoch,
                            "max_age": self.max_age
                        }
                    )
                
                raise ReplayAttackError(f"Epoch {epoch} is too old (age: {current_time - epoch:.1f}s)")
            
            # Check if we've seen this exact epoch before
            epoch_key = (key, epoch)
            if epoch_key in self._epoch_records:
                existing_record = self._epoch_records[epoch_key]
                
                # Allow if from same node (legitimate retransmission)
                if node_id and existing_record.node_id == node_id:
                    existing_record.last_seen = current_time
                    return True
                
                # Otherwise it's a potential replay attack
                self.stats['duplicate_epochs_detected'] += 1
                
                if self.audit_logger:
                    self.audit_logger.log_security_event(
                        AuditEventType.REPLAY_DETECTED,
                        key,
                        "blocked",
                        metadata={
                            "reason": "duplicate_epoch",
                            "epoch": epoch,
                            "first_seen": existing_record.first_seen,
                            "original_node": existing_record.node_id,
                            "current_node": node_id
                        }
                    )
                
                raise ReplayAttackError(f"Duplicate epoch {epoch} detected for key {key}")
            
            # Check if epoch is significantly in the future (clock skew protection)
            future_threshold = 60  # Allow 60 seconds of clock skew
            if epoch > current_time + future_threshold:
                if self.audit_logger:
                    self.audit_logger.log_security_event(
                        AuditEventType.REPLAY_DETECTED,
                        key,
                        "blocked",
                        metadata={
                            "reason": "future_epoch",
                            "epoch": epoch,
                            "current_time": current_time,
                            "skew": epoch - current_time
                        }
                    )
                
                raise ReplayAttackError(f"Epoch {epoch} is too far in the future")
            
            # Record this epoch
            record = EpochRecord(
                key=key,
                epoch=epoch,
                first_seen=current_time,
                last_seen=current_time,
                signature_key_id=signature_key_id,
                node_id=node_id
            )
            
            self._epoch_records[epoch_key] = record
            self._epoch_windows[key].append(epoch)
            
            self.stats['epochs_processed'] += 1
            
            return True
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired epoch records.
        
        Returns:
            Number of records cleaned up
        """
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for epoch_key, record in self._epoch_records.items():
                if current_time - record.last_seen > self.max_age:
                    expired_keys.append(epoch_key)
            
            for epoch_key in expired_keys:
                del self._epoch_records[epoch_key]
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get replay detector statistics."""
        return self.stats.copy()
    
    def get_epoch_info(self, key: str) -> List[float]:
        """Get processed epochs for a key."""
        with self._lock:
            return list(self._epoch_windows[key])


class PhaseMAC:
    """
    Provides HMAC authentication for phase chunks.
    
    Implements per-chunk MAC verification to ensure phase data integrity
    and authenticity.
    """
    
    def __init__(self, mac_key: bytes, algorithm: str = "HMAC-SHA256"):
        """
        Initialize phase MAC system.
        
        Args:
            mac_key: Key for HMAC computation
            algorithm: MAC algorithm to use
        """
        self.mac_key = mac_key
        self.algorithm = algorithm
        
        # Choose hash function based on algorithm
        if algorithm == "HMAC-SHA256":
            self.hash_func = hashlib.sha256
        elif algorithm == "HMAC-SHA512":
            self.hash_func = hashlib.sha512
        else:
            raise ValueError(f"Unsupported MAC algorithm: {algorithm}")
        
        # Statistics
        self.stats = {
            'macs_computed': 0,
            'macs_verified': 0,
            'verification_failures': 0
        }
    
    def compute_mac(
        self,
        chunk_data: bytes,
        chunk_index: int,
        prime: int,
        additional_data: Optional[bytes] = None
    ) -> bytes:
        """
        Compute MAC for a phase chunk.
        
        Args:
            chunk_data: Phase chunk data
            chunk_index: Index of the chunk
            prime: Prime associated with the chunk
            additional_data: Optional additional authenticated data
            
        Returns:
            MAC bytes
        """
        # Create message to authenticate
        message = self._create_mac_message(chunk_data, chunk_index, prime, additional_data)
        
        # Compute HMAC
        mac = hmac.new(self.mac_key, message, self.hash_func).digest()
        
        self.stats['macs_computed'] += 1
        
        return mac
    
    def verify_mac(
        self,
        chunk_data: bytes,
        chunk_index: int,
        prime: int,
        expected_mac: bytes,
        additional_data: Optional[bytes] = None
    ) -> bool:
        """
        Verify MAC for a phase chunk.
        
        Args:
            chunk_data: Phase chunk data
            chunk_index: Index of the chunk
            prime: Prime associated with the chunk
            expected_mac: Expected MAC value
            additional_data: Optional additional authenticated data
            
        Returns:
            True if MAC is valid
            
        Raises:
            MACVerificationError: If MAC verification fails
        """
        try:
            # Compute expected MAC
            computed_mac = self.compute_mac(chunk_data, chunk_index, prime, additional_data)
            
            # Use constant-time comparison
            if hmac.compare_digest(computed_mac, expected_mac):
                self.stats['macs_verified'] += 1
                return True
            else:
                self.stats['verification_failures'] += 1
                return False
        
        except Exception as e:
            self.stats['verification_failures'] += 1
            raise MACVerificationError(f"MAC verification failed: {e}")
    
    def batch_verify_macs(
        self,
        chunks: List[Tuple[bytes, int, int, bytes]],  # (data, index, prime, mac)
        additional_data: Optional[bytes] = None
    ) -> Tuple[bool, List[int]]:
        """
        Verify MACs for multiple chunks efficiently.
        
        Args:
            chunks: List of (chunk_data, chunk_index, prime, expected_mac) tuples
            additional_data: Optional additional authenticated data
            
        Returns:
            (all_valid, failed_indices) tuple
        """
        failed_indices = []
        
        for i, (chunk_data, chunk_index, prime, expected_mac) in enumerate(chunks):
            try:
                if not self.verify_mac(chunk_data, chunk_index, prime, expected_mac, additional_data):
                    failed_indices.append(i)
            except MACVerificationError:
                failed_indices.append(i)
        
        return len(failed_indices) == 0, failed_indices
    
    def _create_mac_message(
        self,
        chunk_data: bytes,
        chunk_index: int,
        prime: int,
        additional_data: Optional[bytes]
    ) -> bytes:
        """
        Create the message to be authenticated.
        
        Args:
            chunk_data: Phase chunk data
            chunk_index: Index of the chunk
            prime: Prime associated with the chunk
            additional_data: Optional additional data
            
        Returns:
            Message bytes for MAC computation
        """
        # Create structured message
        message_parts = [
            chunk_data,
            chunk_index.to_bytes(4, 'big'),
            prime.to_bytes(8, 'big'),  # Primes can be large
        ]
        
        if additional_data:
            message_parts.append(additional_data)
        
        return b''.join(message_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get MAC statistics."""
        return self.stats.copy()


class IntegrityManager:
    """
    High-level integrity management for ResonaGraph.
    
    Coordinates replay detection and MAC verification for comprehensive
    data integrity protection.
    """
    
    def __init__(
        self,
        mac_key: bytes,
        audit_logger: Optional[AuditLogger] = None,
        replay_window_size: int = 10,
        replay_max_age: int = 300
    ):
        """
        Initialize integrity manager.
        
        Args:
            mac_key: Key for MAC computation
            audit_logger: Audit logger for integrity events
            replay_window_size: Replay detection window size
            replay_max_age: Maximum age for replay detection
        """
        self.mac_system = PhaseMAC(mac_key)
        self.replay_detector = ReplayDetector(
            window_size=replay_window_size,
            max_age=replay_max_age,
            audit_logger=audit_logger
        )
        self.audit_logger = audit_logger
        
        # Combined statistics
        self.stats = {
            'integrity_checks': 0,
            'integrity_violations': 0,
            'replay_attacks_blocked': 0,
            'mac_failures': 0
        }
    
    def verify_beacon_integrity(
        self,
        beacon_key: str,
        epoch: float,
        phase_chunks: List[Tuple[bytes, int, int]],  # (data, index, prime)
        chunk_macs: List[bytes],
        node_id: Optional[str] = None,
        signature_key_id: Optional[str] = None
    ) -> bool:
        """
        Verify complete beacon integrity (replay + MAC).
        
        Args:
            beacon_key: Beacon key
            epoch: Beacon epoch
            phase_chunks: List of (chunk_data, chunk_index, prime) tuples
            chunk_macs: List of MAC values for chunks
            node_id: Optional node ID
            signature_key_id: Optional signature key ID
            
        Returns:
            True if beacon integrity is valid
            
        Raises:
            IntegrityError: If integrity check fails
        """
        self.stats['integrity_checks'] += 1
        
        try:
            # 1. Check for replay attacks
            self.replay_detector.check_epoch(
                beacon_key, epoch, signature_key_id, node_id
            )
            
            # 2. Verify phase chunk MACs
            if len(phase_chunks) != len(chunk_macs):
                raise IntegrityError("Mismatch between chunk count and MAC count")
            
            mac_chunks = [
                (chunk_data, chunk_index, prime, mac)
                for (chunk_data, chunk_index, prime), mac
                in zip(phase_chunks, chunk_macs)
            ]
            
            all_valid, failed_indices = self.mac_system.batch_verify_macs(
                mac_chunks,
                additional_data=f"{beacon_key}:{epoch}".encode()
            )
            
            if not all_valid:
                self.stats['mac_failures'] += 1
                
                if self.audit_logger:
                    self.audit_logger.log_security_event(
                        AuditEventType.INTEGRITY_VIOLATION,
                        beacon_key,
                        "failure",
                        metadata={
                            "reason": "mac_verification_failed",
                            "failed_chunks": failed_indices,
                            "epoch": epoch
                        }
                    )
                
                raise MACVerificationError(f"MAC verification failed for chunks: {failed_indices}")
            
            # All checks passed
            return True
        
        except ReplayAttackError:
            self.stats['replay_attacks_blocked'] += 1
            self.stats['integrity_violations'] += 1
            raise
        
        except (MACVerificationError, IntegrityError):
            self.stats['integrity_violations'] += 1
            raise
        
        except Exception as e:
            self.stats['integrity_violations'] += 1
            
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.INTEGRITY_VIOLATION,
                    beacon_key,
                    "error",
                    metadata={
                        "reason": "unexpected_error",
                        "error": str(e),
                        "epoch": epoch
                    }
                )
            
            raise IntegrityError(f"Integrity verification failed: {e}")
    
    def create_protected_chunks(
        self,
        beacon_key: str,
        epoch: float,
        phase_chunks: List[Tuple[bytes, int, int]]  # (data, index, prime)
    ) -> List[bytes]:
        """
        Create MAC-protected phase chunks.
        
        Args:
            beacon_key: Beacon key
            epoch: Beacon epoch
            phase_chunks: List of (chunk_data, chunk_index, prime) tuples
            
        Returns:
            List of MAC values for the chunks
        """
        chunk_macs = []
        additional_data = f"{beacon_key}:{epoch}".encode()
        
        for chunk_data, chunk_index, prime in phase_chunks:
            mac = self.mac_system.compute_mac(
                chunk_data, chunk_index, prime, additional_data
            )
            chunk_macs.append(mac)
        
        return chunk_macs
    
    def cleanup_expired(self) -> int:
        """Clean up expired replay detection records."""
        return self.replay_detector.cleanup_expired()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined integrity statistics."""
        combined_stats = self.stats.copy()
        combined_stats.update({
            'mac_stats': self.mac_system.get_stats(),
            'replay_stats': self.replay_detector.get_stats()
        })
        return combined_stats


# Factory function for easy setup
def create_integrity_manager(
    mac_key: bytes,
    audit_logger: Optional[AuditLogger] = None,
    **kwargs
) -> IntegrityManager:
    """
    Create and configure an integrity manager.
    
    Args:
        mac_key: Key for MAC computation
        audit_logger: Optional audit logger
        **kwargs: Additional arguments for IntegrityManager
        
    Returns:
        Configured integrity manager
    """
    return IntegrityManager(mac_key=mac_key, audit_logger=audit_logger, **kwargs)
