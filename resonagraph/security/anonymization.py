"""
Anonymization for privacy-preserving audit logging.

According to NEXT_STEPS.md 6.3:
- Hash phase keys for logging
- Remove PII from logs
- Configurable anonymization level
- GDPR compliance support
"""

import hashlib
import hmac
import re
from typing import Dict, Any, Optional
from enum import Enum


class AnonymizationLevel(Enum):
    """
    Levels of anonymization.
    
    NONE: No anonymization (for development/debugging)
    LOW: Hash identifiers but keep structure
    MEDIUM: Hash identifiers and remove some metadata
    HIGH: Maximum anonymization (GDPR compliant)
    """
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Anonymizer:
    """
    Anonymizes sensitive data for audit logging.
    
    According to NEXT_STEPS.md 6.3:
    - Hash phase keys for logging
    - Remove PII from logs
    - Configurable anonymization level
    """
    
    # Regex patterns for PII detection
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    PHONE_PATTERN = re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b')
    
    def __init__(
        self,
        level: AnonymizationLevel = AnonymizationLevel.MEDIUM,
        salt: Optional[bytes] = None
    ):
        """
        Initialize anonymizer.
        
        Args:
            level: Anonymization level
            salt: Optional salt for hashing (for consistency)
        """
        self.level = level
        self.salt = salt or b'resonagraph_audit_salt'
    
    def anonymize_phase_key(self, phase_key: bytes) -> str:
        """
        Anonymize a phase key by hashing.
        
        According to copilot-instructions.md:
        - Never log phase keys or raw phase values
        - Hash phase keys for logging
        
        Args:
            phase_key: Phase key bytes
            
        Returns:
            Anonymized hash (hex string)
        """
        if self.level == AnonymizationLevel.NONE:
            return phase_key.hex()[:16] + "..."
        
        # Use HMAC for consistent hashing
        h = hmac.new(self.salt, phase_key, hashlib.sha256)
        hash_hex = h.hexdigest()
        
        # Return different lengths based on level
        if self.level == AnonymizationLevel.LOW:
            return hash_hex[:32]  # 128 bits
        elif self.level == AnonymizationLevel.MEDIUM:
            return hash_hex[:16]  # 64 bits
        else:  # HIGH
            return hash_hex[:8]   # 32 bits
    
    def anonymize_actor(self, actor: str) -> str:
        """
        Anonymize actor identifier.
        
        Args:
            actor: Actor identifier (role:name, user:email, etc.)
            
        Returns:
            Anonymized actor string
        """
        if self.level == AnonymizationLevel.NONE:
            return actor
        
        # Parse actor format
        if ":" in actor:
            actor_type, actor_id = actor.split(":", 1)
            
            if self.level == AnonymizationLevel.LOW:
                # Keep type, hash ID
                hashed_id = self._hash_string(actor_id)[:8]
                return f"{actor_type}:{hashed_id}"
            elif self.level == AnonymizationLevel.MEDIUM:
                # Keep type, shorter hash
                hashed_id = self._hash_string(actor_id)[:6]
                return f"{actor_type}:{hashed_id}"
            else:  # HIGH
                # Generic identifier only
                return f"{actor_type}:***"
        
        # No type separator - hash the whole thing
        if self.level == AnonymizationLevel.LOW:
            return self._hash_string(actor)[:8]
        elif self.level == AnonymizationLevel.MEDIUM:
            return self._hash_string(actor)[:6]
        else:  # HIGH
            return "***"
    
    def anonymize_resource(self, resource: str) -> str:
        """
        Anonymize resource identifier.
        
        Args:
            resource: Resource identifier
            
        Returns:
            Anonymized resource string
        """
        if self.level == AnonymizationLevel.NONE:
            return resource
        
        # For vertex/edge keys, keep the type but hash the ID
        if ":" in resource:
            resource_type, resource_id = resource.split(":", 1)
            
            if self.level == AnonymizationLevel.LOW:
                hashed_id = self._hash_string(resource_id)[:8]
                return f"{resource_type}:{hashed_id}"
            elif self.level == AnonymizationLevel.MEDIUM:
                hashed_id = self._hash_string(resource_id)[:6]
                return f"{resource_type}:{hashed_id}"
            else:  # HIGH
                return f"{resource_type}:***"
        
        # No type separator - hash the whole thing
        if self.level == AnonymizationLevel.LOW:
            return self._hash_string(resource)[:8]
        elif self.level == AnonymizationLevel.MEDIUM:
            return self._hash_string(resource)[:6]
        else:  # HIGH
            return "***"
    
    def anonymize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize metadata dictionary.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Anonymized metadata
        """
        if self.level == AnonymizationLevel.NONE:
            return metadata
        
        anonymized = {}
        
        for key, value in metadata.items():
            # Remove high-sensitivity fields at MEDIUM and HIGH levels
            if self.level.value >= AnonymizationLevel.MEDIUM.value:
                if key in ('password', 'secret', 'token', 'key', 'private_key'):
                    anonymized[key] = "***REDACTED***"
                    continue
            
            # Anonymize based on value type
            if isinstance(value, str):
                anonymized[key] = self._anonymize_string(value)
            elif isinstance(value, bytes):
                anonymized[key] = self.anonymize_phase_key(value)
            elif isinstance(value, dict):
                anonymized[key] = self.anonymize_metadata(value)
            elif isinstance(value, list):
                anonymized[key] = [
                    self._anonymize_string(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                # Keep numeric and boolean values
                anonymized[key] = value
        
        return anonymized
    
    def _anonymize_string(self, value: str) -> str:
        """
        Anonymize a string value by removing PII.
        
        Args:
            value: String value
            
        Returns:
            Anonymized string
        """
        if self.level == AnonymizationLevel.NONE:
            return value
        
        if self.level == AnonymizationLevel.HIGH:
            # Remove all PII patterns
            value = self.EMAIL_PATTERN.sub('[EMAIL]', value)
            value = self.IP_PATTERN.sub('[IP]', value)
            value = self.PHONE_PATTERN.sub('[PHONE]', value)
        elif self.level == AnonymizationLevel.MEDIUM:
            # Partial masking
            value = self.EMAIL_PATTERN.sub(lambda m: self._mask_email(m.group(0)), value)
            value = self.IP_PATTERN.sub(lambda m: self._mask_ip(m.group(0)), value)
            value = self.PHONE_PATTERN.sub('[PHONE]', value)
        
        return value
    
    def _hash_string(self, s: str) -> str:
        """
        Hash a string consistently.
        
        Args:
            s: String to hash
            
        Returns:
            Hex hash
        """
        h = hmac.new(self.salt, s.encode('utf-8'), hashlib.sha256)
        return h.hexdigest()
    
    def _mask_email(self, email: str) -> str:
        """
        Partially mask an email address.
        
        Args:
            email: Email address
            
        Returns:
            Masked email (e.g., a***@example.com)
        """
        parts = email.split('@')
        if len(parts) != 2:
            return '[EMAIL]'
        
        local, domain = parts
        if len(local) <= 2:
            masked_local = local[0] + '***'
        else:
            masked_local = local[0] + '***' + local[-1]
        
        return f"{masked_local}@{domain}"
    
    def _mask_ip(self, ip: str) -> str:
        """
        Partially mask an IP address.
        
        Args:
            ip: IP address
            
        Returns:
            Masked IP (e.g., 192.168.***.*** )
        """
        parts = ip.split('.')
        if len(parts) != 4:
            return '[IP]'
        
        return f"{parts[0]}.{parts[1]}.***.***"
    
    def create_fingerprint(self, data: str) -> str:
        """
        Create a consistent fingerprint for data.
        
        Useful for tracking entities without revealing identity.
        
        Args:
            data: Data to fingerprint
            
        Returns:
            Fingerprint hash
        """
        h = hmac.new(self.salt, data.encode('utf-8'), hashlib.sha256)
        return h.hexdigest()[:16]  # 64-bit fingerprint


class AnonymizedAuditLogger:
    """
    Audit logger with automatic anonymization.
    
    Wraps AuditLogger to automatically anonymize sensitive data.
    """
    
    def __init__(
        self,
        audit_logger,
        anonymizer: Optional[Anonymizer] = None
    ):
        """
        Initialize anonymized audit logger.
        
        Args:
            audit_logger: AuditLogger instance
            anonymizer: Optional Anonymizer (created if not provided)
        """
        self.audit_logger = audit_logger
        self.anonymizer = anonymizer or Anonymizer()
    
    def log_event(
        self,
        event_type,
        actor: str,
        resource: str,
        action: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log an event with automatic anonymization.
        
        Args:
            event_type: Event type
            actor: Actor identifier
            resource: Resource identifier
            action: Action performed
            outcome: Outcome
            metadata: Optional metadata
            
        Returns:
            Audit event
        """
        # Anonymize inputs
        anon_actor = self.anonymizer.anonymize_actor(actor)
        anon_resource = self.anonymizer.anonymize_resource(resource)
        anon_metadata = self.anonymizer.anonymize_metadata(metadata or {})
        
        return self.audit_logger.log_event(
            event_type=event_type,
            actor=anon_actor,
            resource=anon_resource,
            action=action,
            outcome=outcome,
            metadata=anon_metadata
        )
