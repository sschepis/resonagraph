"""
Tests for audit logging and anonymization.

Tests audit event logging, hash chains, anonymization, and privacy controls
as specified in NEXT_STEPS.md 6.3.
"""

import json
import tempfile
import os
import pytest

from resonagraph.security.audit import AuditLogger, AuditEvent, AuditEventType
from resonagraph.security.anonymization import (
    Anonymizer,
    AnonymizationLevel,
    AnonymizedAuditLogger
)


class TestAuditEvent:
    """Test AuditEvent functionality."""
    
    def test_event_creation(self):
        """Test audit event creation."""
        event = AuditEvent(
            event_type=AuditEventType.LOCK_ATTEMPT,
            timestamp=123456.0,
            actor="user:alice",
            resource="vertex:123",
            action="lock",
            outcome="success"
        )
        
        assert event.event_type == AuditEventType.LOCK_ATTEMPT
        assert event.timestamp == 123456.0
        assert event.actor == "user:alice"
        assert event.resource == "vertex:123"
    
    def test_compute_hash(self):
        """Test hash computation for events."""
        event = AuditEvent(
            event_type=AuditEventType.LOCK_ATTEMPT,
            timestamp=123456.0,
            actor="user:alice",
            resource="vertex:123",
            action="lock",
            outcome="success"
        )
        
        hash1 = event.compute_hash()
        hash2 = event.compute_hash()
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex
        assert hash1 == hash2  # Deterministic
    
    def test_hash_includes_previous(self):
        """Test that hash computation includes previous hash."""
        event1 = AuditEvent(
            event_type=AuditEventType.LOCK_ATTEMPT,
            timestamp=123456.0,
            actor="user:alice",
            resource="vertex:123",
            action="lock",
            outcome="success"
        )
        
        hash1 = event1.compute_hash()
        
        event2 = AuditEvent(
            event_type=AuditEventType.LOCK_ATTEMPT,
            timestamp=123457.0,
            actor="user:alice",
            resource="vertex:124",
            action="lock",
            outcome="success",
            previous_hash=hash1
        )
        
        hash2 = event2.compute_hash()
        
        assert hash1 != hash2  # Different because of previous_hash
    
    def test_to_dict(self):
        """Test event serialization to dict."""
        event = AuditEvent(
            event_type=AuditEventType.LOCK_ATTEMPT,
            timestamp=123456.0,
            actor="user:alice",
            resource="vertex:123",
            action="lock",
            outcome="success",
            metadata={'key': 'value'}
        )
        
        data = event.to_dict()
        
        assert data['event_type'] == 'lock_attempt'
        assert data['timestamp'] == 123456.0
        assert data['actor'] == 'user:alice'
        assert data['metadata'] == {'key': 'value'}
    
    def test_to_json(self):
        """Test event serialization to JSON."""
        event = AuditEvent(
            event_type=AuditEventType.LOCK_ATTEMPT,
            timestamp=123456.0,
            actor="user:alice",
            resource="vertex:123",
            action="lock",
            outcome="success"
        )
        
        json_str = event.to_json()
        
        # Should be valid JSON
        data = json.loads(json_str)
        assert data['event_type'] == 'lock_attempt'


