"""
Tests for access control system.

Tests RBAC policies, access decisions, and integration with key hierarchy.
"""

import pytest
from unittest.mock import Mock

from resonagraph.security.access_control import (
    AccessControl, AccessPolicy, AccessRequest, AccessDecision,
    AccessLevel, ResourceType, Action, require_access
)
from resonagraph.security.key_hierarchy import KeyHierarchy
from resonagraph.security.hsm import MockHSM
from resonagraph.core.phase_key import PhaseKey


class TestAccessPolicy:
    """Test AccessPolicy functionality."""
    
    def test_policy_creation(self):
        """Test creating access policies."""
        policy = AccessPolicy(
            policy_id="test_policy",
            resource_pattern="vertex:user_*",
            action=Action.READ,
            principal="role:user",
            level=AccessLevel.READ_ONLY,
            description="Test policy"
        )
        
        assert policy.policy_id == "test_policy"
        assert policy.resource_pattern == "vertex:user_*"
        assert policy.action == Action.READ
        assert policy.principal == "role:user"
        assert policy.level == AccessLevel.READ_ONLY
        assert policy.created_at is not None
    
    def test_resource_matching(self):
        """Test resource pattern matching."""
        policy = AccessPolicy(
            policy_id="wildcard_policy",
            resource_pattern="vertex:user_*",
            action="*",
            principal="*",
            level=AccessLevel.READ_ONLY
        )
        
        # Should match
        assert policy.matches_resource("vertex:user_123")
        assert policy.matches_resource("vertex:user_alice")
        
        # Should not match
        assert not policy.matches_resource("vertex:post_123")
        assert not policy.matches_resource("edge:user_123:follows")
    
    def test_action_matching(self):
        """Test action matching."""
        # Wildcard policy
        wildcard_policy = AccessPolicy(
            policy_id="wildcard",
            resource_pattern="*",
            action="*",
            principal="*",
            level=AccessLevel.READ_ONLY
        )
        
        assert wildcard_policy.matches_action(Action.READ)
        assert wildcard_policy.matches_action(Action.WRITE)
        assert wildcard_policy.matches_action("custom_action")
        
        # Specific action policy
        read_policy = AccessPolicy(
            policy_id="read_only",
            resource_pattern="*",
            action=Action.READ,
            principal="*",
            level=AccessLevel.READ_ONLY
        )
        
        assert read_policy.matches_action(Action.READ)
        assert not read_policy.matches_action(Action.WRITE)
    
    def test_principal_matching(self):
        """Test principal matching."""
        policy = AccessPolicy(
            policy_id="role_policy",
            resource_pattern="*",
            action="*",
            principal="role:admin",
            level=AccessLevel.ADMIN
        )
        
        # Should match
        assert policy.matches_principal("role:admin")
        assert policy.matches_principal("role:admin:user123")  # Role prefix matching
        
        # Should not match
        assert not policy.matches_principal("role:user")
        assert not policy.matches_principal("user:admin")
    
    def test_condition_evaluation(self):
        """Test policy condition evaluation."""
        policy = AccessPolicy(
            policy_id="conditional_policy",
            resource_pattern="*",
            action="*", 
            principal="*",
            level=AccessLevel.READ_ONLY,
            conditions={
                "time_of_day": {"$in": ["morning", "afternoon"]},
                "department": "engineering",
                "security_clearance": {"$regex": "level_[34]"}
            }
        )
        
        # Should pass
        context1 = {
            "time_of_day": "morning",
            "department": "engineering", 
            "security_clearance": "level_3"
        }
        assert policy.evaluate_conditions(context1)
        
        # Should fail - wrong department
        context2 = {
            "time_of_day": "morning",
            "department": "sales",
            "security_clearance": "level_3"
        }
        assert not policy.evaluate_conditions(context2)
        
        # Should fail - missing field
        context3 = {
            "time_of_day": "morning",
            "department": "engineering"
            # missing security_clearance
        }
        assert not policy.evaluate_conditions(context3)


