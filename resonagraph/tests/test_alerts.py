"""
Tests for security alerts system.
"""

import pytest
import time

from resonagraph.security.alerts import SecurityAlert, AlertType
from resonagraph.security.threat_detection import ThreatLevel


class TestSecurityAlert:
    """Test suite for SecurityAlert."""
    
    def test_alert_creation(self):
        """Test security alert creation."""
        alert = SecurityAlert(
            alert_type=AlertType.BRUTE_FORCE_ATTACK,
            threat_level=ThreatLevel.HIGH,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["resource1", "resource2"],
            actor="test@example.com"
        )
        
        assert alert.alert_type == AlertType.BRUTE_FORCE_ATTACK
        assert alert.threat_level == ThreatLevel.HIGH
        assert alert.description == "Test alert"
        assert len(alert.affected_resources) == 2
        assert alert.actor == "test@example.com"
        assert alert.alert_id is not None
    
    def test_alert_id_generation(self):
        """Test automatic alert ID generation."""
        timestamp = time.time()
        alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.MEDIUM,
            timestamp=timestamp,
            description="Test alert",
            affected_resources=["resource1"]
        )
        
        assert alert.alert_id is not None
        assert alert.alert_id.startswith("alert_")
        assert str(int(timestamp)) in alert.alert_id
    
    def test_alert_with_custom_id(self):
        """Test alert creation with custom ID."""
        custom_id = "custom_alert_12345"
        alert = SecurityAlert(
            alert_type=AlertType.SUSPICIOUS_KEY_ACCESS,
            threat_level=ThreatLevel.LOW,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["resource1"],
            alert_id=custom_id
        )
        
        assert alert.alert_id == custom_id
    
    def test_alert_with_evidence(self):
        """Test alert with evidence data."""
        evidence = {
            "event_count": 10,
            "time_window": 300,
            "actor_ip": "192.168.1.100"
        }
        
        alert = SecurityAlert(
            alert_type=AlertType.REPLAY_ATTACK_PATTERN,
            threat_level=ThreatLevel.HIGH,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["resource1"],
            evidence=evidence
        )
        
        assert alert.evidence == evidence
        assert alert.evidence["event_count"] == 10
        assert alert.evidence["time_window"] == 300
    
    def test_alert_with_recommendations(self):
        """Test alert with recommended actions."""
        recommendations = [
            "Block suspicious IP",
            "Review access logs",
            "Notify security team"
        ]
        
        alert = SecurityAlert(
            alert_type=AlertType.SYSTEM_COMPROMISE,
            threat_level=ThreatLevel.CRITICAL,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["system"],
            recommended_actions=recommendations
        )
        
        assert len(alert.recommended_actions) == 3
        assert "Block suspicious IP" in alert.recommended_actions
    
    def test_alert_to_dict(self):
        """Test alert serialization to dictionary."""
        alert = SecurityAlert(
            alert_type=AlertType.PRIVILEGE_ESCALATION,
            threat_level=ThreatLevel.HIGH,
            timestamp=1234567890.0,
            description="Test alert",
            affected_resources=["admin/settings"],
            actor="user@example.com",
            evidence={"attempts": 5},
            recommended_actions=["Review permissions"]
        )
        
        alert_dict = alert.to_dict()
        
        assert alert_dict["alert_type"] == AlertType.PRIVILEGE_ESCALATION.value
        assert alert_dict["threat_level"] == ThreatLevel.HIGH.value
        assert alert_dict["timestamp"] == 1234567890.0
        assert alert_dict["description"] == "Test alert"
        assert alert_dict["affected_resources"] == ["admin/settings"]
        assert alert_dict["actor"] == "user@example.com"
        assert alert_dict["evidence"] == {"attempts": 5}
        assert alert_dict["recommended_actions"] == ["Review permissions"]
        assert "alert_id" in alert_dict
    
    def test_alert_from_dict(self):
        """Test alert deserialization from dictionary."""
        alert_data = {
            "alert_id": "test_123",
            "alert_type": "brute_force_attack",
            "threat_level": "high",
            "timestamp": 1234567890.0,
            "description": "Test alert",
            "affected_resources": ["auth/login"],
            "actor": "attacker@evil.com",
            "evidence": {"failed_attempts": 10},
            "recommended_actions": ["Block IP"]
        }
        
        alert = SecurityAlert.from_dict(alert_data)
        
        assert alert.alert_id == "test_123"
        assert alert.alert_type == AlertType.BRUTE_FORCE_ATTACK
        assert alert.threat_level == ThreatLevel.HIGH
        assert alert.timestamp == 1234567890.0
        assert alert.description == "Test alert"
        assert alert.affected_resources == ["auth/login"]
        assert alert.actor == "attacker@evil.com"
        assert alert.evidence["failed_attempts"] == 10
        assert "Block IP" in alert.recommended_actions
    
    def test_get_severity_score(self):
        """Test severity score calculation."""
        critical_alert = SecurityAlert(
            alert_type=AlertType.SYSTEM_COMPROMISE,
            threat_level=ThreatLevel.CRITICAL,
            timestamp=time.time(),
            description="Critical alert",
            affected_resources=["system"]
        )
        
        high_alert = SecurityAlert(
            alert_type=AlertType.BRUTE_FORCE_ATTACK,
            threat_level=ThreatLevel.HIGH,
            timestamp=time.time(),
            description="High alert",
            affected_resources=["auth"]
        )
        
        medium_alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.MEDIUM,
            timestamp=time.time(),
            description="Medium alert",
            affected_resources=["data"]
        )
        
        low_alert = SecurityAlert(
            alert_type=AlertType.TIME_ANOMALY,
            threat_level=ThreatLevel.LOW,
            timestamp=time.time(),
            description="Low alert",
            affected_resources=["access"]
        )
        
        info_alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.INFO,
            timestamp=time.time(),
            description="Info alert",
            affected_resources=["log"]
        )
        
        assert critical_alert.get_severity_score() > high_alert.get_severity_score()
        assert high_alert.get_severity_score() > medium_alert.get_severity_score()
        assert medium_alert.get_severity_score() > low_alert.get_severity_score()
        assert low_alert.get_severity_score() > info_alert.get_severity_score()
    
    def test_is_high_priority(self):
        """Test high priority detection."""
        critical_alert = SecurityAlert(
            alert_type=AlertType.SYSTEM_COMPROMISE,
            threat_level=ThreatLevel.CRITICAL,
            timestamp=time.time(),
            description="Critical alert",
            affected_resources=["system"]
        )
        
        high_alert = SecurityAlert(
            alert_type=AlertType.BRUTE_FORCE_ATTACK,
            threat_level=ThreatLevel.HIGH,
            timestamp=time.time(),
            description="High alert",
            affected_resources=["auth"]
        )
        
        medium_alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.MEDIUM,
            timestamp=time.time(),
            description="Medium alert",
            affected_resources=["data"]
        )
        
        assert critical_alert.is_high_priority() == True
        assert high_alert.is_high_priority() == True
        assert medium_alert.is_high_priority() == False
    
    def test_add_evidence(self):
        """Test adding evidence to alert."""
        alert = SecurityAlert(
            alert_type=AlertType.SUSPICIOUS_KEY_ACCESS,
            threat_level=ThreatLevel.MEDIUM,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["keys"]
        )
        
        assert len(alert.evidence) == 0
        
        alert.add_evidence("key_count", 50)
        alert.add_evidence("time_window", 300)
        
        assert len(alert.evidence) == 2
        assert alert.evidence["key_count"] == 50
        assert alert.evidence["time_window"] == 300
    
    def test_add_recommendation(self):
        """Test adding recommendations to alert."""
        alert = SecurityAlert(
            alert_type=AlertType.MASS_DATA_ACCESS,
            threat_level=ThreatLevel.HIGH,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["data"]
        )
        
        assert len(alert.recommended_actions) == 0
        
        alert.add_recommendation("Investigate actor")
        alert.add_recommendation("Review access patterns")
        
        assert len(alert.recommended_actions) == 2
        assert "Investigate actor" in alert.recommended_actions
    
    def test_add_duplicate_recommendation(self):
        """Test that duplicate recommendations are not added."""
        alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.LOW,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["resource"]
        )
        
        alert.add_recommendation("Review logs")
        alert.add_recommendation("Review logs")  # Duplicate
        
        # Should only have one instance
        assert alert.recommended_actions.count("Review logs") == 1


class TestAlertType:
    """Test suite for AlertType enum."""
    
    def test_alert_types_exist(self):
        """Test that all expected alert types exist."""
        expected_types = [
            "ANOMALY_DETECTED",
            "BRUTE_FORCE_ATTACK",
            "REPLAY_ATTACK_PATTERN",
            "PRIVILEGE_ESCALATION",
            "SUSPICIOUS_KEY_ACCESS",
            "MASS_DATA_ACCESS",
            "MULTIPLE_FAILURES",
            "GEOGRAPHIC_ANOMALY",
            "TIME_ANOMALY",
            "SYSTEM_COMPROMISE"
        ]
        
        for type_name in expected_types:
            assert hasattr(AlertType, type_name)
    
    def test_alert_type_values(self):
        """Test alert type string values."""
        assert AlertType.ANOMALY_DETECTED.value == "anomaly_detected"
        assert AlertType.BRUTE_FORCE_ATTACK.value == "brute_force_attack"
        assert AlertType.REPLAY_ATTACK_PATTERN.value == "replay_attack_pattern"
        assert AlertType.PRIVILEGE_ESCALATION.value == "privilege_escalation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])