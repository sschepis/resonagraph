#!/usr/bin/env python3
"""
Phase 6 Demo: Enhanced Security Monitoring and Compliance

Demonstrates:
- Real-time security monitoring and threat detection
- Automated alert management and escalation
- Compliance reporting (GDPR, SOX, HIPAA, SOC2)
- Advanced log analytics and investigation
- Security incident response workflows
"""

import time
import tempfile
import os
from datetime import datetime, timedelta

from resonagraph.security import (
    # Audit logging
    create_audit_logger,
    AuditEvent,
    AuditEventType,
    AnonymizationLevel,
    
    # Security monitoring
    create_security_monitor,
    ThreatLevel,
    
    # Compliance
    create_compliance_reporter,
    ComplianceFramework,
    ReportFormat,
    
    # Analytics
    create_log_analyzer,
    QueryFilter
)


def demo_threat_detection():
    """Demonstrate real-time threat detection and alerting."""
    print("\n" + "="*80)
    print("PHASE 6A: Real-Time Threat Detection")
    print("="*80)
    
    # Create temporary log file
    log_file = tempfile.mktemp(suffix='.log')
    
    try:
        # Set up audit logger
        audit_logger = create_audit_logger(
            log_file=log_file,
            anonymization_level=AnonymizationLevel.MEDIUM
        )
        
        # Set up security monitor with alerting
        security_monitor = create_security_monitor(
            audit_logger=audit_logger,
            enable_compliance=True
        )
        
        # Start monitoring
        security_monitor.start_monitoring()
        print("✓ Security monitoring started")
        
        # Simulate normal activity
        print("\n1. Simulating normal user activity...")
        for i in range(5):
            event = AuditEvent(
                event_type=AuditEventType.DATA_READ.value,
                timestamp=time.time(),
                resource=f"data/file_{i}.json",
                action="read",
                outcome="success",
                actor="alice@example.com",
                actor_ip="192.168.1.100"
            )
            audit_logger.log_event(event)
            alerts = security_monitor.process_audit_event(event)
            time.sleep(0.1)
        
        print(f"  Logged {5} normal events - no alerts generated")
        
        # Simulate brute force attack
        print("\n2. Simulating brute force attack...")
        for i in range(10):
            event = AuditEvent(
                event_type=AuditEventType.LOGIN_FAILED.value,
                timestamp=time.time(),
                resource="auth/login",
                action="login",
                outcome="failure",
                actor="attacker@evil.com",
                actor_ip="203.0.113.42",
                metadata={"reason": "invalid_password"}
            )
            audit_logger.log_event(event)
            alerts = security_monitor.process_audit_event(event)
            
            if alerts:
                for alert in alerts:
                    print(f"  🚨 ALERT: {alert.description}")
                    print(f"     Threat Level: {alert.threat_level.value.upper()}")
                    print(f"     Affected: {alert.affected_resources}")
            
            time.sleep(0.05)
        
        # Check active alerts
        print("\n3. Checking active alerts...")
        active_alerts = security_monitor.get_active_alerts()
        print(f"  Active alerts: {len(active_alerts)}")
        
        for alert in active_alerts:
            print(f"\n  Alert ID: {alert.alert_id}")
            print(f"  Type: {alert.alert_type.value}")
            print(f"  Severity: {alert.threat_level.value}")
            print(f"  Recommendations:")
            for rec in alert.recommended_actions:
                print(f"    - {rec}")
        
        # Get monitoring statistics
        print("\n4. Security monitoring statistics:")
        status = security_monitor.get_monitoring_status()
        print(f"  Events processed: {status['monitoring_stats']['events_processed']}")
        print(f"  Threats detected: {status['monitoring_stats']['threats_detected']}")
        print(f"  Alerts generated: {status['monitoring_stats']['alerts_generated']}")
        print(f"  Monitoring uptime: {status['uptime_seconds']:.1f} seconds")
        
        # Stop monitoring
        security_monitor.stop_monitoring()
        print("\n✓ Security monitoring stopped")
        
    finally:
        # Cleanup
        if os.path.exists(log_file):
            os.remove(log_file)


