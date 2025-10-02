"""
Access control and role-based policies for ResonaGraph.

According to copilot-instructions.md Section 5 and NEXT_STEPS.md 6.1:
- Role-based access control (admin, user, read-only)
- Access control policies (resource, action, principal)
- Policy evaluation and enforcement
- Hierarchical access (parent keys unlock child data)
"""

from enum import Enum
from typing import List, Optional, Set, Dict
from dataclasses import dataclass

from ..core.phase_key import PhaseKey
from .key_hierarchy import KeyHierarchy


class AccessLevel(Enum):
    """
    Access levels for role-based access control.
    
    Hierarchical: ADMIN > USER > READ_ONLY > NONE
    """
    NONE = 0
    READ_ONLY = 1
    USER = 2
    ADMIN = 3
    
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented
    
    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented
    
    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented
    
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


@dataclass
class AccessPolicy:
    """
    Represents an access control policy.
    
    According to NEXT_STEPS.md 6.1:
    - Resource: What is being accessed (vertex, edge, topic)
    - Action: What operation (read, write, delete, traverse)
    - Principal: Who is accessing (role, user)
    - Level: Required access level
    """
    resource: str  # Resource pattern (supports wildcards)
    action: str  # Action type (read, write, delete, traverse)
    principal: str  # Principal (role:admin, user:alice, etc.)
    level: AccessLevel
    
    def matches(self, resource: str, action: str, principal: str) -> bool:
        """
        Check if this policy matches the given request.
        
        Args:
            resource: Resource being accessed
            action: Action being performed
            principal: Principal performing action
            
        Returns:
            True if policy matches
        """
        # Simple wildcard matching for now
        resource_match = (
            self.resource == "*" or 
            self.resource == resource or
            (self.resource.endswith("*") and resource.startswith(self.resource[:-1]))
        )
        
        action_match = self.action == "*" or self.action == action
        
        principal_match = (
            self.principal == "*" or 
            self.principal == principal or
            (self.principal.endswith("*") and principal.startswith(self.principal[:-1]))
        )
        
        return resource_match and action_match and principal_match


