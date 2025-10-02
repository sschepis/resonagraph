"""
Audit logging for security events.

According to NEXT_STEPS.md 6.3:
- Structured logging (JSON format)
- Asynchronous logging for performance
- Log rotation and retention policies
- Tamper-evident logging (hash chain)
- Track lock attempts, access denials, key operations
"""

import json
import hashlib
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler


class AuditEventType(Enum):
    """Types of audit events."""
    LOCK_ATTEMPT = "lock_attempt"
    LOCK_SUCCESS = "lock_success"
    LOCK_FAILURE = "lock_failure"
    ACCESS_DENIED = "access_denied"
    ACCESS_GRANTED = "access_granted"
    KEY_GENERATED = "key_generated"
    KEY_ROTATED = "key_rotated"
    KEY_REVOKED = "key_revoked"
    KEY_DERIVED = "key_derived"
    SIGNATURE_VERIFIED = "signature_verified"
    SIGNATURE_FAILED = "signature_failed"
    MAC_VERIFIED = "mac_verified"
    MAC_FAILED = "mac_failed"
    REPLAY_DETECTED = "replay_detected"
    POLICY_VIOLATION = "policy_violation"
    HSM_OPERATION = "hsm_operation"


@dataclass
class AuditEvent:
    """
    Represents an audit log event.
    
    According to NEXT_STEPS.md 6.3:
    - Event type (lock_attempt, access_denied, key_rotation, etc.)
    - Timestamp, actor (anonymized fingerprint), resource
    - Action, outcome, metadata
    """
    event_type: AuditEventType
    timestamp: float
    actor: str  # Anonymized fingerprint
    resource: str
    action: str
    outcome: str  # success, failure, denied
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # For hash chain (tamper-evident logging)
    previous_hash: Optional[str] = None
    event_hash: Optional[str] = None
    
    def compute_hash(self) -> str:
        """
        Compute hash of this event for tamper-evident logging.
        
        Returns:
            SHA-256 hash of event data
        """
        # Create deterministic representation
        event_data = {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'actor': self.actor,
            'resource': self.resource,
            'action': self.action,
            'outcome': self.outcome,
            'metadata': self.metadata,
            'previous_hash': self.previous_hash or ''
        }
        
        # Sort keys for deterministic ordering
        json_str = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        return data
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