def demo_compliance_reporting():
    """Demonstrate compliance reporting for multiple frameworks."""
    print("\n" + "="*80)
    print("PHASE 6B: Compliance Reporting")
    print("="*80)
    
    # Create temporary log file
    log_file = tempfile.mktemp(suffix='.log')
    
    try:
        # Set up audit logger
        audit_logger = create_audit_logger(
            log_file=log_file,
            anonymization_level=AnonymizationLevel.LOW  # Less anonymization for compliance
        )
        
        # Create compliance reporter
        compliance_reporter = create_compliance_reporter(audit_logger)
        
        # Simulate various compliance-relevant events
        print("\n1. Generating compliance-relevant events...")
        
        events = [
            # GDPR: Personal data access
            AuditEvent(
                event_type=AuditEventType.DATA_READ.value,
                timestamp=time.time(),
                resource="customer_personal_data",
                action="read",
                outcome="success",
                actor="analyst@company.com",
                metadata={"record_count": 100}
            ),
            
            # SOX: Financial system access
            AuditEvent(
                event_type=AuditEventType.DATA_WRITE.value,
                timestamp=time.time(),
                resource="financial_ledger",
                action="update",
                outcome="success",
                actor="accountant@company.com",
                metadata={"amount": 50000}
            ),
            
            # HIPAA: PHI access
            AuditEvent(
                event_type=AuditEventType.DATA_READ.value,
                timestamp=time.time(),
                resource="patient_health_records",
                action="read",
                outcome="success",
                actor="doctor@hospital.com",
                metadata={"patient_id": "P12345"}
            ),
            
            # Security event
            AuditEvent(
                event_type=AuditEventType.INTEGRITY_VIOLATION.value,
                timestamp=time.time(),
                resource="critical_system_file",
                action="verify",
                outcome="failure",
                actor="system",
                metadata={"hash_mismatch": True}
            ),
            
            # Unauthorized access attempt
            AuditEvent(
                event_type=AuditEventType.ACCESS_DENIED.value,
                timestamp=time.time(),
                resource="financial_system_admin",
                action="access",
                outcome="failure",
                actor="user@company.com",
                metadata={"required_role": "admin"}
            )
        ]
        
        for event in events:
            audit_logger.log_event(event)
        
        print(f"  Logged {len(events)} compliance-relevant events")
        
        # Generate compliance reports for different frameworks
        frameworks = [
            ComplianceFramework.GDPR,
            ComplianceFramework.SOX,
            ComplianceFramework.HIPAA,
            ComplianceFramework.SOC2
        ]
        
        end_time = time.time()
        start_time = end_time - 3600  # Last hour
        
        for framework in frameworks:
            print(f"\n2. Generating {framework.value.upper()} Compliance Report...")
            
            report = compliance_reporter.generate_compliance_report(
                framework=framework,
                start_time=start_time,
                end_time=end_time,
                output_format=ReportFormat.JSON
            )
            
            print(f"\n  Framework: {framework.value.upper()}")
            print(f"  Report Period: {report['metadata']['report_period']['start']} to")
            print(f"                 {report['metadata']['report_period']['end']}")
            print(f"  Events Analyzed: {report['metadata']['events_analyzed']}")
            print(f"  Violations Detected: {report['metadata']['violations_detected']}")
            
            # Executive summary
            summary = report['executive_summary']
            print(f"\n  Executive Summary:")
            print(f"    Overall Status: {summary['overall_status'].upper()}")
            print(f"    Compliance Score: {summary['compliance_score']:.1f}%")
            print(f"    Risk Level: {summary['risk_level'].upper()}")
            
            if summary['key_findings']:
                print(f"\n  Key Findings:")
                for finding in summary['key_findings']:
                    print(f"    - {finding}")
            
            # Violations
            if report['violations']:
                print(f"\n  Violations:")
                for violation in report['violations']:
                    print(f"    • {violation['rule_id']}: {violation['description']}")
                    print(f"      Severity: {violation['severity'].upper()}")
            
            # Recommendations
            if report['recommendations']:
                print(f"\n  Recommendations:")
                for rec in report['recommendations'][:3]:
                    print(f"    - {rec}")
        
        print("\n✓ Compliance reporting completed")
        
    finally:
        # Cleanup
        if os.path.exists(log_file):
            os.remove(log_file)