class AccessControl:
    """
    Manages access control policies and enforcement.
    
    According to NEXT_STEPS.md 6.1:
    - Policy structure (resource, action, principal)
    - Policy evaluation engine
    - Policy enforcement at SDK level
    - Role-based key derivation
    """
    
    def __init__(self, key_hierarchy: KeyHierarchy):
        """
        Initialize access control system.
        
        Args:
            key_hierarchy: KeyHierarchy for role-based key derivation
        """
        self.key_hierarchy = key_hierarchy
        self._policies: List[AccessPolicy] = []
        self._role_levels: Dict[str, AccessLevel] = {
            "admin": AccessLevel.ADMIN,
            "user": AccessLevel.USER,
            "read-only": AccessLevel.READ_ONLY,
            "guest": AccessLevel.READ_ONLY,
        }
    
    def add_policy(self, policy: AccessPolicy) -> None:
        """
        Add an access control policy.
        
        Args:
            policy: Policy to add
        """
        self._policies.append(policy)
    
    def remove_policy(self, policy: AccessPolicy) -> None:
        """
        Remove an access control policy.
        
        Args:
            policy: Policy to remove
        """
        if policy in self._policies:
            self._policies.remove(policy)
    
    def get_policies(
        self,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        principal: Optional[str] = None
    ) -> List[AccessPolicy]:
        """
        Get policies that could apply to the given criteria.
        
        Returns policies where each specified criterion matches.
        If a criterion is not specified (None), it's not used for filtering.
        
        Args:
            resource: Filter by resource (optional)
            action: Filter by action (optional)
            principal: Filter by principal (optional)
            
        Returns:
            List of policies that match all specified criteria
        """
        if resource is None and action is None and principal is None:
            # No filter - return all policies
            return list(self._policies)
        
        matching = []
        for policy in self._policies:
            # Check each criterion independently
            # Policy must match ALL specified criteria
            
            if resource is not None:
                # Check if policy's resource pattern matches the given resource
                resource_ok = (
                    policy.resource == "*" or
                    policy.resource == resource or
                    (policy.resource.endswith("*") and resource.startswith(policy.resource[:-1]))
                )
                if not resource_ok:
                    continue
            
            if action is not None:
                # Check if policy's action matches the given action
                action_ok = policy.action == "*" or policy.action == action
                if not action_ok:
                    continue
            
            if principal is not None:
                # Check if policy's principal pattern matches the given principal
                principal_ok = (
                    policy.principal == "*" or
                    policy.principal == principal or
                    (policy.principal.endswith("*") and principal.startswith(policy.principal[:-1]))
                )
                if not principal_ok:
                    continue
            
            matching.append(policy)
        
        return matching
    
    def check_access(
        self,
        resource: str,
        action: str,
        principal: str
    ) -> bool:
        """
        Check if access is allowed for the given request.
        
        According to NEXT_STEPS.md 6.1:
        - Policy evaluation engine
        - Access level enforcement
        
        Args:
            resource: Resource being accessed
            action: Action being performed
            principal: Principal performing action
            
        Returns:
            True if access is allowed, False otherwise
        """
        # Find matching policies
        matching_policies = [
            p for p in self._policies
            if p.matches(resource, action, principal)
        ]
        
        if not matching_policies:
            # No policy = deny by default
            return False
        
        # Get the principal's access level
        principal_level = self._get_principal_level(principal)
        
        # Check if any policy grants sufficient access
        for policy in matching_policies:
            if principal_level >= policy.level:
                return True
        
        return False
    
    def require_access(
        self,
        resource: str,
        action: str,
        principal: str
    ) -> None:
        """
        Require access or raise an exception.
        
        Args:
            resource: Resource being accessed
            action: Action being performed
            principal: Principal performing action
            
        Raises:
            PermissionError: If access is denied
        """
        if not self.check_access(resource, action, principal):
            raise PermissionError(
                f"Access denied: {principal} cannot {action} {resource}"
            )
    
    def _get_principal_level(self, principal: str) -> AccessLevel:
        """
        Get the access level for a principal.
        
        Args:
            principal: Principal identifier (format: "role:name" or "user:name")
            
        Returns:
            Access level
        """
        # Parse principal format
        if ":" in principal:
            principal_type, principal_name = principal.split(":", 1)
            
            if principal_type == "role":
                return self._role_levels.get(principal_name, AccessLevel.NONE)
            elif principal_type == "user":
                # For users, default to USER level unless overridden
                return self._role_levels.get(f"user:{principal_name}", AccessLevel.USER)
        
        return AccessLevel.NONE
    
    def set_role_level(self, role: str, level: AccessLevel) -> None:
        """
        Set the access level for a role.
        
        Args:
            role: Role identifier
            level: Access level
        """
        self._role_levels[role] = level
    
    def get_role_key(
        self,
        role: str,
        resource: str,
        version: int = 1
    ) -> PhaseKey:
        """
        Get a role-specific phase key.
        
        According to copilot-instructions.md:
        - Cloaking: Fold semantic keys into HMAC for role-based access views
        - Different keys reveal different data
        
        Args:
            role: Role identifier
            resource: Resource identifier
            version: Key version
            
        Returns:
            Role-specific phase key
        """
        return self.key_hierarchy.derive_role_key(role, resource, version)
    
    def create_default_policies(self) -> None:
        """
        Create default access control policies.
        
        Sets up basic policies for admin, user, and read-only roles.
        """
        # Admin can do everything
        self.add_policy(AccessPolicy(
            resource="*",
            action="*",
            principal="role:admin",
            level=AccessLevel.ADMIN
        ))
        
        # Users can read and write their own data
        self.add_policy(AccessPolicy(
            resource="*",
            action="read",
            principal="role:user",
            level=AccessLevel.USER
        ))
        self.add_policy(AccessPolicy(
            resource="*",
            action="write",
            principal="role:user",
            level=AccessLevel.USER
        ))
        self.add_policy(AccessPolicy(
            resource="*",
            action="traverse",
            principal="role:user",
            level=AccessLevel.USER
        ))
        
        # Read-only can only read
        self.add_policy(AccessPolicy(
            resource="*",
            action="read",
            principal="role:read-only",
            level=AccessLevel.READ_ONLY
        ))