class TestAuditLogger:
    """Test AuditLogger functionality."""
    
    def test_initialization(self):
        """Test audit logger initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file)
            
            assert logger.enable_hash_chain
            assert logger._last_hash is None
    
    def test_log_event(self):
        """Test basic event logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file)
            
            event = logger.log_event(
                event_type=AuditEventType.LOCK_ATTEMPT,
                actor="user:alice",
                resource="vertex:123",
                action="lock",
                outcome="success"
            )
            
            assert isinstance(event, AuditEvent)
            assert event.event_type == AuditEventType.LOCK_ATTEMPT
            
            # Check file was written
            assert os.path.exists(log_file)
    
    def test_hash_chain(self):
        """Test tamper-evident hash chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file, enable_hash_chain=True)
            
            # Log three events
            event1 = logger.log_event(
                event_type=AuditEventType.LOCK_ATTEMPT,
                actor="user:alice",
                resource="vertex:123",
                action="lock",
                outcome="success"
            )
            
            event2 = logger.log_event(
                event_type=AuditEventType.KEY_GENERATED,
                actor="system",
                resource="key_123",
                action="generate",
                outcome="success"
            )
            
            event3 = logger.log_event(
                event_type=AuditEventType.ACCESS_DENIED,
                actor="user:bob",
                resource="vertex:456",
                action="read",
                outcome="denied"
            )
            
            # Verify chain
            assert event1.previous_hash is None
            assert event2.previous_hash == event1.event_hash
            assert event3.previous_hash == event2.event_hash
            assert logger.get_last_hash() == event3.event_hash
    
    def test_verify_hash_chain_valid(self):
        """Test hash chain verification with valid chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file)
            
            events = []
            for i in range(5):
                event = logger.log_event(
                    event_type=AuditEventType.LOCK_ATTEMPT,
                    actor=f"user:{i}",
                    resource=f"vertex:{i}",
                    action="lock",
                    outcome="success"
                )
                events.append(event)
            
            # Chain should be valid
            assert logger.verify_hash_chain(events)
    
    def test_verify_hash_chain_tampered(self):
        """Test hash chain verification detects tampering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file)
            
            events = []
            for i in range(5):
                event = logger.log_event(
                    event_type=AuditEventType.LOCK_ATTEMPT,
                    actor=f"user:{i}",
                    resource=f"vertex:{i}",
                    action="lock",
                    outcome="success"
                )
                events.append(event)
            
            # Tamper with middle event
            events[2].actor = "user:tampered"
            
            # Chain should be invalid
            assert not logger.verify_hash_chain(events)
    
    def test_log_lock_attempt(self):
        """Test logging lock attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file)
            
            event = logger.log_lock_attempt(
                actor="user:alice",
                key="vertex:123",
                success=True,
                convergence_metrics={'iterations': 10, 'entropy': 0.01}
            )
            
            assert event.event_type == AuditEventType.LOCK_SUCCESS
            assert event.resource == "vertex:123"
            assert event.metadata['iterations'] == 10
    
    def test_log_access_decision(self):
        """Test logging access control decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file)
            
            event = logger.log_access_decision(
                actor="role:user",
                resource="vertex:123",
                action="read",
                granted=True,
                reason="Policy matched"
            )
            
            assert event.event_type == AuditEventType.ACCESS_GRANTED
            assert event.outcome == "granted"
            assert event.metadata['reason'] == "Policy matched"
    
    def test_log_key_operation(self):
        """Test logging key operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file=log_file)
            
            event = logger.log_key_operation(
                operation="rotate",
                key_id="key_123",
                key_type="topic",
                actor="system"
            )
            
            assert event.event_type == AuditEventType.KEY_ROTATED
            assert event.resource == "key_123"
            assert event.metadata['key_type'] == "topic"


