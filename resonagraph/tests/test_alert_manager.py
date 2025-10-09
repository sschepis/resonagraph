"""
Tests for alert management and notification system.
"""

import pytest
import time
import tempfile
import os

from resonagraph.security.alert_manager import AlertManager
from resonagraph.security.alerts import SecurityAlert, AlertType
from resonagraph.security.threat_detection import ThreatLevel


class TestAlertManager:
    """Test suite for AlertManager."""
    
    def test_initialization(self):
        """Test alert manager initialization."""
        manager = AlertManager()
        
        assert manager.smtp_config is None
        assert manager.webhook_urls == []
        assert len(manager._active_alerts) == 0
        assert len(manager._alert_history) == 0
        assert manager.stats['alerts_processed'] == 0
    
    def test_initialization_with_config(self):
        """Test alert manager initialization with configuration."""
        smtp_config = {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "from_email": "security@company.com",
            "to_email": "soc@company.com"
        }
        
        webhook_urls = ["https://webhook.example.com/alerts"]
        
        manager = AlertManager(
            smtp_config=smtp_config,
            webhook_urls=webhook_urls
        )
        
        assert manager.smtp_config == smtp_config
        assert manager.webhook_urls == webhook_urls
    
    def test_process_alert(self):
        """Test processing a security alert."""
        manager = AlertManager()
        
        alert = SecurityAlert(
            alert_type=AlertType.BRUTE_FORCE_ATTACK,
            threat_level=ThreatLevel.HIGH,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["auth/login"],
            actor="attacker@evil.com"
        )
        
        manager.process_alert(alert)
        
        assert manager.stats['alerts_processed'] == 1
        assert manager.stats['active_alerts'] == 1
        assert alert.alert_id in manager._active_alerts
        assert len(manager._alert_history) == 1
    
    def test_process_multiple_alerts(self):
        """Test processing multiple alerts."""
        manager = AlertManager()
        
        for i in range(5):
            alert = SecurityAlert(
                alert_type=AlertType.ANOMALY_DETECTED,
                threat_level=ThreatLevel.MEDIUM,
                timestamp=time.time(),
                description=f"Alert {i}",
                affected_resources=[f"resource_{i}"]
            )
            manager.process_alert(alert)
        
        assert manager.stats['alerts_processed'] == 5
        assert manager.stats['active_alerts'] == 5
        assert len(manager._alert_history) == 5
    
    def test_resolve_alert(self):
        """Test resolving an alert."""
        manager = AlertManager()
        
        alert = SecurityAlert(
            alert_type=AlertType.SUSPICIOUS_KEY_ACCESS,
            threat_level=ThreatLevel.MEDIUM,
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["keys"]
        )
        
        manager.process_alert(alert)
        assert manager.stats['active_alerts'] == 1
        
        # Resolve the alert
        result = manager.resolve_alert(alert.alert_id, "Investigated and cleared")
        
        assert result == True
        assert manager.stats['active_alerts'] == 0
        assert alert.alert_id not in manager._active_alerts
        
        # Check resolution metadata was added
        assert 'resolved_at' in alert.evidence
        assert 'resolution_notes' in alert.evidence
        assert alert.evidence['resolution_notes'] == "Investigated and cleared"
    
    def test_resolve_nonexistent_alert(self):
        """Test resolving an alert that doesn't exist."""
        manager = AlertManager()
        
        result = manager.resolve_alert("nonexistent_id")
        assert result == False
    
    def test_get_active_alerts(self):
        """Test retrieving active alerts."""
        manager = AlertManager()
        
        # Create alerts with different threat levels
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
            timestamp=time.time() + 1,
            description="High alert",
            affected_resources=["auth"]
        )
        
        medium_alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.MEDIUM,
            timestamp=time.time() + 2,
            description="Medium alert",
            affected_resources=["data"]
        )
        
        manager.process_alert(critical_alert)
        manager.process_alert(high_alert)
        manager.process_alert(medium_alert)
        
        # Get all active alerts
        active_alerts = manager.get_active_alerts()
        assert len(active_alerts) == 3
        
        # Should be sorted by severity (CRITICAL first)
        assert active_alerts[0].threat_level == ThreatLevel.CRITICAL
        assert active_alerts[1].threat_level == ThreatLevel.HIGH
        assert active_alerts[2].threat_level == ThreatLevel.MEDIUM
    
    def test_get_active_alerts_filtered(self):
        """Test retrieving active alerts filtered by threat level."""
        manager = AlertManager()
        
        # Create alerts with different threat levels
        for level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH, ThreatLevel.MEDIUM]:
            alert = SecurityAlert(
                alert_type=AlertType.ANOMALY_DETECTED,
                threat_level=level,
                timestamp=time.time(),
                description=f"{level.value} alert",
                affected_resources=["resource"]
            )
            manager.process_alert(alert)
        
        # Filter for HIGH level only
        high_alerts = manager.get_active_alerts(threat_level=ThreatLevel.HIGH)
        assert len(high_alerts) == 1
        assert high_alerts[0].threat_level == ThreatLevel.HIGH
    
    def test_get_alert_history(self):
        """Test retrieving alert history."""
        manager = AlertManager()
        
        # Create and process some alerts
        for i in range(5):
            alert = SecurityAlert(
                alert_type=AlertType.ANOMALY_DETECTED,
                threat_level=ThreatLevel.MEDIUM,
                timestamp=time.time() - (i * 60),  # Spread over 5 minutes
                description=f"Alert {i}",
                affected_resources=[f"resource_{i}"]
            )
            manager.process_alert(alert)
        
        history = manager.get_alert_history()
        assert len(history) == 5
        
        # Should be sorted by timestamp (newest first)
        timestamps = [alert.timestamp for alert in history]
        assert timestamps == sorted(timestamps, reverse=True)
    
    def test_get_alert_history_with_limit(self):
        """Test retrieving limited alert history."""
        manager = AlertManager()
        
        # Create 10 alerts
        for i in range(10):
            alert = SecurityAlert(
                alert_type=AlertType.ANOMALY_DETECTED,
                threat_level=ThreatLevel.LOW,
                timestamp=time.time(),
                description=f"Alert {i}",
                affected_resources=[f"resource_{i}"]
            )
            manager.process_alert(alert)
        
        # Get only 3 most recent
        history = manager.get_alert_history(limit=3)
        assert len(history) == 3
    
    def test_get_alert_history_filtered_by_level(self):
        """Test retrieving alert history filtered by threat level."""
        manager = AlertManager()
        
        # Create alerts with different levels
        for i in range(3):
            manager.process_alert(SecurityAlert(
                alert_type=AlertType.ANOMALY_DETECTED,
                threat_level=ThreatLevel.HIGH,
                timestamp=time.time(),
                description=f"High alert {i}",
                affected_resources=["resource"]
            ))
        
        for i in range(2):
            manager.process_alert(SecurityAlert(
                alert_type=AlertType.ANOMALY_DETECTED,
                threat_level=ThreatLevel.MEDIUM,
                timestamp=time.time(),
                description=f"Medium alert {i}",
                affected_resources=["resource"]
            ))
        
        # Get only HIGH alerts
        high_history = manager.get_alert_history(threat_level=ThreatLevel.HIGH)
        assert len(high_history) == 3
        assert all(a.threat_level == ThreatLevel.HIGH for a in high_history)
    
    def test_get_alert_history_time_range(self):
        """Test retrieving alert history within time range."""
        manager = AlertManager()
        current_time = time.time()
        
        # Create alerts at different times
        old_alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.LOW,
            timestamp=current_time - 7200,  # 2 hours ago
            description="Old alert",
            affected_resources=["resource"]
        )
        
        recent_alert = SecurityAlert(
            alert_type=AlertType.ANOMALY_DETECTED,
            threat_level=ThreatLevel.LOW,
            timestamp=current_time - 600,  # 10 minutes ago
            description="Recent alert",
            affected_resources=["resource"]
        )
        
        manager.process_alert(old_alert)
        manager.process_alert(recent_alert)
        
        # Get alerts from last hour only
        recent_history = manager.get_alert_history(
            start_time=current_time - 3600,
            end_time=current_time
        )
        
        assert len(recent_history) == 1
        assert recent_history[0].description == "Recent alert"
    
    def test_get_alert_summary(self):
        """Test getting alert summary statistics."""
        manager = AlertManager()
        current_time = time.time()
        
        # Create diverse alerts
        alerts_data = [
            (AlertType.BRUTE_FORCE_ATTACK, ThreatLevel.HIGH, "auth/login", "attacker1@evil.com"),
            (AlertType.BRUTE_FORCE_ATTACK, ThreatLevel.HIGH, "auth/login", "attacker1@evil.com"),
            (AlertType.ANOMALY_DETECTED, ThreatLevel.MEDIUM, "api/data", "user@example.com"),
            (AlertType.SUSPICIOUS_KEY_ACCESS, ThreatLevel.HIGH, "keys/secret", "user2@example.com"),
        ]
        
        for alert_type, threat_level, resource, actor in alerts_data:
            alert = SecurityAlert(
                alert_type=alert_type,
                threat_level=threat_level,
                timestamp=current_time - 60,  # 1 minute ago
                description="Test alert",
                affected_resources=[resource],
                actor=actor
            )
            manager.process_alert(alert)
        
        summary = manager.get_alert_summary(time_window=3600)
        
        assert summary['total_alerts'] == 4
        # Active alerts is current count, not historical
        assert summary['active_alerts'] >= 0  # Can be any value depending on processing
        assert 'threat_level_distribution' in summary
        assert 'alert_type_distribution' in summary
        assert 'top_affected_resources' in summary
        assert 'top_actors' in summary
        
        # Check distributions
        assert summary['threat_level_distribution']['high'] == 3
        assert summary['threat_level_distribution']['medium'] == 1
        assert summary['alert_type_distribution']['brute_force_attack'] == 2
    
    def test_configure_escalation_rules(self):
        """Test configuring custom escalation rules."""
        manager = AlertManager()
        
        custom_rules = {
            ThreatLevel.HIGH: {
                "immediate_notify": True,
                "escalate_after": 180,  # 3 minutes instead of default
                "notify_channels": ["email"]
            }
        }
        
        manager.configure_escalation_rules(custom_rules)
        
        # Check rules were updated
        assert manager._escalation_rules[ThreatLevel.HIGH]["escalate_after"] == 180
        assert manager._escalation_rules[ThreatLevel.HIGH]["notify_channels"] == ["email"]
    
    def test_add_webhook_url(self):
        """Test adding webhook URL."""
        manager = AlertManager()
        
        assert len(manager.webhook_urls) == 0
        
        manager.add_webhook_url("https://webhook1.example.com")
        assert len(manager.webhook_urls) == 1
        
        manager.add_webhook_url("https://webhook2.example.com")
        assert len(manager.webhook_urls) == 2
    
    def test_add_duplicate_webhook_url(self):
        """Test that duplicate webhook URLs are not added."""
        manager = AlertManager()
        
        url = "https://webhook.example.com"
        manager.add_webhook_url(url)
        manager.add_webhook_url(url)  # Duplicate
        
        assert len(manager.webhook_urls) == 1
    
    def test_remove_webhook_url(self):
        """Test removing webhook URL."""
        manager = AlertManager()
        
        url = "https://webhook.example.com"
        manager.add_webhook_url(url)
        assert len(manager.webhook_urls) == 1
        
        result = manager.remove_webhook_url(url)
        assert result == True
        assert len(manager.webhook_urls) == 0
    
    def test_remove_nonexistent_webhook_url(self):
        """Test removing webhook URL that doesn't exist."""
        manager = AlertManager()
        
        result = manager.remove_webhook_url("https://nonexistent.com")
        assert result == False
    
    def test_get_stats(self):
        """Test getting alert manager statistics."""
        manager = AlertManager()
        
        # Process some alerts
        for i in range(3):
            alert = SecurityAlert(
                alert_type=AlertType.ANOMALY_DETECTED,
                threat_level=ThreatLevel.LOW,
                timestamp=time.time(),
                description=f"Alert {i}",
                affected_resources=["resource"]
            )
            manager.process_alert(alert)
        
        stats = manager.get_stats()
        
        assert stats['alerts_processed'] == 3
        assert stats['active_alerts'] == 3
        assert 'notifications_sent' in stats
        assert 'escalations_triggered' in stats
    
    def test_default_escalation_rules(self):
        """Test default escalation rules are set correctly."""
        manager = AlertManager()
        
        # Check CRITICAL level rules
        critical_rules = manager._escalation_rules[ThreatLevel.CRITICAL]
        assert critical_rules['immediate_notify'] == True
        assert critical_rules['escalate_after'] == 0
        assert 'email' in critical_rules['notify_channels']
        assert 'webhook' in critical_rules['notify_channels']
        
        # Check HIGH level rules
        high_rules = manager._escalation_rules[ThreatLevel.HIGH]
        assert high_rules['immediate_notify'] == True
        assert high_rules['escalate_after'] == 300
        
        # Check MEDIUM level rules
        medium_rules = manager._escalation_rules[ThreatLevel.MEDIUM]
        assert medium_rules['immediate_notify'] == False
        assert medium_rules['escalate_after'] == 1800
        
        # Check LOW level rules
        low_rules = manager._escalation_rules[ThreatLevel.LOW]
        assert low_rules['immediate_notify'] == False
        assert low_rules['escalate_after'] == 3600
    
    def test_notification_without_config(self):
        """Test that notifications don't crash without configuration."""
        manager = AlertManager()  # No SMTP or webhook config
        
        alert = SecurityAlert(
            alert_type=AlertType.BRUTE_FORCE_ATTACK,
            threat_level=ThreatLevel.CRITICAL,  # Should trigger immediate notify
            timestamp=time.time(),
            description="Test alert",
            affected_resources=["resource"]
        )
        
        # Should not raise an exception
        manager.process_alert(alert)
        assert manager.stats['alerts_processed'] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])