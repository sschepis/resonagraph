"""
Key hierarchy and rotation for ResonaGraph.

According to copilot-instructions.md Section 5 and NEXT_STEPS.md 6.1:
- Root K_root derives per-topic K_topic via HKDF
- Automatic 24-hour rotation schedule
- Key version tracking in beacons
- HSM integration ready for production
"""

import hashlib
import hmac
import secrets
import time
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading

from ..core.phase_key import PhaseKey


@dataclass
class KeyVersion:
    """
    Represents a versioned key with metadata.
    
    Attributes:
        key: The phase key
        version: Key version number
        created_at: Timestamp when key was created
        expires_at: Timestamp when key expires
        purpose: Key purpose/context
    """
    key: PhaseKey
    version: int
    created_at: float
    expires_at: float
    purpose: str


class KeyHierarchy:
    """
    Manages hierarchical key derivation using HKDF.
    
    According to design.md Section 6.1:
    - K_root derives per-topic K_topic via HKDF
    - Domain separation for different key types
    - Key context information (purpose, timestamp, version)
    
    This implements RFC 5869 HKDF with SHA-256.
    """
    
    def __init__(self, root_key: Optional[PhaseKey] = None):
        """
        Initialize key hierarchy.
        
        Args:
            root_key: Root key for derivation (generated if not provided)
        """
        self._root_key = root_key or PhaseKey.generate()
        self._derived_keys: Dict[str, KeyVersion] = {}
        self._lock = threading.Lock()
    
    def derive_key(
        self,
        context: str,
        purpose: str = "default",
        version: int = 1,
        salt: Optional[bytes] = None
    ) -> PhaseKey:
        """
        Derive a key from the root key using HKDF.
        
        According to RFC 5869:
        - HKDF-Extract: PRK = HMAC-Hash(salt, IKM)
        - HKDF-Expand: OKM = HMAC-Hash(PRK, info || counter)
        
        Args:
            context: Context for key derivation (e.g., topic name)
            purpose: Key purpose (default, signing, encryption, etc.)
            version: Key version number
            salt: Optional salt (random if not provided)
            
        Returns:
            Derived phase key
        """
        if salt is None:
            salt = secrets.token_bytes(32)
        
        # HKDF Extract: PRK = HMAC-Hash(salt, IKM)
        prk = hmac.new(salt, self._root_key.get_bytes(), hashlib.sha256).digest()
        
        # Build info string with domain separation
        # Format: context||purpose||version
        info = f"{context}||{purpose}||{version}".encode('utf-8')
        
        # HKDF Expand: OKM = HMAC-Hash(PRK, info || 0x01)
        # For 256-bit keys, we only need one iteration
        okm = hmac.new(prk, info + b'\x01', hashlib.sha256).digest()
        
        return PhaseKey(okm)
    
    def derive_topic_key(
        self,
        topic: str,
        version: int = 1,
        ttl_seconds: float = 86400  # 24 hours default
    ) -> KeyVersion:
        """
        Derive a per-topic key with version tracking.
        
        According to copilot-instructions.md:
        - Root K_root derives per-topic K_topic via HKDF
        - Keys expire after 24 hours (configurable)
        
        Args:
            topic: Topic identifier
            version: Key version
            ttl_seconds: Time-to-live in seconds (default 24h)
            
        Returns:
            KeyVersion with metadata
        """
        with self._lock:
            cache_key = f"{topic}::{version}"
            
            # Check cache
            if cache_key in self._derived_keys:
                key_version = self._derived_keys[cache_key]
                # Return cached key if not expired
                if time.time() < key_version.expires_at:
                    return key_version
            
            # Derive new key
            key = self.derive_key(topic, purpose="topic", version=version)
            
            now = time.time()
            key_version = KeyVersion(
                key=key,
                version=version,
                created_at=now,
                expires_at=now + ttl_seconds,
                purpose=f"topic:{topic}"
            )
            
            # Cache the key
            self._derived_keys[cache_key] = key_version
            
            return key_version
    
    def derive_role_key(
        self,
        role: str,
        resource: str,
        version: int = 1
    ) -> PhaseKey:
        """
        Derive a role-based access key.
        
        According to NEXT_STEPS.md 6.1:
        - Role-based key derivation (admin, user, read-only)
        - Hierarchical access (parent keys unlock child data)
        
        Args:
            role: Role identifier (admin, user, read-only, etc.)
            resource: Resource identifier
            version: Key version
            
        Returns:
            Derived phase key for role
        """
        context = f"{role}::{resource}"
        return self.derive_key(context, purpose="role", version=version)
    
    def get_root_key(self) -> PhaseKey:
        """
        Get the root key (for backup/restore purposes).
        
        WARNING: Root key should be protected with HSM in production.
        
        Returns:
            Root phase key
        """
        return self._root_key
    
    def rotate_root_key(self, new_root_key: PhaseKey) -> None:
        """
        Rotate the root key.
        
        This invalidates all derived keys and requires re-derivation.
        Use with caution - typically done during security incidents.
        
        Args:
            new_root_key: New root key
        """
        with self._lock:
            self._root_key = new_root_key
            # Clear derived key cache
            self._derived_keys.clear()


