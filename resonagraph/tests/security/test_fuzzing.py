"""
Security test suite for ResonaGraph.

Tests security hardening, fuzzing, and security regressions
as specified in NEXT_STEPS.md 6.4.
"""

import os
import random
import pytest

from resonagraph.security.hardening import SecurityHardening, InputValidator
from resonagraph.security.signatures import SignatureKeyManager
from resonagraph.security.integrity import PhaseMAC, ReplayDetector


class TestSecurityHardening:
    """Test security hardening utilities."""
    
    def test_constant_time_compare_equal(self):
        """Test constant-time comparison with equal values."""
        a = b"test_data_12345678"
        b = b"test_data_12345678"
        
        assert SecurityHardening.constant_time_compare(a, b)
    
    def test_constant_time_compare_different(self):
        """Test constant-time comparison with different values."""
        a = b"test_data_12345678"
        b = b"different_data_123"
        
        assert not SecurityHardening.constant_time_compare(a, b)
    
    def test_constant_time_compare_different_lengths(self):
        """Test constant-time comparison with different lengths."""
        a = b"short"
        b = b"much_longer_string"
        
        assert not SecurityHardening.constant_time_compare(a, b)
    
    def test_secure_random_bytes(self):
        """Test secure random byte generation."""
        random1 = SecurityHardening.secure_random_bytes(32)
        random2 = SecurityHardening.secure_random_bytes(32)
        
        assert len(random1) == 32
        assert len(random2) == 32
        assert random1 != random2  # Should be different
    
    def test_secure_random_int(self):
        """Test secure random integer generation."""
        for _ in range(100):
            val = SecurityHardening.secure_random_int(1, 10)
            assert 1 <= val <= 10
    
    def test_validate_key_size_valid(self):
        """Test key size validation with valid key."""
        key = b"a" * 32
        SecurityHardening.validate_key_size(key, 32)  # Should not raise
    
    def test_validate_key_size_invalid(self):
        """Test key size validation with invalid key."""
        key = b"a" * 16
        
        with pytest.raises(ValueError, match="Invalid key size"):
            SecurityHardening.validate_key_size(key, 32)
    
    def test_validate_signature_size_valid(self):
        """Test signature size validation with valid signature."""
        signature = b"a" * 64
        SecurityHardening.validate_signature_size(signature)  # Should not raise
    
    def test_validate_signature_size_invalid(self):
        """Test signature size validation with invalid signature."""
        signature = b"a" * 32
        
        with pytest.raises(ValueError, match="Invalid signature size"):
            SecurityHardening.validate_signature_size(signature)
    
    def test_sanitize_error_message(self):
        """Test error message sanitization."""
        internal = "Database error: user alice not found in table users"
        safe = SecurityHardening.sanitize_error_message(internal)
        
        assert safe == "Operation failed"
        assert "alice" not in safe
    
    def test_recommend_security_settings(self):
        """Test security settings recommendations."""
        settings = SecurityHardening.recommend_security_settings()
        
        assert settings['use_hsm'] is True
        assert settings['key_rotation_interval'] == 86400
        assert settings['audit_anonymization_level'] == 'HIGH'


class TestInputValidator:
    """Test input validation utilities."""
    
    def test_validate_key_format_valid(self):
        """Test key format validation with valid key."""
        InputValidator.validate_key_format("vertex:user_123")  # Should not raise
    
    def test_validate_key_format_empty(self):
        """Test key format validation with empty key."""
        with pytest.raises(ValueError, match="cannot be empty"):
            InputValidator.validate_key_format("")
    
    def test_validate_key_format_too_long(self):
        """Test key format validation with too long key."""
        long_key = "a" * 2000
        
        with pytest.raises(ValueError, match="too long"):
            InputValidator.validate_key_format(long_key)
    
    def test_validate_key_format_control_chars(self):
        """Test key format validation rejects control characters."""
        invalid_key = "test\x00key"
        
        with pytest.raises(ValueError, match="control characters"):
            InputValidator.validate_key_format(invalid_key)
    
    def test_validate_epoch_valid(self):
        """Test epoch validation with valid epoch."""
        InputValidator.validate_epoch(95, 100, window=10)  # Should not raise
    
    def test_validate_epoch_too_old(self):
        """Test epoch validation rejects too old epoch."""
        with pytest.raises(ValueError, match="too old"):
            InputValidator.validate_epoch(80, 100, window=10)
    
    def test_validate_epoch_too_future(self):
        """Test epoch validation rejects far future epoch."""
        with pytest.raises(ValueError, match="too far in future"):
            InputValidator.validate_epoch(105, 100)
    
    def test_validate_epoch_negative(self):
        """Test epoch validation rejects negative epoch."""
        with pytest.raises(ValueError, match="cannot be negative"):
            InputValidator.validate_epoch(-5, 100)
    
    def test_validate_nonce_valid(self):
        """Test nonce validation with valid nonce."""
        nonce = b"valid_nonce_12345678"
        InputValidator.validate_nonce(nonce)  # Should not raise
    
    def test_validate_nonce_empty(self):
        """Test nonce validation rejects empty nonce."""
        with pytest.raises(ValueError, match="cannot be empty"):
            InputValidator.validate_nonce(b"")
    
    def test_validate_nonce_too_short(self):
        """Test nonce validation rejects too short nonce."""
        with pytest.raises(ValueError, match="too short"):
            InputValidator.validate_nonce(b"short")
    
    def test_validate_nonce_too_long(self):
        """Test nonce validation rejects too long nonce."""
        long_nonce = b"a" * 300
        with pytest.raises(ValueError, match="too long"):
            InputValidator.validate_nonce(long_nonce)
    
    def test_sanitize_resource_identifier(self):
        """Test resource identifier sanitization."""
        dangerous = "vertex:user_123'; DROP TABLE users--"
        safe = InputValidator.sanitize_resource_identifier(dangerous)
        
        # Dangerous SQL characters should be removed
        assert ";" not in safe
        assert "'" not in safe
        assert "--" not in safe
        # Valid characters should remain
        assert "vertex:" in safe
        assert "user_123" in safe