class TestAnonymizer:
    """Test Anonymizer functionality."""
    
    def test_anonymize_phase_key_none(self):
        """Test phase key anonymization with NONE level."""
        anonymizer = Anonymizer(level=AnonymizationLevel.NONE)
        
        key = b"test_key_12345678901234567890"
        anon = anonymizer.anonymize_phase_key(key)
        
        # Should show first 16 hex chars
        assert anon.startswith(key.hex()[:16])
    
    def test_anonymize_phase_key_hash(self):
        """Test phase key anonymization with hashing."""
        anonymizer = Anonymizer(level=AnonymizationLevel.MEDIUM)
        
        key = b"test_key_12345678901234567890"
        anon1 = anonymizer.anonymize_phase_key(key)
        anon2 = anonymizer.anonymize_phase_key(key)
        
        # Should be deterministic
        assert anon1 == anon2
        # Should be shortened
        assert len(anon1) == 16
    
    def test_anonymize_actor_low(self):
        """Test actor anonymization at LOW level."""
        anonymizer = Anonymizer(level=AnonymizationLevel.LOW)
        
        anon = anonymizer.anonymize_actor("user:alice@example.com")
        
        # Should keep type prefix
        assert anon.startswith("user:")
        # Should hash the rest
        assert "alice" not in anon
    
    def test_anonymize_actor_high(self):
        """Test actor anonymization at HIGH level."""
        anonymizer = Anonymizer(level=AnonymizationLevel.HIGH)
        
        anon = anonymizer.anonymize_actor("user:alice@example.com")
        
        # Should be generic
        assert anon == "user:***"
    
    def test_anonymize_resource(self):
        """Test resource anonymization."""
        anonymizer = Anonymizer(level=AnonymizationLevel.MEDIUM)
        
        anon = anonymizer.anonymize_resource("vertex:user_123")
        
        # Should keep type prefix
        assert anon.startswith("vertex:")
        # Should hash the ID
        assert "user_123" not in anon
    
    def test_anonymize_metadata_removes_secrets(self):
        """Test that metadata anonymization removes secrets."""
        anonymizer = Anonymizer(level=AnonymizationLevel.MEDIUM)
        
        metadata = {
            'password': 'secret123',
            'count': 42,
            'token': 'abc123',
            'description': 'test'
        }
        
        anon = anonymizer.anonymize_metadata(metadata)
        
        assert anon['password'] == "***REDACTED***"
        assert anon['token'] == "***REDACTED***"
        assert anon['count'] == 42  # Numeric preserved
    
    def test_anonymize_string_email(self):
        """Test email anonymization."""
        anonymizer = Anonymizer(level=AnonymizationLevel.HIGH)
        
        text = "Contact alice@example.com for info"
        anon = anonymizer._anonymize_string(text)
        
        assert "alice@example.com" not in anon
        assert "[EMAIL]" in anon
    
    def test_anonymize_string_ip(self):
        """Test IP address anonymization."""
        anonymizer = Anonymizer(level=AnonymizationLevel.HIGH)
        
        text = "Connection from 192.168.1.100"
        anon = anonymizer._anonymize_string(text)
        
        assert "192.168.1.100" not in anon
        assert "[IP]" in anon
    
    def test_mask_email_partial(self):
        """Test partial email masking."""
        anonymizer = Anonymizer(level=AnonymizationLevel.MEDIUM)
        
        masked = anonymizer._mask_email("alice@example.com")
        
        assert masked == "a***e@example.com"
    
    def test_mask_ip_partial(self):
        """Test partial IP masking."""
        anonymizer = Anonymizer(level=AnonymizationLevel.MEDIUM)
        
        masked = anonymizer._mask_ip("192.168.1.100")
        
        assert masked == "192.168.***.***"
    
    def test_create_fingerprint(self):
        """Test fingerprint creation."""
        anonymizer = Anonymizer()
        
        fp1 = anonymizer.create_fingerprint("user:alice")
        fp2 = anonymizer.create_fingerprint("user:alice")
        fp3 = anonymizer.create_fingerprint("user:bob")
        
        # Should be deterministic
        assert fp1 == fp2
        # Should be different for different data
        assert fp1 != fp3
        # Should be 16 chars (64 bits)
        assert len(fp1) == 16


class TestAnonymizedAuditLogger:
    """Test AnonymizedAuditLogger functionality."""
    
    def test_log_event_anonymizes(self):
        """Test that events are automatically anonymized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            base_logger = AuditLogger(log_file=log_file)
            anonymizer = Anonymizer(level=AnonymizationLevel.MEDIUM)
            logger = AnonymizedAuditLogger(base_logger, anonymizer)
            
            event = logger.log_event(
                event_type=AuditEventType.LOCK_ATTEMPT,
                actor="user:alice@example.com",
                resource="vertex:sensitive_data",
                action="lock",
                outcome="success",
                metadata={'password': 'secret123', 'count': 42}
            )
            
            # Actor should be anonymized
            assert "alice@example.com" not in event.actor
            assert event.actor.startswith("user:")
            
            # Resource should be anonymized
            assert "sensitive_data" not in event.resource
            assert event.resource.startswith("vertex:")
            
            # Metadata should be anonymized
            assert event.metadata['password'] == "***REDACTED***"
            assert event.metadata['count'] == 42  # Numeric preserved