class KeyRotationScheduler:
    """
    Manages automatic key rotation on a schedule.
    
    According to copilot-instructions.md:
    - Rotate keys every 24h for security
    - Graceful key transition (overlap period)
    - Key version tracking in beacons
    """
    
    def __init__(
        self,
        key_hierarchy: KeyHierarchy,
        rotation_interval: float = 86400,  # 24 hours
        overlap_period: float = 3600  # 1 hour overlap
    ):
        """
        Initialize key rotation scheduler.
        
        Args:
            key_hierarchy: KeyHierarchy instance to manage
            rotation_interval: Rotation interval in seconds (default 24h)
            overlap_period: Grace period where old and new keys both valid
        """
        self.key_hierarchy = key_hierarchy
        self.rotation_interval = rotation_interval
        self.overlap_period = overlap_period
        self._active_versions: Dict[str, int] = {}
        self._key_creation_times: Dict[str, float] = {}  # Track when keys were created
        self._lock = threading.Lock()
    
    def get_current_version(self, topic: str) -> int:
        """
        Get the current active version for a topic.
        
        Args:
            topic: Topic identifier
            
        Returns:
            Current version number
        """
        with self._lock:
            return self._active_versions.get(topic, 1)
    
    def get_active_keys(self, topic: str) -> Tuple[KeyVersion, Optional[KeyVersion]]:
        """
        Get active keys for a topic (current and previous if in overlap).
        
        During the overlap period, both current and previous keys are valid
        to allow graceful transition.
        
        Args:
            topic: Topic identifier
            
        Returns:
            Tuple of (current_key, previous_key or None)
        """
        with self._lock:
            current_version = self._active_versions.get(topic, 1)
            
            # Check if we need to initialize
            cache_key = f"{topic}::{current_version}"
            if cache_key not in self._key_creation_times:
                # First time accessing this topic/version
                current_key = self.key_hierarchy.derive_topic_key(
                    topic, 
                    version=current_version,
                    ttl_seconds=self.rotation_interval + self.overlap_period
                )
                self._key_creation_times[cache_key] = current_key.created_at
                self._active_versions[topic] = current_version
            else:
                # Use cached creation time
                current_key = self.key_hierarchy.derive_topic_key(
                    topic, 
                    version=current_version,
                    ttl_seconds=self.rotation_interval + self.overlap_period
                )
            
            # Check if we're in overlap period
            now = time.time()
            creation_time = self._key_creation_times[cache_key]
            time_since_creation = now - creation_time
            
            previous_key = None
            if time_since_creation < self.overlap_period and current_version > 1:
                # We're in overlap period, also return previous key
                previous_key = self.key_hierarchy.derive_topic_key(
                    topic,
                    version=current_version - 1,
                    ttl_seconds=self.rotation_interval + self.overlap_period
                )
            
            return current_key, previous_key
    
    def should_rotate(self, topic: str) -> bool:
        """
        Check if a topic's key should be rotated.
        
        Args:
            topic: Topic identifier
            
        Returns:
            True if rotation is needed
        """
        with self._lock:
            current_version = self._active_versions.get(topic, 1)
            cache_key = f"{topic}::{current_version}"
            
            # If we haven't created this key yet, no rotation needed
            if cache_key not in self._key_creation_times:
                return False
            
            # Check time since creation
            now = time.time()
            time_since_creation = now - self._key_creation_times[cache_key]
            
            return time_since_creation >= self.rotation_interval
    
    def rotate_key(self, topic: str) -> KeyVersion:
        """
        Rotate a topic's key to the next version.
        
        Args:
            topic: Topic identifier
            
        Returns:
            New key version
        """
        with self._lock:
            current_version = self._active_versions.get(topic, 1)
            new_version = current_version + 1
            self._active_versions[topic] = new_version
            
            new_key = self.key_hierarchy.derive_topic_key(
                topic,
                version=new_version,
                ttl_seconds=self.rotation_interval + self.overlap_period
            )
            
            # Track creation time for new version
            cache_key = f"{topic}::{new_version}"
            self._key_creation_times[cache_key] = new_key.created_at
            
            return new_key
    
    def auto_rotate_if_needed(self, topic: str) -> Optional[KeyVersion]:
        """
        Automatically rotate key if needed.
        
        Args:
            topic: Topic identifier
            
        Returns:
            New key version if rotated, None otherwise
        """
        if self.should_rotate(topic):
            return self.rotate_key(topic)
        return None