def demo_log_analytics():
    """Demonstrate advanced log analytics and investigation."""
    print("\n" + "="*80)
    print("PHASE 6C: Advanced Log Analytics")
    print("="*80)
    
    # Create temporary log file
    log_file = tempfile.mktemp(suffix='.log')
    
    try:
        # Set up audit logger
        audit_logger = create_audit_logger(
            log_file=log_file,
            anonymization_level=AnonymizationLevel.NONE  # No anonymization for demo
        )
        
        # Generate diverse event data
        print("\n1. Generating test event data...")
        actors = ["alice@company.com", "bob@company.com", "charlie@company.com"]
        resources = ["api/users", "api/orders", "api/products", "admin/settings"]
        event_types = [
            AuditEventType.DATA_READ.value,
            AuditEventType.DATA_WRITE.value,
            AuditEventType.LOGIN_SUCCESS.value,
            AuditEventType.LOGIN_FAILED.value
        ]
        
        # Generate 100 events over the last hour
        current_time = time.time()
        for i in range(100):
            import random
            
            event = AuditEvent(
                event_type=random.choice(event_types),
                timestamp=current_time - random.uniform(0, 3600),
                resource=random.choice(resources),
                action="access",
                outcome=random.choice(["success", "success", "success", "failure"]),
                actor=random.choice(actors),
                actor_ip=f"192.168.1.{random.randint(100, 200)}",
                metadata={"request_id": f"req_{i}"}
            )
            audit_logger.log_event(event)
        
        print(f"  Generated 100 test events")
        
        # Create log analyzer
        log_analyzer = create_log_analyzer(log_file)
        
        # Query events
        print("\n2. Querying events with filters...")
        
        # Query for failed events
        failed_filter = QueryFilter(
            outcomes=["failure"],
            start_time=current_time - 3600,
            end_time=current_time
        )
        
        failed_results = log_analyzer.query_events(failed_filter, limit=10)
        print(f"\n  Failed Events Query:")
        print(f"    Total matches: {failed_results.total_count}")
        print(f"    Execution time: {failed_results.execution_time:.3f}s")
        print(f"    Sample events:")
        for event in failed_results.events[:3]:
            print(f"      - {event.event_type} on {event.resource} by {event.actor}")
        
        # Search for specific actor
        print("\n3. Searching for specific patterns...")
        search_results = log_analyzer.search_events(
            search_term="alice",
            fields=["actor"],
            case_sensitive=False
        )
        print(f"\n  Search Results for 'alice':")
        print(f"    Matches found: {search_results.total_count}")
        
        # User behavior analysis
        print("\n4. Analyzing user behavior...")
        user_report = log_analyzer.analyze_user_behavior(
            actor="alice@company.com",
            start_time=current_time - 3600,
            end_time=current_time
        )
        
        print(f"\n  User Behavior Analysis: alice@company.com")
        print(f"    Total events: {user_report.metrics.get('total_events', 0)}")
        print(f"    Unique resources: {user_report.metrics.get('unique_resources', 0)}")
        print(f"    Success rate: {user_report.metrics.get('success_rate', 0):.1f}%")
        
        if user_report.insights:
            print(f"\n    Insights:")
            for insight in user_report.insights:
                print(f"      - {insight}")
        
        if user_report.recommendations:
            print(f"\n    Recommendations:")
            for rec in user_report.recommendations:
                print(f"      - {rec}")
        
        # Security analysis
        print("\n5. Analyzing security events...")
        security_report = log_analyzer.analyze_security_events(
            start_time=current_time - 3600,
            end_time=current_time
        )
        
        print(f"\n  Security Analysis:")
        print(f"    Total security events: {security_report.metrics.get('total_security_events', 0)}")
        
        event_dist = security_report.metrics.get('event_type_distribution', {})
        if event_dist:
            print(f"\n    Event type distribution:")
            for event_type, count in event_dist.items():
                print(f"      {event_type}: {count}")
        
        if security_report.insights:
            print(f"\n    Security Insights:")
            for insight in security_report.insights:
                print(f"      - {insight}")
        
        # Analytics statistics
        print("\n6. Log analyzer statistics:")
        stats = log_analyzer.get_stats()
        print(f"  Queries executed: {stats['queries_executed']}")
        print(f"  Events analyzed: {stats['events_analyzed']}")
        print(f"  Reports generated: {stats['reports_generated']}")
        
        print("\n✓ Log analytics demonstration completed")
        
    finally:
        # Cleanup
        if os.path.exists(log_file):
            os.remove(log_file)


