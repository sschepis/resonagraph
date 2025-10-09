"""
Role-based access control (RBAC) for ResonaGraph.

Implements policy-based access control with hierarchical roles and
phase-key enforcement according to Phase 6A specifications.
"""

import time
from typing import Dict, List, Optional, Set, Any, Union
from dataclasses import dataclass
from enum import Enum, IntEnum
import fnmatch
import re

from resonagraph.core.phase_key import PhaseKey
from resonagraph.security.key_hierarchy import KeyHierarchy
from resonagraph.security.audit import AuditLogger, AuditEvent, AuditEventType


class AccessLevel(IntEnum):
    """
    Hierarchical access levels.
    
    Higher numeric values indicate higher privilege levels.
    """
    DENIED = 0
    READ_ONLY = 10
    READ_WRITE = 20
    ADMIN = 30
    SUPER_ADMIN = 40


class ResourceType(Enum):
    """Types of resources that can be protected."""
    VERTEX = "vertex"
    EDGE = "edge"
    GRAPH = "graph"
    SYSTEM = "system"
    KEY = "key"
    CONFIG = "config"
    AUDIT = "audit"


class Action(Enum):
    """Actions that can be performed on resources."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    CREATE = "create"
    UPDATE = "update"
    EXECUTE = "execute"
    CONFIGURE = "configure"
    AUDIT = "audit"


@dataclass
class AccessPolicy:
    """
    Access control policy definition.
    
    Defines who can perform what actions on which resources.
    """
    policy_id: str
    resource_pattern: str  # Glob pattern for resource matching
    resource_type: Optional[ResourceType] = None
    action: Union[Action, str] = "*"  # Specific action or "*" for all
    principal: str = "*"  # Role, user, or "*" for all
    level: AccessLevel = AccessLevel.READ_ONLY
    conditions: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    created_at: Optional[float] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.created_at is None:
            self.created_at = time.time()
        
        if self.conditions is None:
            self.conditions = {}
    
    def matches_resource(self, resource: str, resource_type: Optional[ResourceType] = None) -> bool:
        """
        Check if policy matches a resource.
        
        Args:
            resource: Resource identifier
            resource_type: Type of resource
            
        Returns:
            True if policy applies to this resource
        """
        # Check resource type if specified
        if self.resource_type and resource_type and self.resource_type != resource_type:
            return False
        
        # Check resource pattern
        return fnmatch.fnmatch(resource, self.resource_pattern)
    
    def matches_action(self, action: Union[Action, str]) -> bool:
        """
        Check if policy matches an action.
        
        Args:
            action: Action being performed
            
        Returns:
            True if policy applies to this action
        """
        if self.action == "*":
            return True
        
        if isinstance(action, Action):
            action = action.value
        
        if isinstance(self.action, Action):
            return self.action.value == action
        
        return self.action == action
    
    def matches_principal(self, principal: str) -> bool:
        """
        Check if policy matches a principal.
        
        Args:
            principal: Principal (role, user, etc.)
            
        Returns:
            True if policy applies to this principal
        """
        if self.principal == "*":
            return True
        
        # Support role prefix matching
        if self.principal.startswith("role:"):
            return principal.startswith(self.principal)
        
        return self.principal == principal
    
    def evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate policy conditions against context.
        
        Args:
            context: Request context
            
        Returns:
            True if all conditions are met
        """
        if not self.conditions:
            return True
        
        for condition_key, expected_value in self.conditions.items():
            if condition_key not in context:
                return False
            
            actual_value = context[condition_key]
            
            # Support various condition types
            if isinstance(expected_value, dict):
                if "$eq" in expected_value:
                    if actual_value != expected_value["$eq"]:
                        return False
                elif "$in" in expected_value:
                    if actual_value not in expected_value["$in"]:
                        return False
                elif "$regex" in expected_value:
                    if not re.match(expected_value["$regex"], str(actual_value)):
                        return False
            else:
                if actual_value != expected_value:
                    return False
        
        return True


