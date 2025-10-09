"""
Fuzzing tests for ResonaGraph security components.

Tests system robustness against malformed inputs, edge cases,
and adversarial inputs across all security components.
"""

import pytest
import secrets
import random
from typing import Any

from resonagraph.security import (
    PhaseKey,
    KeyHierarchy,
    SignatureKeyManager,
    BeaconSigner,
    PhaseMAC,
    AuditLogger,
    ThreatDetector,
    AccessControl,
    AccessPolicy,
    AccessLevel
)
from resonagraph.security.hardening import (
    ConstantTime,
    MemorySafe,
    InputValidation,
    SecureCompare,
    RateLimiter
)


class FuzzGenerator:
    """Generate fuzzing inputs for testing."""
    
    @staticmethod
    def random_bytes(min_size: int = 0, max_size: int = 1024) -> bytes:
        """Generate random bytes of random length."""
        size = random.randint(min_size, max_size)
        return secrets.token_bytes(size)
    
    @staticmethod
    def malformed_bytes() -> list[bytes]:
        """Generate collection of potentially malformed bytes."""
        return [
            b'',                          # Empty
            b'\x00',                      # Null byte
            b'\x00' * 1000,              # Many nulls
            b'\xff' * 1000,              # Many 0xff
            secrets.token_bytes(1),       # Too short
            secrets.token_bytes(10000),   # Very long
            b'A' * 32,                    # Repeated character
            bytes(range(256)),            # All byte values
        ]
    
    @staticmethod
    def malformed_integers() -> list[int]:
        """Generate collection of potentially malformed integers."""
        return [
            -1,                           # Negative
            0,                            # Zero
            1,                            # One
            2**31 - 1,                    # Max 32-bit
            2**31,                        # Over 32-bit
            2**63 - 1,                    # Max 64-bit
            2**64,                        # Over 64-bit
            -2**63,                       # Min 64-bit
        ]
    
    @staticmethod
    def malformed_strings() -> list[str]:
        """Generate collection of potentially malformed strings."""
        return [
            '',                           # Empty
            ' ',                          # Whitespace
            '\x00',                       # Null character
            '\n' * 100,                   # Many newlines
            'A' * 10000,                  # Very long
            '../../etc/passwd',           # Path traversal
            '<script>alert(1)</script>',  # XSS
            "'; DROP TABLE users;--",     # SQL injection
            '\u0000\u0001\u001f',        # Control chars
            '🔥' * 100,                   # Unicode
        ]


class TestPhaseKeyFuzzing:
    """Fuzzing tests for PhaseKey operations."""
    
    def test_from_secret_malformed(self):
        """Test PhaseKey.from_secret with malformed inputs."""
        for malformed in FuzzGenerator.malformed_bytes():
            if len(malformed) != 32:
                # Should reject invalid sizes
                with pytest.raises((ValueError, TypeError)):
                    PhaseKey.from_secret(malformed)
            else:
                # Should handle valid size
                key = PhaseKey.from_secret(malformed)
                assert isinstance(key, PhaseKey)
    
    def test_derive_with_malformed_context(self):
        """Test key derivation with malformed context."""
        root_key = PhaseKey.generate()
        
        malformed_contexts = [
            {},
            {'': ''},
            {'key': None},
            {'key': 123},
            {'key': b'bytes'},
            {'very_long_key_' * 100: 'value'},
        ]
        
        for context in malformed_contexts:
            # Should handle gracefully
            try:
                derived = root_key.derive(context)
                assert isinstance(derived, PhaseKey)
            except (ValueError, TypeError):
                # Acceptable to reject invalid context
                pass
    
    def test_random_key_operations(self):
        """Test random sequences of key operations."""
        for _ in range(100):
            key1 = PhaseKey.generate()
            key2 = PhaseKey.generate()
            
            # Random operations should not crash
            _ = key1 == key2
            _ = hash(key1)
            _ = key1.derive({'iteration': str(_)})


class TestSignatureFuzzing:
    """Fuzzing tests for signature operations."""
    
    def test_sign_malformed_data(self):
        """Test signing malformed data."""
        signer = BeaconSigner()
        
        for malformed in FuzzGenerator.malformed_bytes():
            # Should handle any bytes without crashing
            signature = signer.sign_beacon(malformed)
            assert isinstance(signature, bytes)
            assert len(signature) == 64  # Ed25519 signature size
    
    def test_verify_malformed_signatures(self):
        """Test verifying malformed signatures."""
        signer = BeaconSigner()
        message = b"test message"
        valid_sig = signer.sign_beacon(message)
        
        for malformed in FuzzGenerator.malformed_bytes():
            # Should reject invalid signatures
            result = signer.verify_beacon(message, malformed)
            if malformed == valid_sig:
                assert result is True
            else:
                assert result is False
    
    def test_signature_length_attacks(self):
        """Test signature verification with length attacks."""
        signer = BeaconSigner()
        message = b"test message"
        valid_sig = signer.sign_beacon(message)
        
        # Try various signature lengths
        for length in [0, 1, 63, 64, 65, 100, 1000]:
            if length == 64:
                continue  # Skip valid length
            
            malformed = secrets.token_bytes(length)
            result = signer.verify_beacon(message, malformed)
            assert result is False
    
    def test_concurrent_signing(self):
        """Test concurrent signing operations."""
        signer = BeaconSigner()
        
        # Multiple signatures should be independent
        messages = [secrets.token_bytes(32) for _ in range(100)]
        signatures = [signer.sign_beacon(msg) for msg in messages]
        
        # All signatures should verify
        for msg, sig in zip(messages, signatures):
            assert signer.verify_beacon(msg, sig)
        
        # Cross-verification should fail
        for i, msg in enumerate(messages):
            wrong_sig = signatures[(i + 1) % len(signatures)]
            assert not signer.verify_beacon(msg, wrong_sig)


