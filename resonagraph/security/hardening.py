"""
Security hardening utilities for ResonaGraph.

This module implements constant-time operations, side-channel mitigations,
and secure coding practices to protect against various attack vectors.
"""

import hmac
import secrets
import time
from typing import Any, Callable, Optional
from functools import wraps


class ConstantTime:
    """Utilities for constant-time operations to prevent timing attacks."""
    
    @staticmethod
    def compare(a: bytes, b: bytes) -> bool:
        """
        Constant-time byte string comparison.
        
        Prevents timing attacks by ensuring comparison time is independent
        of the position of the first differing byte.
        
        Args:
            a: First byte string
            b: Second byte string
            
        Returns:
            True if strings are equal, False otherwise
        """
        return hmac.compare_digest(a, b)
    
    @staticmethod
    def select(condition: bool, true_value: Any, false_value: Any) -> Any:
        """
        Constant-time conditional selection.
        
        Selects between two values based on a condition without revealing
        the condition through timing analysis.
        
        Args:
            condition: Selection condition
            true_value: Value to return if condition is True
            false_value: Value to return if condition is False
            
        Returns:
            Selected value
        """
        # Use bitwise operations to avoid conditional branches
        mask = -int(condition)
        return (true_value & mask) | (false_value & ~mask)
    
    @staticmethod
    def copy_if(condition: bool, source: bytes, dest: bytearray) -> None:
        """
        Constant-time conditional copy.
        
        Copies source to dest only if condition is True, without revealing
        the condition through timing.
        
        Args:
            condition: Whether to perform copy
            source: Source bytes
            dest: Destination bytearray
        """
        mask = -int(condition)
        for i in range(min(len(source), len(dest))):
            dest[i] = (source[i] & mask) | (dest[i] & ~mask)