@dataclass
class AccessRequest:
    """Represents an access control request."""
    principal: str
    resource: str
    action: Union[Action, str]
    resource_type: Optional[ResourceType] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.context is None:
            self.context = {}
        
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class AccessDecision:
    """Result of access control evaluation."""
    granted: bool
    level: AccessLevel
    policy_id: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AccessControl:
    """
    Main access control system for ResonaGraph.
    
    Provides policy-based access control with role hierarchy and
    integration with phase key management.
    """
    
    def __init__(
        self,
        key_hierarchy: KeyHierarchy,
        audit_logger: Optional[AuditLogger] = None,
        default_policy: AccessLevel = AccessLevel.DENIED
    ):
        """
        Initialize access control system.
        
        Args:
            key_hierarchy: Key hierarchy for role key derivation
            audit_logger: Audit logger for access events
            default_policy: Default access level when no policy matches
        """
        self.key_hierarchy = key_hierarchy
        self.audit_logger = audit_logger
        self.default_policy = default_policy
        
        # Policy storage
        self._policies: Dict[str, AccessPolicy] = {}
        self._role_levels: Dict[str, AccessLevel] = {}
        
        # Statistics
        self.stats = {
            'access_requests': 0,
            'access_granted': 0,
            'access_denied': 0,
            'policy_evaluations': 0
        }
        
        # Create default policies
        self._create_default_policies()
    
    def _create_default_policies(self) -> None:
        """Create default access control policies."""
        # Super admin can do anything
        self.add_policy(AccessPolicy(
            policy_id="default_super_admin",
            resource_pattern="*",
            action="*",
            principal="role:super_admin",
            level=AccessLevel.SUPER_ADMIN,
            description="Super admin full access"
        ))
        
        # Admin can manage most resources
        self.add_policy(AccessPolicy(
            policy_id="default_admin",
            resource_pattern="vertex:*",
            action="*",
            principal="role:admin",
            level=AccessLevel.ADMIN,
            description="Admin access to vertices"
        ))
        
        self.add_policy(AccessPolicy(
            policy_id="default_admin_edges",
            resource_pattern="edge:*",
            action="*",
            principal="role:admin",
            level=AccessLevel.ADMIN,
            description="Admin access to edges"
        ))
        
        # Users can read/write their own data
        self.add_policy(AccessPolicy(
            policy_id="default_user_read",
            resource_pattern="vertex:user_*",
            action="read",
            principal="role:user",
            level=AccessLevel.READ_WRITE,
            description="Users can access user vertices"
        ))
        
        # Read-only role
        self.add_policy(AccessPolicy(
            policy_id="default_readonly",
            resource_pattern="*",
            action="read",
            principal="role:readonly",
            level=AccessLevel.READ_ONLY,
            description="Read-only access to all resources"
        ))
        
        # Set default role levels
        self.set_role_level("super_admin", AccessLevel.SUPER_ADMIN)
        self.set_role_level("admin", AccessLevel.ADMIN)
        self.set_role_level("user", AccessLevel.READ_WRITE)
        self.set_role_level("readonly", AccessLevel.READ_ONLY)
    
    def add_policy(self, policy: AccessPolicy) -> None:
        """
        Add an access control policy.
        
        Args:
            policy: Policy to add
        """
        self._policies[policy.policy_id] = policy
        
        if self.audit_logger:
            self.audit_logger.log_security_event(
                AuditEventType.PERMISSION_CHANGED,
                policy.policy_id,
                "success",
                metadata={
                    "action": "policy_added",
                    "resource_pattern": policy.resource_pattern,
                    "principal": policy.principal,
                    "level": policy.level.name
                }
            )
    
    def remove_policy(self, policy_id: str) -> bool:
        """
        Remove an access control policy.
        
        Args:
            policy_id: ID of policy to remove
            
        Returns:
            True if policy was removed
        """
        if policy_id in self._policies:
            policy = self._policies.pop(policy_id)
            
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    AuditEventType.PERMISSION_CHANGED,
                    policy_id,
                    "success",
                    metadata={"action": "policy_removed"}
                )
            
            return True
        
        return False
    
    def set_role_level(self, role: str, level: AccessLevel) -> None:
        """
        Set the access level for a role.
        
        Args:
            role: Role name
            level: Access level for the role
        """
        self._role_levels[role] = level
        
        if self.audit_logger:
            self.audit_logger.log_security_event(
                AuditEventType.PERMISSION_CHANGED,
                f"role:{role}",
                "success",
                metadata={
                    "action": "role_level_set",
                    "level": level.name
                }
            )
    
    def get_role_level(self, role: str) -> AccessLevel:
        """Get the access level for a role."""
        return self._role_levels.get(role, self.default_policy)
    
    def check_access(self, request: AccessRequest) -> AccessDecision:
        """
        Check if access should be granted for a request.
        
        Args:
            request: Access request to evaluate
            
        Returns:
            Access decision
        """
        self.stats['access_requests'] += 1
        
        # Find matching policies
        matching_policies = self._find_matching_policies(request)
        
        if not matching_policies:
            # No matching policies, use default
            decision = AccessDecision(
                granted=(self.default_policy > AccessLevel.DENIED),
                level=self.default_policy,
                reason="No matching policy, using default"
            )
        else:
            # Use the highest privilege policy that matches
            best_policy = max(matching_policies, key=lambda p: p.level)
            decision = AccessDecision(
                granted=(best_policy.level > AccessLevel.DENIED),
                level=best_policy.level,
                policy_id=best_policy.policy_id,
                reason=f"Matched policy: {best_policy.policy_id}"
            )
        
        # Update statistics
        if decision.granted:
            self.stats['access_granted'] += 1
        else:
            self.stats['access_denied'] += 1
        
        # Log access attempt
        if self.audit_logger:
            event_type = AuditEventType.ACCESS_GRANTED if decision.granted else AuditEventType.ACCESS_DENIED
            self.audit_logger.log_security_event(
                event_type,
                request.resource,
                "success" if decision.granted else "denied",
                actor=request.principal,
                metadata={
                    "action": str(request.action),
                    "level": decision.level.name,
                    "policy_id": decision.policy_id,
                    "reason": decision.reason
                }
            )
        
        return decision
    
    def _find_matching_policies(self, request: AccessRequest) -> List[AccessPolicy]:
        """Find all policies that match the request."""
        matching = []
        
        for policy in self._policies.values():
            self.stats['policy_evaluations'] += 1
            
            # Check if policy matches
            if (policy.matches_resource(request.resource, request.resource_type) and
                policy.matches_action(request.action) and
                policy.matches_principal(request.principal) and
                policy.evaluate_conditions(request.context)):
                
                matching.append(policy)
        
        return matching
    
    def get_role_key(self, role: str, topic: str, version: int = 1) -> PhaseKey:
        """
        Get the phase key for a specific role and topic.
        
        Args:
            role: Role name
            topic: Topic/namespace
            version: Key version (for rotation)
            
        Returns:
            Phase key for the role
        """
        # Derive role-specific key
        role_key = self.key_hierarchy.derive_role_key(role, topic)
        
        if self.audit_logger:
            self.audit_logger.log_key_operation(
                "access",
                f"role:{role}:topic:{topic}",
                "success",
                metadata={"version": version}
            )
        
        return role_key
    
    def list_policies(self, principal: Optional[str] = None) -> List[AccessPolicy]:
        """
        List access policies, optionally filtered by principal.
        
        Args:
            principal: Optional principal filter
            
        Returns:
            List of matching policies
        """
        policies = list(self._policies.values())
        
        if principal:
            policies = [p for p in policies if p.matches_principal(principal)]
        
        return policies
    
    def get_policy(self, policy_id: str) -> Optional[AccessPolicy]:
        """Get a specific policy by ID."""
        return self._policies.get(policy_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get access control statistics."""
        return self.stats.copy()
    
    def evaluate_policy_for_user(
        self,
        user: str,
        resource: str,
        action: Union[Action, str],
        context: Optional[Dict[str, Any]] = None
    ) -> AccessDecision:
        """
        Convenience method to evaluate access for a user.
        
        Args:
            user: User identifier
            resource: Resource being accessed
            action: Action being performed
            context: Additional context
            
        Returns:
            Access decision
        """
        request = AccessRequest(
            principal=f"user:{user}",
            resource=resource,
            action=action,
            context=context or {}
        )
        
        return self.check_access(request)
    
    def can_user_access(
        self,
        user: str,
        resource: str,
        action: Union[Action, str],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Simple boolean check if user can access resource.
        
        Args:
            user: User identifier
            resource: Resource being accessed
            action: Action being performed
            context: Additional context
            
        Returns:
            True if access is granted
        """
        decision = self.evaluate_policy_for_user(user, resource, action, context)
        return decision.granted


# Decorator for access control enforcement
def require_access(
    resource: str,
    action: Union[Action, str],
    level: AccessLevel = AccessLevel.READ_ONLY
):
    """
    Decorator to enforce access control on methods.
    
    Args:
        resource: Resource pattern being accessed
        action: Action being performed
        level: Minimum required access level
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Extract user from method arguments or context
            # This would need to be adapted based on actual method signatures
            user = kwargs.get('user') or getattr(self, '_current_user', None)
            
            if not user:
                raise PermissionError("No user context for access control")
            
            # Check access
            if hasattr(self, 'access_control'):
                decision = self.access_control.evaluate_policy_for_user(
                    user, resource, action
                )
                
                if not decision.granted or decision.level < level:
                    raise PermissionError(f"Access denied: {decision.reason}")
            
            return func(self, *args, **kwargs)
        
        return wrapper
    return decorator