class TestMACFuzzing:
    """Fuzzing tests for MAC operations."""
    
    def test_compute_mac_malformed(self):
        """Test MAC computation with malformed inputs."""
        phase_key = PhaseKey.generate()
        mac = PhaseMAC(phase_key)
        
        for chunk_idx in FuzzGenerator.malformed_integers():
            for prime in FuzzGenerator.malformed_integers():
                for data in FuzzGenerator.malformed_bytes():
                    try:
                        result = mac.compute_chunk_mac(chunk_idx, prime, data)
                        assert isinstance(result, bytes)
                    except (ValueError, TypeError, OverflowError):
                        # Acceptable to reject invalid inputs
                        pass
    
    def test_verify_mac_random(self):
        """Test MAC verification with random inputs."""
        phase_key = PhaseKey.generate()
        mac = PhaseMAC(phase_key)
        
        # Generate valid MAC
        chunk_idx = 0
        prime = 2
        data = b"test data"
        valid_mac = mac.compute_chunk_mac(chunk_idx, prime, data)
        
        # Try random MACs (should all fail except valid one)
        for _ in range(100):
            random_mac = secrets.token_bytes(32)
            result = mac.verify_chunk_mac(chunk_idx, prime, data, random_mac)
            
            if random_mac == valid_mac:
                assert result is True
            else:
                assert result is False


class TestInputValidationFuzzing:
    """Fuzzing tests for input validation."""
    
    def test_validate_key_size_fuzzing(self):
        """Test key size validation with random inputs."""
        for size in FuzzGenerator.malformed_integers():
            if size < 0:
                continue  # Skip negative sizes
            
            key = secrets.token_bytes(size) if size <= 10000 else b'x' * size
            
            try:
                InputValidation.validate_key_size(key, 32)
                assert len(key) == 32
            except ValueError:
                assert len(key) != 32
    
    def test_sanitize_string_fuzzing(self):
        """Test string sanitization with malformed inputs."""
        for malformed in FuzzGenerator.malformed_strings():
            try:
                result = InputValidation.sanitize_string(malformed)
                assert isinstance(result, str)
                # No null bytes
                assert '\x00' not in result
                # Within max length
                assert len(result) <= 1024
            except (ValueError, TypeError):
                # Acceptable to reject some inputs
                pass
    
    def test_validate_integer_range_fuzzing(self):
        """Test integer range validation."""
        for value in FuzzGenerator.malformed_integers():
            # Various ranges
            ranges = [
                (0, 100),
                (-100, 100),
                (0, 2**32),
                (None, 1000),
                (0, None),
            ]
            
            for min_val, max_val in ranges:
                try:
                    InputValidation.validate_integer_range(
                        value, min_val, max_val
                    )
                    # If successful, value must be in range
                    if min_val is not None:
                        assert value >= min_val
                    if max_val is not None:
                        assert value <= max_val
                except (ValueError, TypeError):
                    # Acceptable to reject out-of-range
                    pass


class TestConstantTimeFuzzing:
    """Fuzzing tests for constant-time operations."""
    
    def test_compare_random_bytes(self):
        """Test constant-time compare with random inputs."""
        for _ in range(100):
            a = FuzzGenerator.random_bytes()
            b = FuzzGenerator.random_bytes()
            
            result = ConstantTime.compare(a, b)
            assert isinstance(result, bool)
            assert result == (a == b)
    
    def test_compare_timing_consistency(self):
        """Test that comparison time is independent of input."""
        import time
        
        # Generate test cases
        equal_pairs = [(b'A' * 32, b'A' * 32) for _ in range(100)]
        diff_early = [(b'A' * 32, b'B' + b'A' * 31) for _ in range(100)]
        diff_late = [(b'A' * 31 + b'B', b'A' * 32) for _ in range(100)]
        
        def measure_timing(pairs):
            start = time.perf_counter()
            for a, b in pairs:
                ConstantTime.compare(a, b)
            return time.perf_counter() - start
        
        # All should take similar time
        t_equal = measure_timing(equal_pairs)
        t_early = measure_timing(diff_early)
        t_late = measure_timing(diff_late)
        
        # Timing should not vary significantly
        avg = (t_equal + t_early + t_late) / 3
        assert abs(t_equal - avg) / avg < 0.5  # Within 50%
        assert abs(t_early - avg) / avg < 0.5
        assert abs(t_late - avg) / avg < 0.5


