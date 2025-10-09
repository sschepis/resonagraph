"""
Main security monitoring coordinator for ResonaGraph.

Combines threat detection, alert management, and compliance reporting
for comprehensive security monitoring and incident response.
"""

import time
import threading
from typing import Dict, List, Optional, Any

from resonagraph.security.audit import AuditEvent
from resonagraph.security.threat_detection import ThreatDetector
from resonagraph.security.alert_manager import AlertManager
from resonagraph.security.compliance import ComplianceReporter, ComplianceFramework


class SecurityMonitor:
    """
    Main security monitoring coordinator.
    
    Combines threat detection and alert management for comprehensive
    security monitoring.
    """
    
    def __init__(
        self,
        threat_detector: Optional[ThreatDetector] = None,
        alert_manager: Optional[AlertManager] = None,
        compliance_reporter: Optional[ComplianceReporter] = None
    ):
        """
        Initialize security monitor.
        
        Args:
            threat_detector: Threat detection engine
            alert_manager: Alert management system
            compliance_reporter: Compliance reporting system
        """
        self.threat_detector = threat_detector or ThreatDetector()
        self.alert_manager = alert_manager or AlertManager()
        self.compliance_reporter = compliance_reporter
        
        # Connect threat detector to alert manager
        self.threat_detector.alert_callback = self.alert_manager.process_alert
        
        # Monitoring state
        self._is_running = False
        self._baseline_update_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.stats = {
            'monitoring_uptime': 0,
            'events_processed': 0,
            'threats_detected': 0,
            'alerts_generated': 0
        }
        
        self._start_time = time.time()
    
    def start_monitoring(self) -> None:
        """Start security monitoring."""
        if self._is_running:
            return
        
        self._is_running = True
        self._start_time = time.time()
        
        # Start baseline update thread
        self._baseline_update_thread = threading.Thread(
            target=self._baseline_update_loop,
            daemon=True
        )
        self._baseline_update_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop security monitoring."""
        self._is_running = False
        
        if self._baseline_update_thread:
            self._baseline_update_thread.join(timeout=1.0)
    
    def process_audit_event(self, event: AuditEvent) -> List:
        """
        Process an audit event for security monitoring.
        
        Args:
            event: Audit event to analyze
            
        Returns:
            List of security alerts generated
        """
        self.stats['events_processed'] += 1
        
        # Analyze event for threats
        alerts = self.threat_detector.analyze_event(event)
        
        # Update statistics
        high_priority_alerts = [a for a in alerts if a.is_high_priority()]
        self.stats['threats_detected'] += len(high_priority_alerts)
        self.stats['alerts_generated'] += len(alerts)
        
        return alerts
    
    def _baseline_update_loop(self) -> None:
        """Background thread for updating baselines."""
        while self._is_running:
            try:
                # Update baselines every hour
                time.sleep(3600)
                if self._is_running:
                    self.threat_detector.update_baselines()
            except Exception:
                # Log error and continue
                pass
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get comprehensive monitoring status."""
        uptime = time.time() - self._start_time if self._is_running else 0
        
        status = {
            'is_running': self._is_running,
            'uptime_seconds': uptime,
            'threat_detector_stats': self.threat_detector.get_stats(),
            'alert_manager_stats': self.alert_manager.get_stats(),
            'monitoring_stats': self.stats.copy()
        }
        
        if self.compliance_reporter:
            status['compliance_reporter_stats'] = self.compliance_reporter.get_stats()
        
        return status
    
    def get_active_alerts(self, threat_level=None):
        """Get active security alerts."""
        return self.alert_manager.get_active_alerts(threat_level)
    
    def resolve_alert(self, alert_id: str, resolution_notes: Optional[str] = None) -> bool:
        """Mark an alert as resolved."""
        return self.alert_manager.resolve_alert(alert_id, resolution_notes)
    
    def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        start_time: float,
        end_time: float,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Generate compliance report if compliance reporter is available.
        
        Args:
            framework: Compliance framework
            start_time: Report start time
            end_time: Report end time
            **kwargs: Additional arguments for report generation
            
        Returns:
            Compliance report or None if no reporter configured
        """
        if self.compliance_reporter:
            return self.compliance_reporter.generate_compliance_report(
                framework, start_time, end_time, **kwargs
            )
        return None
    
    def get_alert_summary(self, time_window: float = 24 * 3600) -> Dict[str, Any]:
        """Get summary of recent alerts."""
        return self.alert_manager.get_alert_summary(time_window)
    
    def configure_alerting(
        self,
        smtp_config: Optional[Dict[str, Any]] = None,
        webhook_urls: Optional[List[str]] = None,
        escalation_rules: Optional[Dict] = None
    ) -> None:
        """
        Configure alerting settings.
        
        Args:
            smtp_config: SMTP configuration for email alerts
            webhook_urls: Webhook URLs for notifications
            escalation_rules: Custom escalation rules
        """
        if smtp_config:
            self.alert_manager.smtp_config = smtp_config
        
        if webhook_urls:
            self.alert_manager.webhook_urls = webhook_urls
        
        if escalation_rules:
            self.alert_manager.configure_escalation_rules(escalation_rules)


# Factory function for easy setup
def create_security_monitor(
    audit_logger=None,
    smtp_config: Optional[Dict[str, Any]] = None,
    webhook_urls: Optional[List[str]] = None,
    enable_compliance: bool = False
) -> SecurityMonitor:
    """
    Create security monitor with specified configuration.
    
    Args:
        audit_logger: Audit logger for compliance reporting
        smtp_config: SMTP configuration for email alerts
        webhook_urls: Webhook URLs for notifications
        enable_compliance: Enable compliance reporting
        
    Returns:
        Configured security monitor
    """
    # Create components
    threat_detector = ThreatDetector()
    alert_manager = AlertManager(smtp_config=smtp_config, webhook_urls=webhook_urls)
    
    compliance_reporter = None
    if enable_compliance and audit_logger:
        from resonagraph.security.compliance import create_compliance_reporter
        compliance_reporter = create_compliance_reporter(audit_logger)
    
    return SecurityMonitor(
        threat_detector=threat_detector,
        alert_manager=alert_manager,
        compliance_reporter=compliance_reporter
    )