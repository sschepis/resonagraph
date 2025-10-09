"""
Key hierarchy management for ResonaGraph.

Implements HKDF-based key derivation, automatic rotation, and HSM integration
according to Phase 6A specifications.
"""

import hashlib
import hmac
import secrets
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum

from resonagraph.core.phase_key import PhaseKey
from resonagraph.security.hsm import HSMInterface, MockHSM
from resonagraph.security.audit import AuditLogger, AuditEvent


class KeyType(Enum):
    """Types of keys in the hierarchy."""
    ROOT = "root"
    TOPIC = "topic" 
    ROLE = "role"
    SESSION = "session"


class KeyStatus(Enum):
    """Key lifecycle status."""
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class KeyMetadata:
    """Metadata for a managed key."""
    key_id: str
    key_type: KeyType
    created_at: datetime
    expires_at: Optional[datetime]
    status: KeyStatus
    parent_key_id: Optional[str] = None
    topic: Optional[str] = None
    role: Optional[str] = None
    rotation_interval: int = 86400  # 24 hours default
    
    @property
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def needs_rotation(self) -> bool:
        """Check if key needs rotation."""
        if self.status != KeyStatus.ACTIVE:
            return False
        next_rotation = self.created_at + timedelta(seconds=self.rotation_interval)
        return datetime.utcnow() > next_rotation


