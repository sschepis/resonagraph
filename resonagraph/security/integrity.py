"""
Integrity verification and replay attack prevention.

According to NEXT_STEPS.md 6.2:
- Per-chunk HMAC for phase authenticity
- MAC verification during residue extraction
- Epoch-based replay detection
- Nonce support for beacons
"""

import hashlib
import hmac
import time
from typing import Dict, Set, Tuple, Optional
from collections import deque
import threading


class PhaseMAC:
    """
    Manages HMAC-SHA256 for phase chunk authenticity.
    
    According to NEXT_STEPS.md 6.2:
    - HMAC-SHA256 for each phase chunk
    - Include chunk index and prime in MAC
    - Batch MAC verification for performance
    """
    
    @staticmethod
    def compute_chunk_mac(
        chunk_data: bytes,
        chunk_index: int,
        prime: int,
        key: bytes
    ) -> bytes:
        """
        Compute HMAC-SHA256 for a phase chunk.
        
        According to copilot-instructions.md:
        - Per-chunk HMAC for phase authenticity
        - Include chunk index and prime in MAC
        
        Args:
            chunk_data: Phase chunk data
            chunk_index: Index of this chunk
            prime: Prime number associated with chunk
            key: HMAC key
            
        Returns:
            32-byte HMAC-SHA256
        """
        # Build message: chunk_data || chunk_index || prime
        message = chunk_data + chunk_index.to_bytes(4, 'big') + prime.to_bytes(8, 'big')
        return hmac.new(key, message, hashlib.sha256).digest()
    
    @staticmethod
    def verify_chunk_mac(
        chunk_data: bytes,
        chunk_index: int,
        prime: int,
        expected_mac: bytes,
        key: bytes
    ) -> bool:
        """
        Verify HMAC-SHA256 for a phase chunk.
        
        Args:
            chunk_data: Phase chunk data
            chunk_index: Index of this chunk
            prime: Prime number associated with chunk
            expected_mac: Expected MAC value
            key: HMAC key
            
        Returns:
            True if MAC is valid
        """
        computed_mac = PhaseMAC.compute_chunk_mac(chunk_data, chunk_index, prime, key)
        return hmac.compare_digest(computed_mac, expected_mac)
    
    @staticmethod
    def batch_verify_macs(
        chunks: list[Tuple[bytes, int, int, bytes]],
        key: bytes
    ) -> bool:
        """
        Verify multiple MACs efficiently.
        
        According to NEXT_STEPS.md 6.2:
        - Batch MAC verification for performance
        
        Args:
            chunks: List of (chunk_data, chunk_index, prime, expected_mac) tuples
            key: HMAC key
            
        Returns:
            True if all MACs are valid
        """
        for chunk_data, chunk_index, prime, expected_mac in chunks:
            if not PhaseMAC.verify_chunk_mac(chunk_data, chunk_index, prime, expected_mac, key):
                return False
        return True


