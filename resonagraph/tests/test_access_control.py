"""
Tests for access control and role-based policies.

Tests access control policies, role-based access, and policy evaluation
as specified in NEXT_STEPS.md 6.1.
"""

import pytest

from resonagraph.core.phase_key import PhaseKey
from resonagraph.security.key_hierarchy import KeyHierarchy
from resonagraph.security.access_control import (
    AccessControl,
    AccessPolicy,
    AccessLevel
)


class TestAccessLevel:
    """Test AccessLevel enum comparisons."""
    
    def test_hierarchy(self):
        """Test access level hierarchy."""
        assert AccessLevel.ADMIN > AccessLevel.USER
        assert AccessLevel.USER > AccessLevel.READ_ONLY
        assert AccessLevel.READ_ONLY > AccessLevel.NONE
        
        assert AccessLevel.ADMIN >= AccessLevel.USER
        assert AccessLevel.USER >= AccessLevel.READ_ONLY
        assert AccessLevel.READ_ONLY >= AccessLevel.NONE
        
        assert AccessLevel.NONE < AccessLevel.READ_ONLY
        assert AccessLevel.READ_ONLY < AccessLevel.USER
        assert AccessLevel.USER < AccessLevel.ADMIN
    
    def test_equality(self):
        """Test access level equality."""
        assert AccessLevel.ADMIN >= AccessLevel.ADMIN
        assert AccessLevel.USER >= AccessLevel.USER
        assert not (AccessLevel.USER > AccessLevel.USER)


class TestAccessPolicy:
    """Test AccessPolicy functionality."""
    
    def test_exact_match(self):
        """Test exact policy matching."""
        policy = AccessPolicy(
            resource="vertex:user_123",
            action="read",
            principal="role:user",
            level=AccessLevel.USER
        )
        
        assert policy.matches("vertex:user_123", "read", "role:user")
        assert not policy.matches("vertex:user_456", "read", "role:user")
        assert not policy.matches("vertex:user_123", "write", "role:user")
        assert not policy.matches("vertex:user_123", "read", "role:admin")
    
    def test_wildcard_resource(self):
        """Test wildcard resource matching."""
        policy = AccessPolicy(
            resource="*",
            action="read",
            principal="role:user",
            level=AccessLevel.USER
        )
        
        assert policy.matches("vertex:user_123", "read", "role:user")
        assert policy.matches("edge:follows_456", "read", "role:user")
    
    def test_wildcard_action(self):
        """Test wildcard action matching."""
        policy = AccessPolicy(
            resource="vertex:user_123",
            action="*",
            principal="role:admin",
            level=AccessLevel.ADMIN
        )
        
        assert policy.matches("vertex:user_123", "read", "role:admin")
        assert policy.matches("vertex:user_123", "write", "role:admin")
        assert policy.matches("vertex:user_123", "delete", "role:admin")
    
    def test_wildcard_principal(self):
        """Test wildcard principal matching."""
        policy = AccessPolicy(
            resource="vertex:public",
            action="read",
            principal="*",
            level=AccessLevel.READ_ONLY
        )
        
        assert policy.matches("vertex:public", "read", "role:user")
        assert policy.matches("vertex:public", "read", "role:admin")
        assert policy.matches("vertex:public", "read", "role:guest")
    
    def test_prefix_wildcard_resource(self):
        """Test prefix wildcard for resources."""
        policy = AccessPolicy(
            resource="vertex:*",
            action="read",
            principal="role:user",
            level=AccessLevel.USER
        )
        
        assert policy.matches("vertex:user_123", "read", "role:user")
        assert policy.matches("vertex:post_456", "read", "role:user")
        assert not policy.matches("edge:follows", "read", "role:user")
    
    def test_prefix_wildcard_principal(self):
        """Test prefix wildcard for principals."""
        policy = AccessPolicy(
            resource="vertex:user_123",
            action="read",
            principal="role:*",
            level=AccessLevel.READ_ONLY
        )
        
        assert policy.matches("vertex:user_123", "read", "role:user")
        assert policy.matches("vertex:user_123", "read", "role:admin")
        assert not policy.matches("vertex:user_123", "read", "user:alice")