class KeyHierarchy:
    """
    Manages hierarchical key derivation and rotation.
    
    Key Structure:
    - Root Key (K_root): Stored in HSM, never rotated automatically
    - Topic Keys (K_topic): Derived from root, rotated every 24h
    - Role Keys (K_role): Derived from topic, role-specific access
    - Session Keys: Short-lived keys for specific operations
    """
    
    def __init__(
        self, 
        hsm: Optional[HSMInterface] = None,
        audit_logger: Optional[AuditLogger] = None,
        auto_rotation: bool = True
    ):
        """
        Initialize key hierarchy manager.
        
        Args:
            hsm: HSM interface for root key storage (uses MockHSM if None)
            audit_logger: Audit logger for key operations
            auto_rotation: Enable automatic key rotation
        """
        self.hsm = hsm or MockHSM()
        self.audit_logger = audit_logger
        self._keys: Dict[str, KeyMetadata] = {}
        self._derived_keys: Dict[str, PhaseKey] = {}
        self._rotation_lock = threading.RLock()
        self._rotation_scheduler: Optional[KeyRotationScheduler] = None
        
        if auto_rotation:
            self._rotation_scheduler = KeyRotationScheduler(self)
            self._rotation_scheduler.start()
    
    def create_root_key(self, key_id: str = "root") -> str:
        """
        Create or retrieve root key from HSM.
        
        Args:
            key_id: Identifier for the root key
            
        Returns:
            Key ID of the created/retrieved root key
        """
        # Check if root key already exists
        if self.hsm.key_exists(key_id):
            self._log_audit_event("root_key_retrieved", key_id)
            metadata = KeyMetadata(
                key_id=key_id,
                key_type=KeyType.ROOT,
                created_at=datetime.utcnow(),
                expires_at=None,  # Root keys don't expire
                status=KeyStatus.ACTIVE
            )
            self._keys[key_id] = metadata
            return key_id
        
        # Generate new root key
        root_key_bytes = secrets.token_bytes(32)
        self.hsm.store_key(key_id, root_key_bytes)
        
        metadata = KeyMetadata(
            key_id=key_id,
            key_type=KeyType.ROOT,
            created_at=datetime.utcnow(),
            expires_at=None,
            status=KeyStatus.ACTIVE
        )
        self._keys[key_id] = metadata
        
        self._log_audit_event("root_key_created", key_id)
        return key_id
    
    def derive_topic_key(
        self,
        topic: str,
        root_key_id: str = "root",
        rotation_interval: int = 86400
    ) -> PhaseKey:
        """
        Derive a topic-specific key from root key.
        
        Args:
            topic: Topic name for key derivation
            root_key_id: Root key to derive from
            rotation_interval: Rotation interval in seconds
            
        Returns:
            Derived PhaseKey for the topic
        """
        with self._rotation_lock:
            # Check if we have a current active topic key
            topic_key_id = f"{root_key_id}:topic:{topic}"
            
            if topic_key_id in self._keys:
                metadata = self._keys[topic_key_id]
                if metadata.status == KeyStatus.ACTIVE and not metadata.needs_rotation:
                    # Return cached key
                    if topic_key_id in self._derived_keys:
                        return self._derived_keys[topic_key_id]
            
            # Derive new topic key
            root_key_bytes = self.hsm.get_key(root_key_id)
            if root_key_bytes is None:
                raise ValueError(f"Root key {root_key_id} not found")
            
            root_key = PhaseKey(root_key_bytes)
            topic_key = PhaseKey.derive_topic_key(root_key, topic)
            
            # Store metadata
            metadata = KeyMetadata(
                key_id=topic_key_id,
                key_type=KeyType.TOPIC,
                created_at=datetime.utcnow(),
                expires_at=None,
                status=KeyStatus.ACTIVE,
                parent_key_id=root_key_id,
                topic=topic,
                rotation_interval=rotation_interval
            )
            self._keys[topic_key_id] = metadata
            self._derived_keys[topic_key_id] = topic_key
            
            self._log_audit_event("topic_key_derived", topic_key_id, {"topic": topic})
            return topic_key
    
    def derive_role_key(
        self,
        role: str,
        topic: str,
        root_key_id: str = "root"
    ) -> PhaseKey:
        """
        Derive a role-specific key from topic key.
        
        Args:
            role: Role name (e.g., "admin", "user", "readonly")
            topic: Topic name
            root_key_id: Root key identifier
            
        Returns:
            Derived PhaseKey for the role
        """
        # First get the topic key
        topic_key = self.derive_topic_key(topic, root_key_id)
        
        # Derive role key using HKDF with role as context
        role_key_id = f"{root_key_id}:role:{topic}:{role}"
        
        if role_key_id in self._derived_keys:
            return self._derived_keys[role_key_id]
        
        # HKDF for role derivation
        salt = hashlib.sha256(f"role:{role}".encode()).digest()[:16]
        prk = hmac.new(salt, topic_key.get_bytes(), hashlib.sha256).digest()
        info = f"role:{role}:topic:{topic}".encode()
        okm = hmac.new(prk, info + b'\x01', hashlib.sha256).digest()
        
        role_key = PhaseKey(okm)
        
        # Store metadata
        metadata = KeyMetadata(
            key_id=role_key_id,
            key_type=KeyType.ROLE,
            created_at=datetime.utcnow(),
            expires_at=None,
            status=KeyStatus.ACTIVE,
            parent_key_id=f"{root_key_id}:topic:{topic}",
            topic=topic,
            role=role
        )
        self._keys[role_key_id] = metadata
        self._derived_keys[role_key_id] = role_key
        
        self._log_audit_event("role_key_derived", role_key_id, {
            "role": role, 
            "topic": topic
        })
        return role_key
    
    def rotate_key(self, key_id: str, retain_old: bool = True) -> PhaseKey:
        """
        Rotate a specific key.
        
        Args:
            key_id: Key to rotate
            retain_old: Keep old key for grace period
            
        Returns:
            New rotated key
        """
        with self._rotation_lock:
            if key_id not in self._keys:
                raise ValueError(f"Key {key_id} not found")
            
            old_metadata = self._keys[key_id]
            
            if old_metadata.key_type == KeyType.ROOT:
                raise ValueError("Root keys cannot be automatically rotated")
            
            # Mark old key as rotated
            if retain_old:
                old_metadata.status = KeyStatus.ROTATED
                old_metadata.expires_at = datetime.utcnow() + timedelta(hours=1)
            else:
                old_metadata.status = KeyStatus.REVOKED
                if key_id in self._derived_keys:
                    del self._derived_keys[key_id]
            
            # Create new key
            if old_metadata.key_type == KeyType.TOPIC:
                new_key = self.derive_topic_key(
                    old_metadata.topic,
                    old_metadata.parent_key_id,
                    old_metadata.rotation_interval
                )
            elif old_metadata.key_type == KeyType.ROLE:
                new_key = self.derive_role_key(
                    old_metadata.role,
                    old_metadata.topic,
                    old_metadata.parent_key_id.split(':')[0]  # Extract root key ID
                )
            else:
                raise ValueError(f"Cannot rotate key type {old_metadata.key_type}")
            
            self._log_audit_event("key_rotated", key_id, {
                "old_status": old_metadata.status.value,
                "retain_old": retain_old
            })
            
            return new_key
    
    def revoke_key(self, key_id: str) -> None:
        """
        Revoke a key immediately.
        
        Args:
            key_id: Key to revoke
        """
        with self._rotation_lock:
            if key_id not in self._keys:
                raise ValueError(f"Key {key_id} not found")
            
            metadata = self._keys[key_id]
            metadata.status = KeyStatus.REVOKED
            
            # Remove from derived keys cache
            if key_id in self._derived_keys:
                del self._derived_keys[key_id]
            
            self._log_audit_event("key_revoked", key_id)
    
    def cleanup_expired_keys(self) -> int:
        """
        Clean up expired keys.
        
        Returns:
            Number of keys cleaned up
        """
        cleanup_count = 0
        expired_keys = []
        
        with self._rotation_lock:
            for key_id, metadata in self._keys.items():
                if metadata.is_expired or metadata.status == KeyStatus.REVOKED:
                    expired_keys.append(key_id)
            
            for key_id in expired_keys:
                if key_id in self._derived_keys:
                    del self._derived_keys[key_id]
                # Keep metadata for audit purposes
                cleanup_count += 1
        
        if cleanup_count > 0:
            self._log_audit_event("keys_cleaned_up", "system", {
                "cleanup_count": cleanup_count
            })
        
        return cleanup_count
    
    def get_key_metadata(self, key_id: str) -> Optional[KeyMetadata]:
        """Get metadata for a key."""
        return self._keys.get(key_id)
    
    def list_keys(self, key_type: Optional[KeyType] = None, status: Optional[KeyStatus] = None) -> Dict[str, KeyMetadata]:
        """
        List keys with optional filtering.
        
        Args:
            key_type: Filter by key type
            status: Filter by key status
            
        Returns:
            Dict of key_id -> metadata
        """
        result = {}
        for key_id, metadata in self._keys.items():
            if key_type and metadata.key_type != key_type:
                continue
            if status and metadata.status != status:
                continue
            result[key_id] = metadata
        return result
    
    def _log_audit_event(self, event_type: str, key_id: str, metadata: Optional[Dict] = None) -> None:
        """Log audit event if logger is available."""
        if self.audit_logger:
            event = AuditEvent(
                event_type=event_type,
                resource=key_id,
                action="key_operation",
                outcome="success",
                metadata=metadata or {}
            )
            self.audit_logger.log_event(event)
    
    def shutdown(self) -> None:
        """Shutdown the key hierarchy manager."""
        if self._rotation_scheduler:
            self._rotation_scheduler.stop()