def demo_integrated_security():
    """Demonstrate integrated security monitoring, compliance, and analytics."""
    print("\n" + "="*80)
    print("PHASE 6D: Integrated Security Operations")
    print("="*80)
    
    # Create temporary log file
    log_file = tempfile.mktemp(suffix='.log')
    
    try:
        # Set up complete security infrastructure
        print("\n1. Setting up integrated security infrastructure...")
        
        # Audit logger with hash chain
        audit_logger = create_audit_logger(
            log_file=log_file,
            anonymization_level=AnonymizationLevel.MEDIUM,
            enable_hash_chain=True
        )
        
        # Security monitor with SMTP and webhooks
        security_monitor = create_security_monitor(
            audit_logger=audit_logger,
            smtp_config=None,  # Would be real SMTP config in production
            webhook_urls=[],    # Would be real webhooks in production
            enable_compliance=True
        )
        
        # Log analyzer
        log_analyzer = create_log_analyzer(log_file)
        
        security_monitor.start_monitoring()
        print("  ✓ Security monitoring active")
        print("  ✓ Audit logging with hash chain enabled")
        print("  ✓ Compliance reporting configured")
        print("  ✓ Log analytics ready")
        
        # Simulate security incident
        print("\n2. Simulating security incident...")
        
        # Normal activity
        for i in range(5):
            event = AuditEvent(
                event_type=AuditEventType.DATA_READ.value,
                timestamp=time.time(),
                resource=f"api/data_{i}",
                action="read",
                outcome="success",
                actor="user@company.com"
            )
            audit_logger.log_event(event)
            security_monitor.process_audit_event(event)
            time.sleep(0.05)
        
        # Suspicious activity
        print("  Simulating suspicious access pattern...")
        for i in range(15):
            event = AuditEvent(
                event_type=AuditEventType.KEY_ACCESSED.value,
                timestamp=time.time(),
                resource=f"key_store/key_{i}",
                action="access",
                outcome="success" if i % 3 == 0 else "failure",
                actor="suspicious@external.com",
                actor_ip="198.51.100.42"
            )
            audit_logger.log_event(event)
            alerts = security_monitor.process_audit_event(event)
            time.sleep(0.02)
        
        # Check for alerts
        print("\n3. Reviewing generated alerts...")
        active_alerts = security_monitor.get_active_alerts()
        
        if active_alerts:
            print(f"  {len(active_alerts)} active alerts detected:")
            for alert in active_alerts[:3]:
                print(f"\n    Alert: {alert.alert_id}")
                print(f"    Type: {alert.alert_type.value}")
                print(f"    Threat Level: {alert.threat_level.value.upper()}")
                print(f"    Description: {alert.description}")
        
        # Get alert summary
        print("\n4. Alert summary (last 24 hours)...")
        summary = security_monitor.get_alert_summary(time_window=24*3600)
        print(f"  Total alerts: {summary['total_alerts']}")
        print(f"  Active alerts: {summary['active_alerts']}")
        
        if summary['threat_level_distribution']:
            print(f"\n  Threat level distribution:")
            for level, count in summary['threat_level_distribution'].items():
                print(f"    {level}: {count}")
        
        # Verify log integrity
        print("\n5. Verifying audit log integrity...")
        is_valid = audit_logger.verify_log_integrity()
        print(f"  Log integrity: {'✓ VALID' if is_valid else '✗ COMPROMISED'}")
        
        # Investigation with log analytics
        print("\n6. Forensic investigation with log analytics...")
        
        # Find events from suspicious actor
        suspicious_filter = QueryFilter(
            actors=["suspicious@external.com"]
        )
        results = log_analyzer.query_events(suspicious_filter)
        
        print(f"  Events from suspicious actor: {results.total_count}")
        print(f"  Analysis:")
        
        if results.events:
            event_types = {}
            for event in results.events:
                event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
            
            for event_type, count in event_types.items():
                print(f"    {event_type}: {count} events")
        
        # Final status
        print("\n7. Final security status...")
        status = security_monitor.get_monitoring_status()
        print(f"  Monitoring uptime: {status['uptime_seconds']:.1f}s")
        print(f"  Events processed: {status['monitoring_stats']['events_processed']}")
        print(f"  Threats detected: {status['monitoring_stats']['threats_detected']}")
        print(f"  Alerts generated: {status['monitoring_stats']['alerts_generated']}")
        
        # Stop monitoring
        security_monitor.stop_monitoring()
        print("\n✓ Integrated security demonstration completed")
        
    finally:
        # Cleanup
        if os.path.exists(log_file):
            os.remove(log_file)


def main():
    """Run all Phase 6 security demonstrations."""
    print("\n" + "="*80)
    print("ResonaGraph Phase 6: Enhanced Security Infrastructure")
    print("Advanced Monitoring, Compliance, and Analytics")
    print("="*80)
    
    try:
        # Run demonstrations
        demo_threat_detection()
        demo_compliance_reporting()
        demo_log_analytics()
        demo_integrated_security()
        
        print("\n" + "="*80)
        print("Phase 6 Security Demo Complete!")
        print("="*80)
        print("\nKey Features Demonstrated:")
        print("  ✓ Real-time threat detection with pattern matching")
        print("  ✓ Automated alert generation and escalation")
        print("  ✓ Multi-framework compliance reporting (GDPR, SOX, HIPAA, SOC2)")
        print("  ✓ Advanced log analytics and querying")
        print("  ✓ User behavior analysis and profiling")
        print("  ✓ Security incident investigation workflows")
        print("  ✓ Tamper-evident audit logging with hash chains")
        print("  ✓ Integrated security operations center (SOC) capabilities")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        raise


if __name__ == "__main__":
    main()