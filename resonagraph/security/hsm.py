"""
Hardware Security Module (HSM) interface for ResonaGraph.

Provides abstraction for HSM integration with fallback to mock implementation
for development and testing.
"""

import os
import secrets
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum


class HSMError(Exception):
    """Base exception for HSM operations."""
    pass


class HSMKeyNotFoundError(HSMError):
    """Raised when a key is not found in HSM."""
    pass


class HSMOperationError(HSMError):
    """Raised when an HSM operation fails."""
    pass


@dataclass
class HSMKeyInfo:
    """Information about a key stored in HSM."""
    key_id: str
    created_at: str
    key_type: str
    key_size: int
    algorithm: str
    
    
class HSMInterface(ABC):
    """
    Abstract interface for Hardware Security Modules.
    
    Supports both real HSMs (PKCS#11, AWS CloudHSM, Azure Key Vault)
    and mock implementations for development.
    """
    
    @abstractmethod
    def store_key(self, key_id: str, key_data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store a key in the HSM.
        
        Args:
            key_id: Unique identifier for the key
            key_data: Raw key bytes
            metadata: Optional metadata to store with key
            
        Returns:
            True if successful
            
        Raises:
            HSMOperationError: If operation fails
        """
        pass
    
    @abstractmethod
    def get_key(self, key_id: str) -> Optional[bytes]:
        """
        Retrieve a key from the HSM.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Key bytes if found, None otherwise
            
        Raises:
            HSMOperationError: If operation fails
        """
        pass
    
    @abstractmethod
    def key_exists(self, key_id: str) -> bool:
        """
        Check if a key exists in the HSM.
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if key exists
        """
        pass
    
    @abstractmethod
    def delete_key(self, key_id: str) -> bool:
        """
        Delete a key from the HSM.
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if successful
            
        Raises:
            HSMKeyNotFoundError: If key doesn't exist
            HSMOperationError: If operation fails
        """
        pass
    
    @abstractmethod
    def list_keys(self) -> Dict[str, HSMKeyInfo]:
        """
        List all keys in the HSM.
        
        Returns:
            Dict mapping key_id to key info
        """
        pass
    
    @abstractmethod
    def generate_key(self, key_id: str, key_size: int = 32) -> bytes:
        """
        Generate a new key directly in the HSM.
        
        Args:
            key_id: Key identifier
            key_size: Key size in bytes
            
        Returns:
            Generated key bytes
            
        Raises:
            HSMOperationError: If operation fails
        """
        pass


class MockHSM(HSMInterface):
    """
    Mock HSM implementation for development and testing.
    
    Stores keys in memory with optional file persistence.
    NOT FOR PRODUCTION USE.
    """
    
    def __init__(self, persist_file: Optional[str] = None):
        """
        Initialize mock HSM.
        
        Args:
            persist_file: Optional file to persist keys to
        """
        self._keys: Dict[str, bytes] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self.persist_file = persist_file
        
        if persist_file and os.path.exists(persist_file):
            self._load_from_file()
    
    def store_key(self, key_id: str, key_data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store key in memory."""
        if len(key_data) not in [16, 24, 32]:  # AES key sizes
            raise HSMOperationError(f"Invalid key size: {len(key_data)} bytes")
        
        self._keys[key_id] = key_data
        self._metadata[key_id] = metadata or {}
        
        if self.persist_file:
            self._save_to_file()
        
        return True
    
    def get_key(self, key_id: str) -> Optional[bytes]:
        """Retrieve key from memory."""
        return self._keys.get(key_id)
    
    def key_exists(self, key_id: str) -> bool:
        """Check if key exists."""
        return key_id in self._keys
    
    def delete_key(self, key_id: str) -> bool:
        """Delete key from memory."""
        if key_id not in self._keys:
            raise HSMKeyNotFoundError(f"Key {key_id} not found")
        
        del self._keys[key_id]
        if key_id in self._metadata:
            del self._metadata[key_id]
        
        if self.persist_file:
            self._save_to_file()
        
        return True
    
    def list_keys(self) -> Dict[str, HSMKeyInfo]:
        """List all keys."""
        result = {}
        for key_id, key_data in self._keys.items():
            metadata = self._metadata.get(key_id, {})
            result[key_id] = HSMKeyInfo(
                key_id=key_id,
                created_at=metadata.get('created_at', 'unknown'),
                key_type='symmetric',
                key_size=len(key_data),
                algorithm='AES'
            )
        return result
    
    def generate_key(self, key_id: str, key_size: int = 32) -> bytes:
        """Generate new key."""
        key_data = secrets.token_bytes(key_size)
        self.store_key(key_id, key_data, {
            'created_at': str(os.times()),
            'generated': True
        })
        return key_data
    
    def _save_to_file(self) -> None:
        """Save keys to file (for persistence)."""
        if not self.persist_file:
            return
        
        import json
        data = {
            'keys': {k: v.hex() for k, v in self._keys.items()},
            'metadata': self._metadata
        }
        
        with open(self.persist_file, 'w') as f:
            json.dump(data, f)
    
    def _load_from_file(self) -> None:
        """Load keys from file."""
        if not self.persist_file or not os.path.exists(self.persist_file):
            return
        
        import json
        try:
            with open(self.persist_file, 'r') as f:
                data = json.load(f)
            
            self._keys = {k: bytes.fromhex(v) for k, v in data.get('keys', {}).items()}
            self._metadata = data.get('metadata', {})
        except (json.JSONDecodeError, ValueError) as e:
            raise HSMOperationError(f"Failed to load HSM data from {self.persist_file}: {e}")


class PKCS11HSM(HSMInterface):
    """
    PKCS#11 HSM implementation for production use.
    
    Requires PyKCS11 or similar PKCS#11 library.
    """
    
    def __init__(
        self,
        library_path: str,
        slot_id: int = 0,
        pin: Optional[str] = None,
        token_label: Optional[str] = None
    ):
        """
        Initialize PKCS#11 HSM.
        
        Args:
            library_path: Path to PKCS#11 library
            slot_id: HSM slot ID
            pin: PIN for HSM access
            token_label: Token label to use
        """
        self.library_path = library_path
        self.slot_id = slot_id
        self.pin = pin
        self.token_label = token_label
        self._session = None
        
        # Note: Actual PKCS#11 implementation would require PyKCS11
        # This is a placeholder for the interface
        raise NotImplementedError("PKCS#11 HSM implementation requires PyKCS11 library")
    
    def store_key(self, key_id: str, key_data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store key in PKCS#11 HSM."""
        # Placeholder - would implement actual PKCS#11 operations
        raise NotImplementedError("PKCS#11 implementation pending")
    
    def get_key(self, key_id: str) -> Optional[bytes]:
        """Retrieve key from PKCS#11 HSM."""
        raise NotImplementedError("PKCS#11 implementation pending")
    
    def key_exists(self, key_id: str) -> bool:
        """Check if key exists in PKCS#11 HSM."""
        raise NotImplementedError("PKCS#11 implementation pending")
    
    def delete_key(self, key_id: str) -> bool:
        """Delete key from PKCS#11 HSM."""
        raise NotImplementedError("PKCS#11 implementation pending")
    
    def list_keys(self) -> Dict[str, HSMKeyInfo]:
        """List keys in PKCS#11 HSM."""
        raise NotImplementedError("PKCS#11 implementation pending")
    
    def generate_key(self, key_id: str, key_size: int = 32) -> bytes:
        """Generate key in PKCS#11 HSM."""
        raise NotImplementedError("PKCS#11 implementation pending")


class AWSCloudHSM(HSMInterface):
    """
    AWS CloudHSM implementation.
    
    Requires boto3 and AWS SDK configuration.
    """
    
    def __init__(self, cluster_id: str, region: str = 'us-east-1'):
        """
        Initialize AWS CloudHSM.
        
        Args:
            cluster_id: CloudHSM cluster ID
            region: AWS region
        """
        self.cluster_id = cluster_id
        self.region = region
        
        # Note: Actual implementation would require boto3
        raise NotImplementedError("AWS CloudHSM implementation requires boto3")
    
    def store_key(self, key_id: str, key_data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store key in CloudHSM."""
        raise NotImplementedError("AWS CloudHSM implementation pending")
    
    def get_key(self, key_id: str) -> Optional[bytes]:
        """Retrieve key from CloudHSM."""
        raise NotImplementedError("AWS CloudHSM implementation pending")
    
    def key_exists(self, key_id: str) -> bool:
        """Check if key exists in CloudHSM."""
        raise NotImplementedError("AWS CloudHSM implementation pending")
    
    def delete_key(self, key_id: str) -> bool:
        """Delete key from CloudHSM."""
        raise NotImplementedError("AWS CloudHSM implementation pending")
    
    def list_keys(self) -> Dict[str, HSMKeyInfo]:
        """List keys in CloudHSM."""
        raise NotImplementedError("AWS CloudHSM implementation pending")
    
    def generate_key(self, key_id: str, key_size: int = 32) -> bytes:
        """Generate key in CloudHSM."""
        raise NotImplementedError("AWS CloudHSM implementation pending")


def create_hsm(hsm_config: Dict[str, Any]) -> HSMInterface:
    """
    Factory function to create HSM instance based on configuration.
    
    Args:
        hsm_config: HSM configuration dict
        
    Returns:
        HSM interface instance
        
    Example config:
        {
            "type": "mock",
            "persist_file": "/tmp/hsm_keys.json"
        }
        
        {
            "type": "pkcs11",
            "library_path": "/usr/lib/libpkcs11.so",
            "slot_id": 0,
            "pin": "1234"
        }
        
        {
            "type": "aws_cloudhsm",
            "cluster_id": "cluster-abcd1234",
            "region": "us-east-1"
        }
    """
    hsm_type = hsm_config.get('type', 'mock').lower()
    
    if hsm_type == 'mock':
        return MockHSM(persist_file=hsm_config.get('persist_file'))
    
    elif hsm_type == 'pkcs11':
        return PKCS11HSM(
            library_path=hsm_config['library_path'],
            slot_id=hsm_config.get('slot_id', 0),
            pin=hsm_config.get('pin'),
            token_label=hsm_config.get('token_label')
        )
    
    elif hsm_type == 'aws_cloudhsm':
        return AWSCloudHSM(
            cluster_id=hsm_config['cluster_id'],
            region=hsm_config.get('region', 'us-east-1')
        )
    
    else:
        raise ValueError(f"Unsupported HSM type: {hsm_type}")