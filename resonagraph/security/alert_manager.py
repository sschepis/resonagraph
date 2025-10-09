"""
Alert management and notification system for ResonaGraph security.

Handles alert routing, escalation, and integration with external
monitoring systems including email, webhooks, and SIEM platforms.
"""

import time
import threading
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict

from resonagraph.security.alerts import SecurityAlert, AlertType
from resonagraph.security.threat_detection import ThreatLevel


class AlertManager:
    """
    Manages security alerts and notifications.
    
    Handles alert routing, escalation, and integration with external
    monitoring systems.
    """
    
    def __init__(
        self,
        smtp_config: Optional[Dict[str, Any]] = None,
        webhook_urls: Optional[List[str]] = None,
        escalation_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize alert manager.
        
        Args:
            smtp_config: SMTP configuration for email alerts
            webhook_urls: Webhook URLs for external integrations
            escalation_config: Custom escalation rules
        """
        self.smtp_config = smtp_config
        self.webhook_urls = webhook_urls or []
        
        # Alert storage and tracking
        self._active_alerts: Dict[str, SecurityAlert] = {}
        self._alert_history: List[SecurityAlert] = []
        
        # Escalation rules
        self._escalation_rules = escalation_config or self._default_escalation_rules()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'alerts_processed': 0,
            'notifications_sent': 0,
            'escalations_triggered': 0,
            'active_alerts': 0
        }
    
    def _default_escalation_rules(self) -> Dict[ThreatLevel, Dict[str, Any]]:
        """Get default escalation rules."""
        return {
            ThreatLevel.CRITICAL: {
                "immediate_notify": True,
                "escalate_after": 0,  # Immediate escalation
                "notify_channels": ["email", "webhook", "sms"]
            },
            ThreatLevel.HIGH: {
                "immediate_notify": True,
                "escalate_after": 300,  # 5 minutes
                "notify_channels": ["email", "webhook"]
            },
            ThreatLevel.MEDIUM: {
                "immediate_notify": False,
                "escalate_after": 1800,  # 30 minutes
                "notify_channels": ["webhook"]
            },
            ThreatLevel.LOW: {
                "immediate_notify": False,
                "escalate_after": 3600,  # 1 hour
                "notify_channels": ["webhook"]
            },
            ThreatLevel.INFO: {
                "immediate_notify": False,
                "escalate_after": 0,  # No escalation
                "notify_channels": []
            }
        }
    
    def process_alert(self, alert: SecurityAlert) -> None:
        """
        Process a security alert.
        
        Args:
            alert: Security alert to process
        """
        with self._lock:
            # Add to active alerts
            self._active_alerts[alert.alert_id] = alert
            self._alert_history.append(alert)
            
            # Update statistics
            self.stats['alerts_processed'] += 1
            self.stats['active_alerts'] = len(self._active_alerts)
            
            # Apply escalation rules
            rules = self._escalation_rules.get(alert.threat_level, {})
            
            if rules.get("immediate_notify", False):
                self._send_notifications(alert, rules.get("notify_channels", []))
            
            # Schedule escalation if needed
            escalate_after = rules.get("escalate_after", 0)
            if escalate_after > 0:
                # In a real implementation, this would use a proper scheduler
                threading.Timer(escalate_after, self._escalate_alert, args=[alert.alert_id]).start()
    
    def _send_notifications(self, alert: SecurityAlert, channels: List[str]) -> None:
        """Send notifications through specified channels."""
        for channel in channels:
            try:
                if channel == "email" and self.smtp_config:
                    self._send_email_notification(alert)
                elif channel == "webhook":
                    self._send_webhook_notifications(alert)
                # SMS integration would go here
                
                self.stats['notifications_sent'] += 1
            
            except Exception as e:
                # Log error but continue with other channels
                import logging
                logging.getLogger('resonagraph.alert_manager').error(
                    f"Failed to send notification via {channel}: {e}"
                )
    
    def _send_email_notification(self, alert: SecurityAlert) -> None:
        """Send email notification for alert."""
        if not self.smtp_config:
            return
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = self.smtp_config['from_email']
        msg['To'] = self.smtp_config['to_email']
        msg['Subject'] = f"Security Alert: {alert.threat_level.value.upper()} - {alert.alert_type.value}"
        
        # Create email body
        body = f"""
Security Alert Generated

Alert ID: {alert.alert_id}
Threat Level: {alert.threat_level.value.upper()}
Alert Type: {alert.alert_type.value}
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(alert.timestamp))}

Description:
{alert.description}

Affected Resources:
{', '.join(alert.affected_resources)}

Actor: {alert.actor or 'Unknown'}

Evidence:
{json.dumps(alert.evidence, indent=2)}

Recommended Actions:
{chr(10).join(f"- {action}" for action in alert.recommended_actions)}