class AuditLogger:
    """
    Manages audit logging with tamper-evident hash chain.
    
    According to NEXT_STEPS.md 6.3:
    - Structured logging (JSON format)
    - Asynchronous logging for performance
    - Log rotation and retention policies
    - Tamper-evident logging (hash chain)
    """
    
    def __init__(
        self,
        log_file: str = "audit.log",
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 10,
        enable_hash_chain: bool = True
    ):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            enable_hash_chain: Enable tamper-evident hash chain
        """
        self.enable_hash_chain = enable_hash_chain
        self._last_hash: Optional[str] = None
        self._lock = threading.Lock()
        
        # Create log directory if needed
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up rotating file handler
        self.logger = logging.getLogger('resonagraph.audit')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Don't propagate to root logger
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Add rotating file handler
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
    
    def log_event(
        self,
        event_type: AuditEventType,
        actor: str,
        resource: str,
        action: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            actor: Actor (anonymized fingerprint)
            resource: Resource being accessed
            action: Action being performed
            outcome: Outcome (success, failure, denied)
            metadata: Optional additional metadata
            
        Returns:
            Created audit event
        """
        with self._lock:
            event = AuditEvent(
                event_type=event_type,
                timestamp=time.time(),
                actor=actor,
                resource=resource,
                action=action,
                outcome=outcome,
                metadata=metadata or {},
                previous_hash=self._last_hash if self.enable_hash_chain else None
            )
            
            # Compute hash for hash chain
            if self.enable_hash_chain:
                event.event_hash = event.compute_hash()
                self._last_hash = event.event_hash
            
            # Write to log
            self.logger.info(event.to_json())
            
            return event
    
    def log_lock_attempt(
        self,
        actor: str,
        key: str,
        success: bool,
        convergence_metrics: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """
        Log a resonance lock attempt.
        
        Args:
            actor: Actor fingerprint
            key: Key being locked
            success: Whether lock succeeded
            convergence_metrics: Optional convergence metrics
            
        Returns:
            Audit event
        """
        return self.log_event(
            event_type=AuditEventType.LOCK_SUCCESS if success else AuditEventType.LOCK_FAILURE,
            actor=actor,
            resource=key,
            action="lock",
            outcome="success" if success else "failure",
            metadata=convergence_metrics or {}
        )
    
    def log_access_decision(
        self,
        actor: str,
        resource: str,
        action: str,
        granted: bool,
        reason: Optional[str] = None
    ) -> AuditEvent:
        """
        Log an access control decision.
        
        Args:
            actor: Actor (role:name or user:name)
            resource: Resource being accessed
            action: Action being performed
            granted: Whether access was granted
            reason: Optional reason for decision
            
        Returns:
            Audit event
        """
        return self.log_event(
            event_type=AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED,
            actor=actor,
            resource=resource,
            action=action,
            outcome="granted" if granted else "denied",
            metadata={'reason': reason} if reason else {}
        )
    
    def log_key_operation(
        self,
        operation: str,
        key_id: str,
        key_type: str,
        actor: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """
        Log a key operation.
        
        Args:
            operation: Operation (generate, rotate, revoke, derive)
            key_id: Key identifier
            key_type: Key type (root, topic, role, signature)
            actor: Actor performing operation
            metadata: Optional additional metadata
            
        Returns:
            Audit event
        """
        event_type_map = {
            'generate': AuditEventType.KEY_GENERATED,
            'rotate': AuditEventType.KEY_ROTATED,
            'revoke': AuditEventType.KEY_REVOKED,
            'derive': AuditEventType.KEY_DERIVED,
        }
        
        return self.log_event(
            event_type=event_type_map.get(operation, AuditEventType.KEY_GENERATED),
            actor=actor,
            resource=key_id,
            action=operation,
            outcome="success",
            metadata={'key_type': key_type, **(metadata or {})}
        )
    
    def log_signature_verification(
        self,
        key_id: str,
        success: bool,
        actor: str = "system"
    ) -> AuditEvent:
        """
        Log a signature verification attempt.
        
        Args:
            key_id: Key identifier used for verification
            success: Whether verification succeeded
            actor: Actor performing verification
            
        Returns:
            Audit event
        """
        return self.log_event(
            event_type=AuditEventType.SIGNATURE_VERIFIED if success else AuditEventType.SIGNATURE_FAILED,
            actor=actor,
            resource=key_id,
            action="verify_signature",
            outcome="success" if success else "failure"
        )
    
    def log_mac_verification(
        self,
        resource: str,
        success: bool,
        actor: str = "system"
    ) -> AuditEvent:
        """
        Log a MAC verification attempt.
        
        Args:
            resource: Resource being verified
            success: Whether verification succeeded
            actor: Actor performing verification
            
        Returns:
            Audit event
        """
        return self.log_event(
            event_type=AuditEventType.MAC_VERIFIED if success else AuditEventType.MAC_FAILED,
            actor=actor,
            resource=resource,
            action="verify_mac",
            outcome="success" if success else "failure"
        )
    
    def log_replay_detected(
        self,
        key: str,
        epoch: int,
        nonce: Optional[str] = None
    ) -> AuditEvent:
        """
        Log a replay attack detection.
        
        Args:
            key: Beacon key
            epoch: Epoch number
            nonce: Optional nonce
            
        Returns:
            Audit event
        """
        return self.log_event(
            event_type=AuditEventType.REPLAY_DETECTED,
            actor="system",
            resource=key,
            action="beacon_validation",
            outcome="replay_detected",
            metadata={'epoch': epoch, 'nonce': nonce}
        )
    
    def verify_hash_chain(self, events: List[AuditEvent]) -> bool:
        """
        Verify the integrity of a hash chain.
        
        Args:
            events: List of events in order
            
        Returns:
            True if hash chain is valid
        """
        if not self.enable_hash_chain:
            return True
        
        previous_hash = None
        for event in events:
            # Check that previous_hash matches
            if event.previous_hash != previous_hash:
                return False
            
            # Compute and verify event hash
            expected_hash = event.compute_hash()
            if event.event_hash != expected_hash:
                return False
            
            previous_hash = event.event_hash
        
        return True
    
    def get_last_hash(self) -> Optional[str]:
        """
        Get the last hash in the chain.
        
        Returns:
            Last hash or None
        """
        return self._last_hash