class TestAccessControl:
    """Test AccessControl functionality."""
    
    def test_initialization(self):
        """Test access control initialization."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        assert ac.key_hierarchy is hierarchy
        assert len(ac._policies) == 0
    
    def test_add_remove_policy(self):
        """Test adding and removing policies."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        policy = AccessPolicy(
            resource="*",
            action="read",
            principal="role:user",
            level=AccessLevel.USER
        )
        
        ac.add_policy(policy)
        assert len(ac._policies) == 1
        assert policy in ac._policies
        
        ac.remove_policy(policy)
        assert len(ac._policies) == 0
    
    def test_get_policies_no_filter(self):
        """Test getting all policies."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        policy1 = AccessPolicy("*", "read", "role:user", AccessLevel.USER)
        policy2 = AccessPolicy("*", "write", "role:admin", AccessLevel.ADMIN)
        
        ac.add_policy(policy1)
        ac.add_policy(policy2)
        
        policies = ac.get_policies()
        assert len(policies) == 2
    
    def test_get_policies_filtered(self):
        """Test getting filtered policies."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        policy1 = AccessPolicy("vertex:*", "read", "role:user", AccessLevel.USER)
        policy2 = AccessPolicy("edge:*", "write", "role:admin", AccessLevel.ADMIN)
        
        ac.add_policy(policy1)
        ac.add_policy(policy2)
        
        # Filter by resource
        vertex_policies = ac.get_policies(resource="vertex:123")
        assert len(vertex_policies) == 1
        assert policy1 in vertex_policies
    
    def test_check_access_allowed(self):
        """Test access check with matching policy."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        # Add policy for users to read
        ac.add_policy(AccessPolicy(
            resource="*",
            action="read",
            principal="role:user",
            level=AccessLevel.USER
        ))
        
        # Should allow access
        assert ac.check_access("vertex:123", "read", "role:user")
    
    def test_check_access_denied_no_policy(self):
        """Test access denial when no policy exists."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        # No policies added - should deny
        assert not ac.check_access("vertex:123", "read", "role:user")
    
    def test_check_access_denied_insufficient_level(self):
        """Test access denial with insufficient access level."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        # Add policy requiring ADMIN level
        ac.add_policy(AccessPolicy(
            resource="*",
            action="delete",
            principal="role:*",
            level=AccessLevel.ADMIN
        ))
        
        # User has insufficient level
        assert not ac.check_access("vertex:123", "delete", "role:user")
        
        # Admin should have access
        assert ac.check_access("vertex:123", "delete", "role:admin")
    
    def test_check_access_hierarchical(self):
        """Test hierarchical access levels."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        # Policy requiring USER level
        ac.add_policy(AccessPolicy(
            resource="*",
            action="write",
            principal="role:*",
            level=AccessLevel.USER
        ))
        
        # Admin (higher level) should have access
        assert ac.check_access("vertex:123", "write", "role:admin")
        
        # User should have access
        assert ac.check_access("vertex:123", "write", "role:user")
        
        # Read-only (lower level) should not have access
        assert not ac.check_access("vertex:123", "write", "role:read-only")
    
    def test_require_access_allowed(self):
        """Test require_access with allowed access."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        ac.add_policy(AccessPolicy(
            resource="*",
            action="read",
            principal="role:user",
            level=AccessLevel.USER
        ))
        
        # Should not raise exception
        ac.require_access("vertex:123", "read", "role:user")
    
    def test_require_access_denied(self):
        """Test require_access with denied access."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        # No policies - should raise PermissionError
        with pytest.raises(PermissionError, match="Access denied"):
            ac.require_access("vertex:123", "read", "role:user")
    
    def test_set_role_level(self):
        """Test setting custom role levels."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        # Create custom role
        ac.set_role_level("moderator", AccessLevel.USER)
        
        # Add policy
        ac.add_policy(AccessPolicy(
            resource="*",
            action="moderate",
            principal="role:*",
            level=AccessLevel.USER
        ))
        
        # Moderator should have access
        assert ac.check_access("vertex:123", "moderate", "role:moderator")
    
    def test_get_role_key(self):
        """Test getting role-specific phase keys."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        admin_key = ac.get_role_key("admin", "resource1", version=1)
        user_key = ac.get_role_key("user", "resource1", version=1)
        
        assert isinstance(admin_key, PhaseKey)
        assert isinstance(user_key, PhaseKey)
        assert admin_key != user_key
    
    def test_create_default_policies(self):
        """Test default policy creation."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        ac.create_default_policies()
        
        # Should have multiple default policies
        assert len(ac._policies) > 0
        
        # Admin should have full access
        assert ac.check_access("vertex:123", "read", "role:admin")
        assert ac.check_access("vertex:123", "write", "role:admin")
        assert ac.check_access("vertex:123", "delete", "role:admin")
        
        # User should have read/write/traverse
        assert ac.check_access("vertex:123", "read", "role:user")
        assert ac.check_access("vertex:123", "write", "role:user")
        assert ac.check_access("vertex:123", "traverse", "role:user")
        
        # Read-only should only have read
        assert ac.check_access("vertex:123", "read", "role:read-only")
        assert not ac.check_access("vertex:123", "write", "role:read-only")
    
    def test_user_principal_format(self):
        """Test user principal format."""
        hierarchy = KeyHierarchy()
        ac = AccessControl(hierarchy)
        
        # Add policy for specific user
        ac.add_policy(AccessPolicy(
            resource="vertex:alice_data",
            action="write",
            principal="user:alice",
            level=AccessLevel.USER
        ))
        
        # Alice should have access to her data
        assert ac.check_access("vertex:alice_data", "write", "user:alice")
        
        # Bob should not
        assert not ac.check_access("vertex:alice_data", "write", "user:bob")