class TestSecurityFuzzing:
    """Fuzzing tests for security-critical components."""
    
    def test_fuzz_signature_verification(self):
        """Fuzz signature verification with random inputs."""
        manager = SignatureKeyManager("test_node")
        
        # Test with many random inputs
        for _ in range(100):
            # Random message and signature
            message_len = random.randint(0, 1000)
            message = os.urandom(message_len)
            signature = os.urandom(64)
            
            # Should not crash, should return False for invalid
            try:
                result = manager.verify_signature(message, signature)
                assert result is False  # Random signature should not verify
            except Exception as e:
                # Certain exceptions are acceptable (e.g., invalid format)
                assert isinstance(e, (ValueError, TypeError))
    
    def test_fuzz_mac_verification(self):
        """Fuzz MAC verification with random inputs."""
        key = b"test_key_32_bytes_long_000000"
        
        for _ in range(100):
            # Random chunk data
            chunk_len = random.randint(0, 1000)
            chunk_data = os.urandom(chunk_len)
            chunk_index = random.randint(0, 100)
            prime = random.randint(2, 1000)
            mac = os.urandom(32)
            
            # Should not crash
            try:
                PhaseMAC.verify_chunk_mac(chunk_data, chunk_index, prime, mac, key)
            except Exception:
                pytest.fail("MAC verification crashed on random input")
    
    def test_fuzz_replay_detector(self):
        """Fuzz replay detector with random inputs."""
        detector = ReplayDetector()
        
        for _ in range(100):
            # Random parameters
            key = f"key_{random.randint(0, 100)}"
            epoch = random.randint(-10, 200)
            current_epoch = 100
            nonce = os.urandom(random.randint(0, 100))
            
            # Should not crash
            try:
                detector.validate_beacon(key, epoch, current_epoch, nonce)
            except Exception:
                pytest.fail("Replay detector crashed on random input")
    
    def test_fuzz_input_validator(self):
        """Fuzz input validator with malformed inputs."""
        test_cases = [
            "",
            "\x00\x01\x02",
            "a" * 10000,
            "normal_key",
            "key:with:many:colons",
            "key\nwith\nnewlines",
            "key\twith\ttabs",
            "key with spaces",
            "key_with_😀_emoji",
        ]
        
        for test_input in test_cases:
            # Should either accept or raise ValueError, not crash
            try:
                InputValidator.validate_key_format(test_input)
            except ValueError:
                pass  # Expected for some inputs
            except Exception as e:
                pytest.fail(f"Unexpected exception: {e}")


class TestSecurityRegression:
    """Regression tests for known security issues."""
    
    def test_timing_attack_resistance(self):
        """Test that key comparison is timing-resistant."""
        import time
        
        key1 = b"a" * 32
        key2 = b"a" * 31 + b"b"  # Different only in last byte
        key3 = b"b" + b"a" * 31  # Different in first byte
        
        # Measure comparison times
        iterations = 1000
        
        start = time.perf_counter()
        for _ in range(iterations):
            SecurityHardening.constant_time_compare(key1, key2)
        time_last_diff = time.perf_counter() - start
        
        start = time.perf_counter()
        for _ in range(iterations):
            SecurityHardening.constant_time_compare(key1, key3)
        time_first_diff = time.perf_counter() - start
        
        # Times should be similar (within 50% of each other)
        # This is a weak test but catches obvious timing leaks
        ratio = max(time_last_diff, time_first_diff) / min(time_last_diff, time_first_diff)
        assert ratio < 1.5, "Potential timing attack vulnerability"
    
    def test_key_not_logged(self):
        """Test that keys are not exposed in string representations."""
        from resonagraph.core.phase_key import PhaseKey
        
        key = PhaseKey.generate()
        key_repr = repr(key)
        key_str = str(key)
        
        # Should not contain actual key bytes
        assert "***hidden***" in key_repr
        assert len(key.get_bytes()) == 32
        # Make sure actual key bytes aren't in the representation
        key_hex = key.get_bytes().hex()
        assert key_hex not in key_repr
    
    def test_signature_verification_constant_time(self):
        """Test that signature verification doesn't leak info via timing."""
        manager = SignatureKeyManager("node1")
        
        message = b"test message"
        signing_key = manager.get_signing_key()
        valid_signature = signing_key.sign(message)
        
        # Invalid signature (all zeros)
        invalid_signature1 = b'\x00' * 64
        
        # Invalid signature (random)
        invalid_signature2 = os.urandom(64)
        
        import time
        iterations = 100
        
        # Time invalid signatures
        start = time.perf_counter()
        for _ in range(iterations):
            manager.verify_signature(message, invalid_signature1)
        time_zeros = time.perf_counter() - start
        
        start = time.perf_counter()
        for _ in range(iterations):
            manager.verify_signature(message, invalid_signature2)
        time_random = time.perf_counter() - start
        
        # Times should be similar
        ratio = max(time_zeros, time_random) / min(time_zeros, time_random)
        assert ratio < 2.0, "Potential timing leak in signature verification"