class TestAccessControl:
    """Test AccessControl system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.hsm = MockHSM()
        self.key_hierarchy = KeyHierarchy(hsm=self.hsm, auto_rotation=False)
        self.access_control = AccessControl(
            key_hierarchy=self.key_hierarchy,
            default_policy=AccessLevel.DENIED
        )
        
        # Create root key for key derivation tests
        self.key_hierarchy.create_root_key("test_root")
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if hasattr(self, 'key_hierarchy'):
            self.key_hierarchy.shutdown()
    
    def test_default_policies_created(self):
        """Test that default policies are created."""
        policies = self.access_control.list_policies()
        
        # Should have default policies
        policy_ids = [p.policy_id for p in policies]
        assert "default_super_admin" in policy_ids
        assert "default_admin" in policy_ids
        assert "default_user_read" in policy_ids
        assert "default_readonly" in policy_ids
    
    def test_add_remove_policy(self):
        """Test adding and removing policies."""
        initial_count = len(self.access_control.list_policies())
        
        # Add policy
        new_policy = AccessPolicy(
            policy_id="test_add_policy",
            resource_pattern="test:*",
            action="read",
            principal="role:tester",
            level=AccessLevel.READ_ONLY
        )
        
        self.access_control.add_policy(new_policy)
        assert len(self.access_control.list_policies()) == initial_count + 1
        
        # Remove policy
        removed = self.access_control.remove_policy("test_add_policy")
        assert removed
        assert len(self.access_control.list_policies()) == initial_count
        
        # Try to remove non-existent policy
        removed = self.access_control.remove_policy("non_existent")
        assert not removed
    
    def test_role_level_management(self):
        """Test setting and getting role levels."""
        self.access_control.set_role_level("test_role", AccessLevel.ADMIN)
        
        level = self.access_control.get_role_level("test_role")
        assert level == AccessLevel.ADMIN
        
        # Non-existent role should return default
        default_level = self.access_control.get_role_level("non_existent_role")
        assert default_level == AccessLevel.DENIED  # Our default policy
    
    def test_access_decision_super_admin(self):
        """Test super admin access."""
        request = AccessRequest(
            principal="role:super_admin",
            resource="any:resource",
            action=Action.DELETE  # High privilege action
        )
        
        decision = self.access_control.check_access(request)
        
        assert decision.granted
        assert decision.level == AccessLevel.SUPER_ADMIN
        assert decision.policy_id == "default_super_admin"
    
    def test_access_decision_denied(self):
        """Test access denial."""
        request = AccessRequest(
            principal="role:unknown",
            resource="sensitive:data",
            action=Action.WRITE
        )
        
        decision = self.access_control.check_access(request)
        
        assert not decision.granted
        assert decision.level == AccessLevel.DENIED
        assert "No matching policy" in decision.reason
    
    def test_access_decision_readonly(self):
        """Test read-only access."""
        request = AccessRequest(
            principal="role:readonly",
            resource="vertex:user_123",
            action=Action.READ
        )
        
        decision = self.access_control.check_access(request)
        
        assert decision.granted
        assert decision.level == AccessLevel.READ_ONLY
        assert decision.policy_id == "default_readonly"
        
        # Should deny write access
        write_request = AccessRequest(
            principal="role:readonly",
            resource="vertex:user_123", 
            action=Action.WRITE
        )
        
        write_decision = self.access_control.check_access(write_request)
        assert not write_decision.granted
    
    def test_user_convenience_methods(self):
        """Test convenience methods for user access."""
        # Test boolean check
        can_read = self.access_control.can_user_access(
            "test_user",
            "vertex:user_test_user",
            Action.READ
        )
        # Should be denied due to default policy
        assert not can_read
        
        # Add a policy for this user
        user_policy = AccessPolicy(
            policy_id="test_user_policy",
            resource_pattern="vertex:user_test_user",
            action="read",
            principal="user:test_user",
            level=AccessLevel.READ_ONLY
        )
        self.access_control.add_policy(user_policy)
        
        # Now should be granted
        can_read = self.access_control.can_user_access(
            "test_user",
            "vertex:user_test_user",
            Action.READ
        )
        assert can_read
        
        # Detailed evaluation
        decision = self.access_control.evaluate_policy_for_user(
            "test_user",
            "vertex:user_test_user",
            Action.READ
        )
        assert decision.granted
        assert decision.policy_id == "test_user_policy"
    
    def test_role_key_derivation(self):
        """Test deriving role-specific phase keys."""
        admin_key = self.access_control.get_role_key("admin", "users")
        user_key = self.access_control.get_role_key("user", "users")
        
        assert isinstance(admin_key, PhaseKey)
        assert isinstance(user_key, PhaseKey)
        
        # Keys should be different
        assert admin_key.get_bytes() != user_key.get_bytes()
        
        # Same role/topic should return same key (cached)
        admin_key2 = self.access_control.get_role_key("admin", "users")
        assert admin_key.get_bytes() == admin_key2.get_bytes()
    
    def test_policy_hierarchy(self):
        """Test that higher privilege policies override lower ones."""
        # Add conflicting policies with different privilege levels
        low_policy = AccessPolicy(
            policy_id="low_privilege",
            resource_pattern="test:resource",
            action="read",
            principal="role:test",
            level=AccessLevel.READ_ONLY
        )
        
        high_policy = AccessPolicy(
            policy_id="high_privilege", 
            resource_pattern="test:resource",
            action="read",
            principal="role:test",
            level=AccessLevel.ADMIN
        )
        
        self.access_control.add_policy(low_policy)
        self.access_control.add_policy(high_policy)
        
        request = AccessRequest(
            principal="role:test",
            resource="test:resource",
            action=Action.READ
        )
        
        decision = self.access_control.check_access(request)
        
        # Should use the higher privilege policy
        assert decision.granted
        assert decision.level == AccessLevel.ADMIN
        assert decision.policy_id == "high_privilege"
    
    def test_statistics_tracking(self):
        """Test access control statistics."""
        initial_stats = self.access_control.get_stats()
        
        # Make some access requests
        requests = [
            AccessRequest("role:admin", "vertex:test", Action.READ),
            AccessRequest("role:unknown", "vertex:test", Action.WRITE),
            AccessRequest("role:readonly", "vertex:test", Action.READ)
        ]
        
        for request in requests:
            self.access_control.check_access(request)
        
        stats = self.access_control.get_stats()
        
        # Should have tracked the requests
        assert stats['access_requests'] == initial_stats['access_requests'] + 3
        assert stats['access_granted'] > initial_stats['access_granted'] 
        assert stats['access_denied'] > initial_stats['access_denied']
        assert stats['policy_evaluations'] > initial_stats['policy_evaluations']


class TestAccessControlDecorator:
    """Test access control decorator."""
    
    def test_require_access_decorator(self):
        """Test the require_access decorator."""
        # Mock class that uses access control
        class MockService:
            def __init__(self):
                self.access_control = Mock()
                self._current_user = "test_user"
            
            @require_access("vertex:*", Action.READ, AccessLevel.READ_ONLY)
            def read_vertex(self, vertex_id):
                return f"Reading {vertex_id}"
            
            @require_access("vertex:*", Action.WRITE, AccessLevel.READ_WRITE)
            def write_vertex(self, vertex_id, data):
                return f"Writing {data} to {vertex_id}"
        
        service = MockService()
        
        # Mock successful access decision
        service.access_control.evaluate_policy_for_user.return_value = AccessDecision(
            granted=True,
            level=AccessLevel.READ_WRITE,
            reason="Test access granted"
        )
        
        # Should succeed
        result = service.read_vertex("vertex:123")
        assert result == "Reading vertex:123"
        
        # Verify access control was called
        service.access_control.evaluate_policy_for_user.assert_called()
        
        # Test access denied
        service.access_control.evaluate_policy_for_user.return_value = AccessDecision(
            granted=False,
            level=AccessLevel.DENIED,
            reason="Access denied"
        )
        
        with pytest.raises(PermissionError, match="Access denied"):
            service.read_vertex("vertex:456")


class TestIntegration:
    """Integration tests for access control components."""
    
    def test_end_to_end_access_control(self):
        """Test complete access control workflow."""
        # Set up components
        hsm = MockHSM()
        key_hierarchy = KeyHierarchy(hsm=hsm, auto_rotation=False)
        access_control = AccessControl(key_hierarchy=key_hierarchy)
        
        try:
            # Create root key
            key_hierarchy.create_root_key("production")
            
            # Define a custom policy for a specific application
            app_policy = AccessPolicy(
                policy_id="app_user_access",
                resource_pattern="vertex:app_user_*",
                action="*",
                principal="role:app_user",
                level=AccessLevel.READ_WRITE,
                conditions={"app_version": {"$regex": "v[2-9]\\."}}  # v2.0+ only
            )
            
            access_control.add_policy(app_policy)
            
            # Test access with correct context
            request = AccessRequest(
                principal="role:app_user",
                resource="vertex:app_user_123",
                action=Action.WRITE,
                context={"app_version": "v2.1.0"}
            )
            
            decision = access_control.check_access(request)
            assert decision.granted
            assert decision.level == AccessLevel.READ_WRITE
            
            # Test access with wrong context
            old_request = AccessRequest(
                principal="role:app_user",
                resource="vertex:app_user_123", 
                action=Action.WRITE,
                context={"app_version": "v1.5.0"}
            )
            
            old_decision = access_control.check_access(old_request)
            assert not old_decision.granted
            
            # Get role-specific key
            app_user_key = access_control.get_role_key("app_user", "application")
            assert isinstance(app_user_key, PhaseKey)
            
            # Verify different roles get different keys
            admin_key = access_control.get_role_key("admin", "application")
            assert app_user_key.get_bytes() != admin_key.get_bytes()
        
        finally:
            key_hierarchy.shutdown()
    
    def test_policy_conflict_resolution(self):
        """Test how conflicting policies are resolved."""
        hsm = MockHSM()
        key_hierarchy = KeyHierarchy(hsm=hsm, auto_rotation=False)
        access_control = AccessControl(key_hierarchy=key_hierarchy)
        
        try:
            # Add conflicting policies
            deny_policy = AccessPolicy(
                policy_id="deny_writes",
                resource_pattern="vertex:protected_*",
                action=Action.WRITE,
                principal="role:user",
                level=AccessLevel.DENIED
            )
            
            allow_policy = AccessPolicy(
                policy_id="allow_admin_writes",
                resource_pattern="vertex:protected_*", 
                action=Action.WRITE,
                principal="role:admin",
                level=AccessLevel.ADMIN
            )
            
            access_control.add_policy(deny_policy)
            access_control.add_policy(allow_policy)
            
            # User should be denied
            user_request = AccessRequest(
                principal="role:user",
                resource="vertex:protected_data",
                action=Action.WRITE
            )
            
            user_decision = access_control.check_access(user_request)
            assert not user_decision.granted
            
            # Admin should be allowed
            admin_request = AccessRequest(
                principal="role:admin",
                resource="vertex:protected_data",
                action=Action.WRITE
            )
            
            admin_decision = access_control.check_access(admin_request)
            assert admin_decision.granted
            assert admin_decision.level == AccessLevel.ADMIN
        
        finally:
            key_hierarchy.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
