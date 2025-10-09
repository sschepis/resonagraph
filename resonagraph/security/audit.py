"""
Audit logging for ResonaGraph security events.

Provides tamper-evident logging with anonymization for compliance
(GDPR, HIPAA, SOC2).
"""

import json
import time
import hashlib
import hmac
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union, TextIO
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from logging.handlers import RotatingFileHandler


class AnonymizationLevel(Enum):
    """Levels of anonymization for audit logs."""
    NONE = "none"        # No anonymization (dev only)
    LOW = "low"          # Hash PIDs and user IDs
    MEDIUM = "medium"    # Hash all identifiers
    HIGH = "high"        # Hash all identifiers + truncate data


class AuditEventType(Enum):
    """Types of audit events."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    
    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    
    # Key management events
    KEY_CREATED = "key_created"
    KEY_ROTATED = "key_rotated"
    KEY_REVOKED = "key_revoked"
    KEY_ACCESSED = "key_accessed"
    
    # Data access events
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    
    # Resonance events
    LOCK_ATTEMPT = "lock_attempt"
    LOCK_SUCCESS = "lock_success"
    LOCK_FAILED = "lock_failed"
    BEACON_VERIFIED = "beacon_verified"
    SIGNATURE_FAILED = "signature_failed"
    
    # Security events
    REPLAY_DETECTED = "replay_detected"
    INTEGRITY_VIOLATION = "integrity_violation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # System events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    CONFIGURATION_CHANGED = "configuration_changed"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class AuditEvent:
    """Represents a single audit event."""
    event_type: str
    timestamp: float
    resource: str
    action: str
    outcome: str  # success, failure, error
    actor: Optional[str] = None
    actor_ip: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate event data."""
        if self.timestamp is None:
            self.timestamp = time.time()
        
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """Create from dictionary."""
        return cls(**data)