--
ResonaGraph Security Monitoring System
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['smtp_port']) as server:
            if self.smtp_config.get('use_tls', True):
                server.starttls()
            if 'username' in self.smtp_config:
                server.login(self.smtp_config['username'], self.smtp_config['password'])
            server.send_message(msg)
    
    def _send_webhook_notifications(self, alert: SecurityAlert) -> None:
        """Send webhook notifications for alert."""
        if not self.webhook_urls:
            return
        
        # Create webhook payload
        payload = alert.to_dict()
        
        # Send to all webhook URLs
        try:
            import requests
            
            for url in self.webhook_urls:
                try:
                    requests.post(url, json=payload, timeout=10)
                except Exception as e:
                    import logging
                    logging.getLogger('resonagraph.alert_manager').warning(
                        f"Failed to send webhook to {url}: {e}"
                    )
        except ImportError:
            # requests not available, skip webhook notifications
            pass
    
    def _escalate_alert(self, alert_id: str) -> None:
        """Escalate an alert if it's still active."""
        with self._lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                
                # Escalate threat level
                if alert.threat_level == ThreatLevel.LOW:
                    alert.threat_level = ThreatLevel.MEDIUM
                elif alert.threat_level == ThreatLevel.MEDIUM:
                    alert.threat_level = ThreatLevel.HIGH
                elif alert.threat_level == ThreatLevel.HIGH:
                    alert.threat_level = ThreatLevel.CRITICAL
                
                # Send escalated notifications
                rules = self._escalation_rules.get(alert.threat_level, {})
                self._send_notifications(alert, rules.get("notify_channels", []))
                
                self.stats['escalations_triggered'] += 1
    
    def resolve_alert(self, alert_id: str, resolution_notes: Optional[str] = None) -> bool:
        """
        Mark an alert as resolved.
        
        Args:
            alert_id: ID of alert to resolve
            resolution_notes: Optional notes about resolution
            
        Returns:
            True if alert was found and resolved
        """
        with self._lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts.pop(alert_id)
                
                # Add resolution metadata
                alert.add_evidence('resolved_at', time.time())
                if resolution_notes:
                    alert.add_evidence('resolution_notes', resolution_notes)
                
                self.stats['active_alerts'] = len(self._active_alerts)
                return True
        
        return False
    
    def get_active_alerts(self, threat_level: Optional[ThreatLevel] = None) -> List[SecurityAlert]:
        """Get list of active alerts, optionally filtered by threat level."""
        with self._lock:
            alerts = list(self._active_alerts.values())
            
            if threat_level:
                alerts = [a for a in alerts if a.threat_level == threat_level]
            
            # Sort by threat level and timestamp
            alerts.sort(key=lambda a: (a.get_severity_score(), a.timestamp), reverse=True)
            return alerts
    
    def get_alert_history(
        self,
        limit: Optional[int] = None,
        threat_level: Optional[ThreatLevel] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[SecurityAlert]:
        """
        Get alert history with optional filtering.
        
        Args:
            limit: Maximum number of alerts to return
            threat_level: Filter by threat level
            start_time: Filter alerts after this timestamp
            end_time: Filter alerts before this timestamp
            
        Returns:
            List of historical alerts
        """
        with self._lock:
            alerts = list(self._alert_history)
            
            # Apply filters
            if threat_level:
                alerts = [a for a in alerts if a.threat_level == threat_level]
            
            if start_time:
                alerts = [a for a in alerts if a.timestamp >= start_time]
            
            if end_time:
                alerts = [a for a in alerts if a.timestamp <= end_time]
            
            # Sort by timestamp (newest first)
            alerts.sort(key=lambda a: a.timestamp, reverse=True)
            
            # Apply limit
            if limit:
                alerts = alerts[:limit]
            
            return alerts
    
    def get_alert_summary(self, time_window: float = 24 * 3600) -> Dict[str, Any]:
        """
        Get summary of alerts in the specified time window.
        
        Args:
            time_window: Time window in seconds (default: 24 hours)
            
        Returns:
            Alert summary statistics
        """
        current_time = time.time()
        start_time = current_time - time_window
        
        recent_alerts = self.get_alert_history(start_time=start_time)
        
        # Count by threat level
        threat_counts = defaultdict(int)
        for alert in recent_alerts:
            threat_counts[alert.threat_level.value] += 1
        
        # Count by alert type
        type_counts = defaultdict(int)
        for alert in recent_alerts:
            type_counts[alert.alert_type.value] += 1
        
        # Most affected resources
        resource_counts = defaultdict(int)
        for alert in recent_alerts:
            for resource in alert.affected_resources:
                resource_counts[resource] += 1
        
        # Most active actors
        actor_counts = defaultdict(int)
        for alert in recent_alerts:
            if alert.actor:
                actor_counts[alert.actor] += 1
        
        return {
            'time_window_hours': time_window / 3600,
            'total_alerts': len(recent_alerts),
            'active_alerts': len(self._active_alerts),
            'threat_level_distribution': dict(threat_counts),
            'alert_type_distribution': dict(type_counts),
            'top_affected_resources': dict(sorted(resource_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'top_actors': dict(sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'stats': self.get_stats()
        }
    
    def configure_escalation_rules(self, rules: Dict[ThreatLevel, Dict[str, Any]]) -> None:
        """
        Configure custom escalation rules.
        
        Args:
            rules: Escalation rules by threat level
        """
        with self._lock:
            self._escalation_rules.update(rules)
    
    def add_webhook_url(self, url: str) -> None:
        """Add a webhook URL for notifications."""
        if url not in self.webhook_urls:
            self.webhook_urls.append(url)
    
    def remove_webhook_url(self, url: str) -> bool:
        """Remove a webhook URL."""
        if url in self.webhook_urls:
            self.webhook_urls.remove(url)
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get alert manager statistics."""
        return self.stats.copy()