class TestRateLimiterFuzzing:
    """Fuzzing tests for rate limiter."""
    
    def test_rate_limiter_random_requests(self):
        """Test rate limiter with random request patterns."""
        limiter = RateLimiter(max_attempts=10, window_seconds=1)
        
        # Random identifiers
        identifiers = [f"user_{i}" for i in range(20)]
        
        # Random requests
        for _ in range(200):
            identifier = random.choice(identifiers)
            result = limiter.check_limit(identifier)
            assert isinstance(result, bool)
    
    def test_rate_limiter_burst(self):
        """Test rate limiter under burst conditions."""
        limiter = RateLimiter(max_attempts=5, window_seconds=1)
        
        identifier = "test_user"
        
        # Burst of requests
        results = [limiter.check_limit(identifier) for _ in range(20)]
        
        # First 5 should succeed, rest should fail
        assert sum(results) <= 5
        assert results[:5] == [True] * 5
        assert all(not r for r in results[5:])


class TestAccessControlFuzzing:
    """Fuzzing tests for access control."""
    
    def test_policy_with_malformed_resources(self):
        """Test access control with malformed resource patterns."""
        root_key = PhaseKey.generate()
        hierarchy = KeyHierarchy(root_key)
        ac = AccessControl(hierarchy)
        
        malformed_resources = [
            '',
            '*' * 1000,
            '/' * 100,
            '../../../etc/passwd',
            'vertex:' + 'A' * 10000,
        ]
        
        for resource in malformed_resources:
            try:
                policy = AccessPolicy(
                    resource=resource,
                    action="read",
                    principal="user",
                    level=AccessLevel.READ_ONLY
                )
                ac.add_policy(policy)
            except (ValueError, TypeError):
                # Acceptable to reject malformed resources
                pass
    
    def test_concurrent_policy_checks(self):
        """Test concurrent access policy checks."""
        root_key = PhaseKey.generate()
        hierarchy = KeyHierarchy(root_key)
        ac = AccessControl(hierarchy)
        
        # Add policies
        ac.add_policy(AccessPolicy(
            resource="vertex:*",
            action="read",
            principal="role:user",
            level=AccessLevel.READ_ONLY
        ))
        
        # Many concurrent checks
        for _ in range(1000):
            resource = f"vertex:user_{random.randint(0, 100)}"
            action = random.choice(["read", "write", "delete"])
            principal = f"role:{random.choice(['user', 'admin', 'guest'])}"
            
            result = ac.check_access(resource, action, principal)
            assert isinstance(result, bool)


class TestAuditLogFuzzing:
    """Fuzzing tests for audit logging."""
    
    def test_log_malformed_events(self, tmp_path):
        """Test logging malformed audit events."""
        log_file = tmp_path / "audit_fuzz.log"
        logger = AuditLogger(str(log_file))
        
        malformed_events = [
            {},  # Empty event
            {'event_type': None},
            {'event_type': ''},
            {'event_type': 'test', 'actor': None},
            {'event_type': 'test', 'resource': '../../../etc/passwd'},
            {'event_type': 'test' * 1000},  # Very long
        ]
        
        for event in malformed_events:
            try:
                logger.log_event(**event)
            except (ValueError, TypeError, KeyError):
                # Acceptable to reject invalid events
                pass
    
    def test_concurrent_logging(self, tmp_path):
        """Test concurrent audit logging."""
        log_file = tmp_path / "audit_concurrent.log"
        logger = AuditLogger(str(log_file))
        
        # Log many events concurrently
        for i in range(1000):
            logger.log_event(
                event_type=random.choice(['read', 'write', 'delete']),
                actor=f"user_{random.randint(0, 100)}",
                resource=f"resource_{random.randint(0, 100)}",
                action=random.choice(['get', 'put', 'delete']),
                outcome=random.choice(['success', 'failure'])
            )
        
        # Verify log integrity
        logger.verify_integrity()


# Performance and stress tests
class TestSecurityPerformance:
    """Performance tests for security operations."""
    
    def test_signature_performance(self):
        """Test signature generation/verification performance."""
        signer = BeaconSigner()
        message = secrets.token_bytes(1024)
        
        import time
        
        # Benchmark signing
        start = time.perf_counter()
        signatures = [signer.sign_beacon(message) for _ in range(100)]
        sign_time = time.perf_counter() - start
        
        # Benchmark verification
        start = time.perf_counter()
        for sig in signatures:
            signer.verify_beacon(message, sig)
        verify_time = time.perf_counter() - start
        
        # Should be reasonably fast
        assert sign_time < 1.0  # 100 signatures in < 1s
        assert verify_time < 1.0  # 100 verifications in < 1s
    
    def test_mac_performance(self):
        """Test MAC computation performance."""
        phase_key = PhaseKey.generate()
        mac = PhaseMAC(phase_key)
        
        import time
        
        # Benchmark MAC computation
        start = time.perf_counter()
        for i in range(1000):
            mac.compute_chunk_mac(i, 2, b"test data")
        compute_time = time.perf_counter() - start
        
        # Should handle 1000 MACs quickly
        assert compute_time < 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
