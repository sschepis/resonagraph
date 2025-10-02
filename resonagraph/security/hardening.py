"""
Security hardening utilities for ResonaGraph.

According to NEXT_STEPS.md 6.4:
- Constant-time operations for crypto
- Memory-safe implementations
- Side-channel attack mitigations
"""

import os
import secrets
from typing import Optional


class SecurityHardening:
    """
    Security hardening utilities and best practices.
    
    Provides helper functions for secure operations and
    side-channel attack mitigations.
    """
    
    @staticmethod
    def constant_time_compare(a: bytes, b: bytes) -> bool:
        """
        Constant-time comparison of byte strings.
        
        According to copilot-instructions.md:
        - Use constant-time comparisons for security-critical paths
        - Prevents timing attacks on key/signature comparisons
        
        Args:
            a: First byte string
            b: Second byte string
            
        Returns:
            True if equal, False otherwise
        """
        # Use hmac.compare_digest for constant-time comparison
        import hmac
        return hmac.compare_digest(a, b)
    
    @staticmethod
    def secure_random_bytes(n: int) -> bytes:
        """
        Generate cryptographically secure random bytes.
        
        Args:
            n: Number of bytes to generate
            
        Returns:
            Random bytes
        """
        return secrets.token_bytes(n)
    
    @staticmethod
    def secure_random_int(min_val: int, max_val: int) -> int:
        """
        Generate cryptographically secure random integer.
        
        Args:
            min_val: Minimum value (inclusive)
            max_val: Maximum value (inclusive)
            
        Returns:
            Random integer in range
        """
        return secrets.randbelow(max_val - min_val + 1) + min_val
    
    @staticmethod
    def clear_memory(data: bytearray) -> None:
        """
        Clear sensitive data from memory.
        
        Best effort to overwrite memory before deallocation.
        Note: Python's memory management makes this difficult.
        
        Args:
            data: Bytearray to clear
        """
        if isinstance(data, bytearray):
            # Overwrite with random data
            for i in range(len(data)):
                data[i] = 0
    
    @staticmethod
    def validate_key_size(key: bytes, expected_size: int) -> None:
        """
        Validate key size for cryptographic operations.
        
        Args:
            key: Key bytes to validate
            expected_size: Expected key size in bytes
            
        Raises:
            ValueError: If key size is incorrect
        """
        if len(key) != expected_size:
            raise ValueError(f"Invalid key size: expected {expected_size}, got {len(key)}")
    
    @staticmethod
    def validate_signature_size(signature: bytes) -> None:
        """
        Validate Ed25519 signature size.
        
        Args:
            signature: Signature bytes to validate
            
        Raises:
            ValueError: If signature size is incorrect
        """
        if len(signature) != 64:
            raise ValueError(f"Invalid signature size: expected 64, got {len(signature)}")
    
    @staticmethod
    def add_random_delay(max_ms: int = 100) -> None:
        """
        Add random delay to prevent timing attacks.
        
        Use sparingly as it impacts performance.
        
        Args:
            max_ms: Maximum delay in milliseconds
        """
        import time
        delay_ms = secrets.randbelow(max_ms + 1)
        time.sleep(delay_ms / 1000.0)
    
    @staticmethod
    def sanitize_error_message(message: str, safe_message: str = "Operation failed") -> str:
        """
        Sanitize error messages to prevent information leakage.
        
        Args:
            message: Internal error message
            safe_message: Safe message to return externally
            
        Returns:
            Sanitized error message
        """
        # In production, always return generic message
        # Internal message should be logged to audit
        return safe_message
    
    @staticmethod
    def check_resource_limits() -> dict:
        """
        Check system resource limits.
        
        Returns:
            Dictionary of resource information
        """
        try:
            import resource
            
            # Get current limits
            nofile_soft, nofile_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            nproc_soft, nproc_hard = resource.getrlimit(resource.RLIMIT_NPROC)
            
            return {
                'max_open_files_soft': nofile_soft,
                'max_open_files_hard': nofile_hard,
                'max_processes_soft': nproc_soft,
                'max_processes_hard': nproc_hard
            }
        except (ImportError, AttributeError):
            # resource module not available (Windows)
            return {}
    
    @staticmethod
    def recommend_security_settings() -> dict:
        """
        Get recommended security settings for production.
        
        Returns:
            Dictionary of recommended settings
        """
        return {
            'use_hsm': True,
            'key_rotation_interval': 86400,  # 24 hours for phase keys
            'signature_key_rotation': 86400 * 30,  # 30 days for signature keys
            'audit_anonymization_level': 'HIGH',
            'enable_hash_chain': True,
            'epoch_window': 10,
            'max_nonces_per_key': 10000,
            'tls_min_version': 'TLSv1.3',
            'enable_rate_limiting': True,
            'max_lock_attempts_per_minute': 100,
            'session_timeout': 3600,  # 1 hour
            'log_retention_days': 90,
        }


class InputValidator:
    """
    Input validation utilities to prevent injection and other attacks.
    """
    
    @staticmethod
    def validate_key_format(key: str) -> None:
        """
        Validate key format.
        
        Args:
            key: Key string to validate
            
        Raises:
            ValueError: If key format is invalid
        """
        if not key:
            raise ValueError("Key cannot be empty")
        
        if len(key) > 1024:
            raise ValueError("Key too long (max 1024 characters)")
        
        # Check for control characters
        if any(ord(c) < 32 for c in key):
            raise ValueError("Key contains invalid control characters")
    
    @staticmethod
    def validate_epoch(epoch: int, current_epoch: int, window: int = 10) -> None:
        """
        Validate epoch value.
        
        Args:
            epoch: Epoch to validate
            current_epoch: Current epoch number
            window: Acceptable window size
            
        Raises:
            ValueError: If epoch is invalid
        """
        if not isinstance(epoch, int):
            raise TypeError("Epoch must be integer")
        
        if epoch < 0:
            raise ValueError("Epoch cannot be negative")
        
        if epoch < current_epoch - window:
            raise ValueError("Epoch too old")
        
        if epoch > current_epoch + 1:
            raise ValueError("Epoch too far in future")
    
    @staticmethod
    def validate_nonce(nonce: bytes) -> None:
        """
        Validate nonce format.
        
        Args:
            nonce: Nonce bytes to validate
            
        Raises:
            ValueError: If nonce is invalid
        """
        if not nonce:
            raise ValueError("Nonce cannot be empty")
        
        if len(nonce) < 8:
            raise ValueError("Nonce too short (min 8 bytes)")
        
        if len(nonce) > 256:
            raise ValueError("Nonce too long (max 256 bytes)")
    
    @staticmethod
    def sanitize_resource_identifier(resource: str) -> str:
        """
        Sanitize resource identifier for safe use.
        
        Args:
            resource: Resource identifier
            
        Returns:
            Sanitized resource identifier
        """
        # Remove potentially dangerous characters, keep only alphanumeric, colon, dot, underscore
        import re
        return re.sub(r'[^\w:.]', '', resource)[:1024]