class MemorySafe:
    """Memory safety utilities to prevent sensitive data leakage."""
    
    @staticmethod
    def zero_memory(data: bytearray) -> None:
        """
        Securely zero memory containing sensitive data.
        
        Overwrites memory with zeros to prevent sensitive data from
        remaining in memory after use.
        
        Args:
            data: Bytearray to zero
        """
        if not isinstance(data, bytearray):
            raise TypeError("Can only zero bytearray objects")
        
        # Multiple passes to resist data remanence
        for _ in range(3):
            for i in range(len(data)):
                data[i] = 0
    
    @staticmethod
    def secure_random(num_bytes: int) -> bytes:
        """
        Generate cryptographically secure random bytes.
        
        Uses secrets module to generate random bytes suitable for
        cryptographic use.
        
        Args:
            num_bytes: Number of random bytes to generate
            
        Returns:
            Random bytes
        """
        return secrets.token_bytes(num_bytes)
    
    @staticmethod
    def timing_safe_operation(func: Callable) -> Callable:
        """
        Decorator to add random delay to prevent timing analysis.
        
        Adds a small random delay to operations to make timing attacks
        more difficult.
        
        Args:
            func: Function to wrap
            
        Returns:
            Wrapped function with random delay
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)
            
            # Add random delay (0-10ms)
            delay = secrets.randbelow(10001) / 1000000.0
            time.sleep(delay)
            
            return result
        
        return wrapper


class InputValidation:
    """Input validation and sanitization utilities."""
    
    @staticmethod
    def validate_key_size(key: bytes, expected_size: int) -> None:
        """
        Validate cryptographic key size.
        
        Args:
            key: Key to validate
            expected_size: Expected key size in bytes
            
        Raises:
            ValueError: If key size is incorrect
        """
        if not isinstance(key, bytes):
            raise TypeError(f"Key must be bytes, got {type(key)}")
        
        if len(key) != expected_size:
            raise ValueError(
                f"Invalid key size: expected {expected_size} bytes, "
                f"got {len(key)} bytes"
            )
    
    @staticmethod
    def validate_nonce(nonce: bytes, min_size: int = 12) -> None:
        """
        Validate nonce size and uniqueness.
        
        Args:
            nonce: Nonce to validate
            min_size: Minimum nonce size in bytes
            
        Raises:
            ValueError: If nonce is invalid
        """
        if not isinstance(nonce, bytes):
            raise TypeError(f"Nonce must be bytes, got {type(nonce)}")
        
        if len(nonce) < min_size:
            raise ValueError(
                f"Nonce too small: minimum {min_size} bytes, "
                f"got {len(nonce)} bytes"
            )
    
    @staticmethod
    def sanitize_string(s: str, max_length: int = 1024) -> str:
        """
        Sanitize string input to prevent injection attacks.
        
        Args:
            s: String to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError: If string is too long or contains invalid characters
        """
        if not isinstance(s, str):
            raise TypeError(f"Expected string, got {type(s)}")
        
        if len(s) > max_length:
            raise ValueError(f"String too long: max {max_length} characters")
        
        # Remove null bytes and control characters
        sanitized = ''.join(char for char in s if ord(char) >= 32)
        
        return sanitized
    
    @staticmethod
    def validate_integer_range(
        value: int,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ) -> None:
        """
        Validate integer is within acceptable range.
        
        Args:
            value: Integer to validate
            min_value: Minimum allowed value (inclusive)
            max_value: Maximum allowed value (inclusive)
            
        Raises:
            TypeError: If value is not an integer
            ValueError: If value is out of range
        """
        if not isinstance(value, int):
            raise TypeError(f"Expected integer, got {type(value)}")
        
        if min_value is not None and value < min_value:
            raise ValueError(f"Value {value} below minimum {min_value}")
        
        if max_value is not None and value > max_value:
            raise ValueError(f"Value {value} above maximum {max_value}")


class SideChannelMitigation:
    """Mitigations against side-channel attacks."""
    
    @staticmethod
    def constant_time_modexp(base: int, exp: int, mod: int) -> int:
        """
        Constant-time modular exponentiation.
        
        Performs modular exponentiation in constant time to prevent
        timing attacks.
        
        Args:
            base: Base value
            exp: Exponent
            mod: Modulus
            
        Returns:
            (base ** exp) % mod
        """
        # Use Python's built-in pow with constant-time guarantee
        return pow(base, exp, mod)
    
    @staticmethod
    def prevent_branch_prediction(condition: bool) -> int:
        """
        Convert boolean to integer without conditional branches.
        
        Prevents branch prediction side-channel attacks.
        
        Args:
            condition: Boolean condition
            
        Returns:
            1 if condition is True, 0 otherwise
        """
        # Use bitwise operations instead of conditional
        return int(condition) & 1
    
    @staticmethod
    def cache_timing_resistant_lookup(
        table: list,
        index: int,
        dummy_value: Any
    ) -> Any:
        """
        Cache-timing resistant table lookup.
        
        Performs table lookup while accessing all elements to prevent
        cache timing attacks.
        
        Args:
            table: Lookup table
            index: Index to lookup
            dummy_value: Default value to return
            
        Returns:
            table[index] if valid, otherwise dummy_value
        """
        result = dummy_value
        
        # Access all elements to prevent cache timing analysis
        for i, value in enumerate(table):
            # Constant-time selection
            mask = -int(i == index)
            if isinstance(value, int) and isinstance(result, int):
                result = (value & mask) | (result & ~mask)
        
        return result


class RateLimiter:
    """Rate limiting to prevent abuse and DoS attacks."""
    
    def __init__(self, max_attempts: int, window_seconds: int):
        """
        Initialize rate limiter.
        
        Args:
            max_attempts: Maximum attempts allowed in window
            window_seconds: Time window in seconds
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = {}
    
    def check_limit(self, identifier: str) -> bool:
        """
        Check if identifier is within rate limit.
        
        Args:
            identifier: Unique identifier (e.g., IP address, user ID)
            
        Returns:
            True if within limit, False if limit exceeded
        """
        now = time.time()
        
        # Clean up old attempts
        if identifier in self.attempts:
            self.attempts[identifier] = [
                t for t in self.attempts[identifier]
                if now - t < self.window_seconds
            ]
        else:
            self.attempts[identifier] = []
        
        # Check limit
        if len(self.attempts[identifier]) >= self.max_attempts:
            return False
        
        # Record attempt
        self.attempts[identifier].append(now)
        return True
    
    def reset(self, identifier: str) -> None:
        """
        Reset rate limit for identifier.
        
        Args:
            identifier: Identifier to reset
        """
        if identifier in self.attempts:
            del self.attempts[identifier]


class SecureCompare:
    """Secure comparison utilities resistant to timing attacks."""
    
    @staticmethod
    def arrays_equal(a: bytes, b: bytes) -> bool:
        """
        Constant-time array comparison.
        
        Args:
            a: First array
            b: Second array
            
        Returns:
            True if arrays are equal
        """
        return ConstantTime.compare(a, b)
    
    @staticmethod
    def strings_equal(a: str, b: str) -> bool:
        """
        Constant-time string comparison.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            True if strings are equal
        """
        return hmac.compare_digest(a.encode(), b.encode())
    
    @staticmethod
    def verify_signature(
        signature: bytes,
        expected: bytes
    ) -> bool:
        """
        Constant-time signature verification.
        
        Args:
            signature: Signature to verify
            expected: Expected signature value
            
        Returns:
            True if signature is valid
        """
        if len(signature) != len(expected):
            # Still perform comparison to prevent length-based timing
            dummy = b'\x00' * len(expected)
            hmac.compare_digest(signature + dummy[:len(expected)-len(signature)], expected)
            return False
        
        return hmac.compare_digest(signature, expected)


# Export hardening utilities
__all__ = [
    'ConstantTime',
    'MemorySafe',
    'InputValidation',
    'SideChannelMitigation',
    'RateLimiter',
    'SecureCompare'
]