class KeyRotationScheduler:
    """
    Automatic key rotation scheduler.
    
    Runs in background thread and rotates keys based on their rotation intervals.
    """
    
    def __init__(self, key_hierarchy: KeyHierarchy, check_interval: int = 300):
        """
        Initialize rotation scheduler.
        
        Args:
            key_hierarchy: Key hierarchy to manage
            check_interval: How often to check for rotations (seconds)
        """
        self.key_hierarchy = key_hierarchy
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self) -> None:
        """Start the rotation scheduler."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._rotation_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the rotation scheduler."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join()
    
    def _rotation_loop(self) -> None:
        """Main rotation loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self._check_and_rotate_keys()
                self.key_hierarchy.cleanup_expired_keys()
            except Exception as e:
                # Log error but continue running
                if self.key_hierarchy.audit_logger:
                    event = AuditEvent(
                        event_type="rotation_error",
                        resource="scheduler",
                        action="auto_rotation",
                        outcome="error",
                        metadata={"error": str(e)}
                    )
                    self.key_hierarchy.audit_logger.log_event(event)
            
            # Wait for next check or stop signal
            self._stop_event.wait(self.check_interval)
    
    def _check_and_rotate_keys(self) -> None:
        """Check keys and rotate those that need rotation."""
        keys_to_rotate = []
        
        # Find keys that need rotation
        for key_id, metadata in self.key_hierarchy.list_keys().items():
            if metadata.needs_rotation and metadata.key_type != KeyType.ROOT:
                keys_to_rotate.append(key_id)
        
        # Rotate each key
        for key_id in keys_to_rotate:
            try:
                self.key_hierarchy.rotate_key(key_id, retain_old=True)
            except Exception as e:
                if self.key_hierarchy.audit_logger:
                    event = AuditEvent(
                        event_type="rotation_failed",
                        resource=key_id,
                        action="auto_rotation",
                        outcome="error",
                        metadata={"error": str(e)}
                    )
                    self.key_hierarchy.audit_logger.log_event(event)