class ReplayDetector:
    """
    Prevents replay attacks using epoch and nonce tracking.
    
    According to NEXT_STEPS.md 6.2:
    - Track processed epochs per key
    - Reject beacons with old epochs
    - Sliding window for acceptable epochs
    - Nonce tracking to prevent replay
    """
    
    def __init__(
        self,
        epoch_window: int = 10,
        max_nonces_per_key: int = 10000
    ):
        """
        Initialize replay detector.
        
        Args:
            epoch_window: Number of epochs to accept (default 10)
            max_nonces_per_key: Maximum nonces to track per key
        """
        self.epoch_window = epoch_window
        self.max_nonces_per_key = max_nonces_per_key
        
        # Track processed epochs per key
        self._processed_epochs: Dict[str, Set[int]] = {}
        
        # Track nonces per key (using deque for bounded memory)
        self._nonces: Dict[str, deque] = {}
        
        # Lock for thread safety
        self._lock = threading.Lock()
    
    def check_epoch(self, key: str, epoch: int, current_epoch: int) -> bool:
        """
        Check if an epoch is valid (not too old, not in future).
        
        According to NEXT_STEPS.md 6.2:
        - Reject beacons with old epochs
        - Sliding window for acceptable epochs
        
        Args:
            key: Beacon key
            epoch: Epoch to check
            current_epoch: Current epoch number
            
        Returns:
            True if epoch is acceptable
        """
        # Check if epoch is within acceptable window
        min_epoch = current_epoch - self.epoch_window
        max_epoch = current_epoch + 1  # Allow 1 epoch in future for clock skew
        
        if epoch < min_epoch or epoch > max_epoch:
            return False
        
        # Check if we've already processed this epoch for this key
        with self._lock:
            if key in self._processed_epochs:
                if epoch in self._processed_epochs[key]:
                    # Duplicate epoch - likely replay
                    return False
        
        return True
    
    def mark_epoch_processed(self, key: str, epoch: int) -> None:
        """
        Mark an epoch as processed for a key.
        
        Args:
            key: Beacon key
            epoch: Epoch number
        """
        with self._lock:
            if key not in self._processed_epochs:
                self._processed_epochs[key] = set()
            
            self._processed_epochs[key].add(epoch)
            
            # Clean up old epochs (keep only recent window)
            current_epoch = epoch
            min_epoch = current_epoch - self.epoch_window * 2  # Keep 2x window for safety
            self._processed_epochs[key] = {
                e for e in self._processed_epochs[key]
                if e >= min_epoch
            }
    
    def check_nonce(self, key: str, nonce: bytes) -> bool:
        """
        Check if a nonce has been seen before.
        
        According to NEXT_STEPS.md 6.2:
        - Track nonces to prevent replay
        - Nonce expiration policy
        
        Args:
            key: Beacon key
            nonce: Nonce value
            
        Returns:
            True if nonce is new (not seen before)
        """
        with self._lock:
            if key not in self._nonces:
                self._nonces[key] = deque(maxlen=self.max_nonces_per_key)
            
            # Check if nonce exists
            if nonce in self._nonces[key]:
                return False  # Replay detected
            
            return True
    
    def mark_nonce_used(self, key: str, nonce: bytes) -> None:
        """
        Mark a nonce as used.
        
        Args:
            key: Beacon key
            nonce: Nonce value
        """
        with self._lock:
            if key not in self._nonces:
                self._nonces[key] = deque(maxlen=self.max_nonces_per_key)
            
            self._nonces[key].append(nonce)
    
    def validate_beacon(
        self,
        key: str,
        epoch: int,
        current_epoch: int,
        nonce: Optional[bytes] = None
    ) -> Tuple[bool, str]:
        """
        Validate a beacon against replay attacks.
        
        Args:
            key: Beacon key
            epoch: Beacon epoch
            current_epoch: Current epoch
            nonce: Optional nonce
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check epoch
        if not self.check_epoch(key, epoch, current_epoch):
            return False, "Invalid epoch (too old or already processed)"
        
        # Check nonce if provided
        if nonce is not None:
            if not self.check_nonce(key, nonce):
                return False, "Duplicate nonce detected (replay attack)"
        
        return True, "Valid"
    
    def accept_beacon(
        self,
        key: str,
        epoch: int,
        nonce: Optional[bytes] = None
    ) -> None:
        """
        Accept a beacon (mark epoch and nonce as used).
        
        Args:
            key: Beacon key
            epoch: Beacon epoch
            nonce: Optional nonce
        """
        self.mark_epoch_processed(key, epoch)
        if nonce is not None:
            self.mark_nonce_used(key, nonce)
    
    def cleanup_old_data(self, current_epoch: int) -> None:
        """
        Clean up old epoch and nonce data.
        
        Args:
            current_epoch: Current epoch number
        """
        min_epoch = current_epoch - self.epoch_window * 2
        
        with self._lock:
            # Clean up old epochs
            for key in list(self._processed_epochs.keys()):
                self._processed_epochs[key] = {
                    e for e in self._processed_epochs[key]
                    if e >= min_epoch
                }
                
                # Remove empty entries
                if not self._processed_epochs[key]:
                    del self._processed_epochs[key]
            
            # Nonces are automatically bounded by deque maxlen,
            # so no cleanup needed


class IntegrityVerifier:
    """
    Combined integrity verification system.
    
    Integrates signature verification, MAC verification, and replay detection.
    """
    
    def __init__(
        self,
        signature_key_manager,
        replay_detector: Optional[ReplayDetector] = None
    ):
        """
        Initialize integrity verifier.
        
        Args:
            signature_key_manager: SignatureKeyManager instance
            replay_detector: Optional ReplayDetector (created if not provided)
        """
        self.signature_key_manager = signature_key_manager
        self.replay_detector = replay_detector or ReplayDetector()
    
    def verify_beacon_integrity(
        self,
        payload: bytes,
        signature: bytes,
        mac: bytes,
        key: str,
        epoch: int,
        current_epoch: int,
        key_id: Optional[str] = None,
        mac_key: Optional[bytes] = None,
        nonce: Optional[bytes] = None
    ) -> Tuple[bool, str]:
        """
        Verify complete beacon integrity.
        
        According to NEXT_STEPS.md 6.2:
        - Verify beacon signatures before processing
        - Verify MACs during residue extraction
        - Check for replay attacks
        
        Args:
            payload: Beacon payload
            signature: Ed25519 signature
            mac: HMAC-SHA256
            key: Beacon key
            epoch: Beacon epoch
            current_epoch: Current epoch
            key_id: Optional signature key ID
            mac_key: Optional MAC key
            nonce: Optional nonce
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check replay attack
        replay_valid, replay_reason = self.replay_detector.validate_beacon(
            key, epoch, current_epoch, nonce
        )
        if not replay_valid:
            return False, f"Replay check failed: {replay_reason}"
        
        # Verify signature
        sig_valid = self.signature_key_manager.verify_signature(
            payload, signature, key_id=key_id
        )
        if not sig_valid:
            return False, "Signature verification failed"
        
        # Verify MAC if key provided
        if mac_key is not None:
            computed_mac = hmac.new(mac_key, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(computed_mac, mac):
                return False, "MAC verification failed"
        
        return True, "Valid"
    
    def accept_verified_beacon(
        self,
        key: str,
        epoch: int,
        nonce: Optional[bytes] = None
    ) -> None:
        """
        Accept a verified beacon.
        
        Args:
            key: Beacon key
            epoch: Beacon epoch
            nonce: Optional nonce
        """
        self.replay_detector.accept_beacon(key, epoch, nonce)