class Anonymizer:
    """Handles anonymization of audit data."""
    
    def __init__(self, level: AnonymizationLevel, salt: Optional[bytes] = None):
        """
        Initialize anonymizer.
        
        Args:
            level: Anonymization level
            salt: Salt for hashing (generated if None)
        """
        self.level = level
        self.salt = salt or os.urandom(32)
        self._hash_cache: Dict[str, str] = {}
    
    def anonymize_event(self, event: AuditEvent) -> AuditEvent:
        """
        Anonymize an audit event based on configured level.
        
        Args:
            event: Original audit event
            
        Returns:
            Anonymized audit event
        """
        if self.level == AnonymizationLevel.NONE:
            return event
        
        # Create copy to avoid modifying original
        anonymized = AuditEvent(
            event_type=event.event_type,
            timestamp=event.timestamp,
            resource=self._anonymize_identifier(event.resource),
            action=event.action,
            outcome=event.outcome,
            actor=self._anonymize_identifier(event.actor) if event.actor else None,
            actor_ip=self._anonymize_ip(event.actor_ip) if event.actor_ip else None,
            session_id=self._anonymize_identifier(event.session_id) if event.session_id else None,
            metadata=self._anonymize_metadata(event.metadata or {})
        )
        
        return anonymized
    
    def _anonymize_identifier(self, identifier: Optional[str]) -> Optional[str]:
        """Anonymize an identifier."""
        if not identifier:
            return identifier
        
        if identifier in self._hash_cache:
            return self._hash_cache[identifier]
        
        # Hash the identifier with salt
        hash_input = f"{identifier}:{self.salt.hex()}".encode()
        hash_value = hashlib.sha256(hash_input).hexdigest()
        
        if self.level == AnonymizationLevel.HIGH:
            # Truncate hash for higher anonymization
            hash_value = hash_value[:16]
        
        self._hash_cache[identifier] = hash_value
        return hash_value
    
    def _anonymize_ip(self, ip_address: Optional[str]) -> Optional[str]:
        """Anonymize IP address."""
        if not ip_address:
            return ip_address
        
        if self.level in [AnonymizationLevel.LOW, AnonymizationLevel.MEDIUM]:
            # Zero out last octet for IPv4
            if '.' in ip_address:
                parts = ip_address.split('.')
                if len(parts) == 4:
                    return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
        
        # Full anonymization
        return self._anonymize_identifier(ip_address)
    
    def _anonymize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize metadata fields."""
        if self.level == AnonymizationLevel.NONE:
            return metadata
        
        anonymized = {}
        sensitive_keys = {
            'user_id', 'username', 'email', 'phone', 'ssn', 'key_id',
            'phase_key', 'signature', 'token', 'password', 'secret'
        }
        
        for key, value in metadata.items():
            if key.lower() in sensitive_keys:
                if isinstance(value, str):
                    anonymized[key] = self._anonymize_identifier(value)
                else:
                    anonymized[key] = "[REDACTED]"
            elif self.level == AnonymizationLevel.HIGH and isinstance(value, str) and len(value) > 50:
                # Truncate long strings in high anonymization
                anonymized[key] = value[:50] + "..."
            else:
                anonymized[key] = value
        
        return anonymized


class HashChain:
    """Implements tamper-evident hash chain for audit logs."""
    
    def __init__(self, chain_key: bytes):
        """
        Initialize hash chain.
        
        Args:
            chain_key: Secret key for hash chain
        """
        self.chain_key = chain_key
        self.previous_hash = b'\x00' * 32  # Genesis hash
    
    def add_event(self, event_data: bytes) -> str:
        """
        Add event to hash chain.
        
        Args:
            event_data: Serialized event data
            
        Returns:
            Hash value for this event
        """
        # Compute HMAC of previous hash + event data
        combined = self.previous_hash + event_data
        current_hash = hmac.new(self.chain_key, combined, hashlib.sha256).digest()
        
        # Update chain state
        self.previous_hash = current_hash
        
        return current_hash.hex()
    
    def verify_chain(self, events: List[Tuple[bytes, str]]) -> bool:
        """
        Verify integrity of event chain.
        
        Args:
            events: List of (event_data, expected_hash) tuples
            
        Returns:
            True if chain is valid
        """
        previous_hash = b'\x00' * 32
        
        for event_data, expected_hash in events:
            combined = previous_hash + event_data
            computed_hash = hmac.new(self.chain_key, combined, hashlib.sha256).digest()
            
            if computed_hash.hex() != expected_hash:
                return False
            
            previous_hash = computed_hash
        
        return True


class AuditLogger:
    """
    Main audit logger with rotation and tamper-evident logging.
    """
    
    def __init__(
        self,
        log_file: str,
        anonymizer: Optional[Anonymizer] = None,
        enable_hash_chain: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 10,
        chain_key: Optional[bytes] = None
    ):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file
            anonymizer: Anonymizer for sensitive data
            enable_hash_chain: Enable tamper-evident hash chain
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            chain_key: Key for hash chain (generated if None)
        """
        self.log_file = log_file
        self.anonymizer = anonymizer or Anonymizer(AnonymizationLevel.MEDIUM)
        self.enable_hash_chain = enable_hash_chain
        self._lock = threading.RLock()
        
        # Set up file handler with rotation
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        self.logger = logging.getLogger(f"resonagraph.audit.{id(self)}")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add rotating file handler
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Use JSON formatter
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Initialize hash chain
        self.hash_chain = None
        if enable_hash_chain:
            if chain_key is None:
                chain_key = os.urandom(32)
            self.hash_chain = HashChain(chain_key)
        
        # Track statistics
        self.stats = {
            'events_logged': 0,
            'events_anonymized': 0,
            'chain_violations': 0,
            'last_event_time': None
        }
    
    def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.
        
        Args:
            event: Audit event to log
        """
        with self._lock:
            try:
                # Anonymize event if configured
                log_event = event
                if self.anonymizer.level != AnonymizationLevel.NONE:
                    log_event = self.anonymizer.anonymize_event(event)
                    self.stats['events_anonymized'] += 1
                
                # Convert to JSON
                event_dict = log_event.to_dict()
                
                # Add hash chain if enabled
                if self.hash_chain:
                    event_data = json.dumps(event_dict, sort_keys=True).encode()
                    event_dict['chain_hash'] = self.hash_chain.add_event(event_data)
                
                # Add metadata
                event_dict['log_timestamp'] = time.time()
                event_dict['logger_id'] = id(self)
                
                # Log the event
                self.logger.info(json.dumps(event_dict, sort_keys=True))
                
                # Update statistics
                self.stats['events_logged'] += 1
                self.stats['last_event_time'] = event_dict['log_timestamp']
                
            except Exception as e:
                # Log error to standard logger
                error_logger = logging.getLogger('resonagraph.audit.error')
                error_logger.error(f"Failed to log audit event: {e}")
    
    def log_security_event(
        self,
        event_type: AuditEventType,
        resource: str,
        outcome: str,
        actor: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Convenience method for logging security events.
        
        Args:
            event_type: Type of security event
            resource: Resource being accessed
            outcome: Outcome (success, failure, error)
            actor: Actor performing the action
            metadata: Additional event metadata
        """
        event = AuditEvent(
            event_type=event_type.value,
            timestamp=time.time(),
            resource=resource,
            action="security_event",
            outcome=outcome,
            actor=actor,
            metadata=metadata or {}
        )
        self.log_event(event)
    
    def log_key_operation(
        self,
        operation: str,
        key_id: str,
        outcome: str,
        actor: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Convenience method for logging key operations.
        
        Args:
            operation: Key operation (create, rotate, revoke, access)
            key_id: Key identifier
            outcome: Outcome of operation
            actor: Actor performing operation
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type=f"key_{operation}",
            timestamp=time.time(),
            resource=key_id,
            action=f"key_{operation}",
            outcome=outcome,
            actor=actor,
            metadata=metadata or {}
        )
        self.log_event(event)
    
    def log_access_attempt(
        self,
        resource: str,
        action: str,
        outcome: str,
        actor: Optional[str] = None,
        actor_ip: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Convenience method for logging access attempts.
        
        Args:
            resource: Resource being accessed
            action: Action being performed
            outcome: Access outcome
            actor: Actor attempting access
            actor_ip: IP address of actor
            metadata: Additional metadata
        """
        event = AuditEvent(
            event_type="access_attempt",
            timestamp=time.time(),
            resource=resource,
            action=action,
            outcome=outcome,
            actor=actor,
            actor_ip=actor_ip,
            metadata=metadata or {}
        )
        self.log_event(event)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit logger statistics."""
        return self.stats.copy()
    
    def verify_log_integrity(self, start_time: Optional[float] = None, end_time: Optional[float] = None) -> bool:
        """
        Verify integrity of audit logs using hash chain.
        
        Args:
            start_time: Start time for verification (Unix timestamp)
            end_time: End time for verification (Unix timestamp)
            
        Returns:
            True if logs are tamper-free
        """
        if not self.hash_chain:
            return True  # No hash chain to verify
        
        try:
            events = []
            
            # Read log file and extract events
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        event_dict = json.loads(line.strip())
                        
                        # Filter by time range if specified
                        event_time = event_dict.get('timestamp', 0)
                        if start_time and event_time < start_time:
                            continue
                        if end_time and event_time > end_time:
                            continue
                        
                        # Extract chain hash
                        chain_hash = event_dict.pop('chain_hash', None)
                        if chain_hash:
                            event_data = json.dumps(event_dict, sort_keys=True).encode()
                            events.append((event_data, chain_hash))
                    
                    except json.JSONDecodeError:
                        continue
            
            # Verify chain
            return self.hash_chain.verify_chain(events)
        
        except Exception as e:
            logging.getLogger('resonagraph.audit.error').error(f"Failed to verify log integrity: {e}")
            return False


class AnonymizedAuditLogger:
    """
    Wrapper for audit logger with specific anonymization settings.
    """
    
    def __init__(
        self,
        base_logger: AuditLogger,
        anonymizer: Anonymizer
    ):
        """
        Initialize anonymized audit logger.
        
        Args:
            base_logger: Base audit logger
            anonymizer: Anonymizer to use
        """
        self.base_logger = base_logger
        self.anonymizer = anonymizer
    
    def log_event(self, event: AuditEvent) -> None:
        """Log event with anonymization."""
        anonymized_event = self.anonymizer.anonymize_event(event)
        self.base_logger.log_event(anonymized_event)
    
    def __getattr__(self, name):
        """Delegate other methods to base logger."""
        return getattr(self.base_logger, name)


# Factory function for easy setup
def create_audit_logger(
    log_file: str,
    anonymization_level: AnonymizationLevel = AnonymizationLevel.MEDIUM,
    **kwargs
) -> AuditLogger:
    """
    Create audit logger with specified configuration.
    
    Args:
        log_file: Path to audit log file
        anonymization_level: Level of anonymization
        **kwargs: Additional arguments for AuditLogger
        
    Returns:
        Configured audit logger
    """
    anonymizer = Anonymizer(anonymization_level)
    return AuditLogger(log_file, anonymizer=anonymizer, **kwargs)
