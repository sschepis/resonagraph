"""
Compliance reporting and audit log analysis for ResonaGraph.

Provides SOX, GDPR, HIPAA, and other regulatory compliance reporting
capabilities with automated analysis and export functionality.
"""

import json
import csv
import time
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple, TextIO
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import logging
from collections import defaultdict, Counter

from resonagraph.security.audit import AuditEvent, AuditEventType, AuditLogger


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    SOX = "sox"              # Sarbanes-Oxley Act
    GDPR = "gdpr"            # General Data Protection Regulation
    HIPAA = "hipaa"          # Health Insurance Portability and Accountability Act
    SOC2 = "soc2"            # Service Organization Control 2
    PCI_DSS = "pci_dss"      # Payment Card Industry Data Security Standard
    ISO27001 = "iso27001"    # ISO/IEC 27001
    NIST = "nist"            # NIST Cybersecurity Framework


class ReportFormat(Enum):
    """Report output formats."""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"


@dataclass
class ComplianceViolation:
    """Represents a compliance violation."""
    framework: ComplianceFramework
    rule_id: str
    severity: str  # low, medium, high, critical
    description: str
    events: List[AuditEvent]
    timestamp: float
    resource: str
    actor: Optional[str] = None
    remediation_steps: List[str] = None
    
    def __post_init__(self):
        if self.remediation_steps is None:
            self.remediation_steps = []


@dataclass
class ComplianceMetric:
    """Compliance metric for reporting."""
    metric_name: str
    current_value: Any
    threshold: Any
    status: str  # compliant, non_compliant, warning
    description: str
    measurement_time: float


class ComplianceRuleEngine:
    """
    Engine for evaluating compliance rules against audit events.
    
    Implements rules for various compliance frameworks and generates
    violation reports.
    """
    
    def __init__(self):
        """Initialize compliance rule engine."""
        self.rules = self._initialize_compliance_rules()
        self.stats = {
            'events_evaluated': 0,
            'violations_detected': 0,
            'rules_executed': 0
        }
    
    def evaluate_events(
        self,
        events: List[AuditEvent],
        frameworks: Optional[List[ComplianceFramework]] = None
    ) -> List[ComplianceViolation]:
        """
        Evaluate events against compliance rules.
        
        Args:
            events: List of audit events to evaluate
            frameworks: Specific frameworks to check (all if None)
            
        Returns:
            List of compliance violations detected
        """
        violations = []
        frameworks = frameworks or list(ComplianceFramework)
        
        for framework in frameworks:
            framework_rules = self.rules.get(framework, [])
            
            for rule in framework_rules:
                self.stats['rules_executed'] += 1
                rule_violations = rule['evaluator'](events)
                violations.extend(rule_violations)
        
        self.stats['events_evaluated'] += len(events)
        self.stats['violations_detected'] += len(violations)
        
        return violations
    
    def _initialize_compliance_rules(self) -> Dict[ComplianceFramework, List[Dict]]:
        """Initialize compliance rules for each framework."""
        rules = {}
        
        # SOX Rules
        rules[ComplianceFramework.SOX] = [
            {
                'rule_id': 'SOX-404.1',
                'description': 'Unauthorized access to financial data',
                'evaluator': self._check_sox_unauthorized_access
            },
            {
                'rule_id': 'SOX-302.1',
                'description': 'Changes to financial systems without approval',
                'evaluator': self._check_sox_unauthorized_changes
            }
        ]
        
        # GDPR Rules
        rules[ComplianceFramework.GDPR] = [
            {
                'rule_id': 'GDPR-32.1',
                'description': 'Personal data access without proper authorization',
                'evaluator': self._check_gdpr_unauthorized_data_access
            },
            {
                'rule_id': 'GDPR-33.1',
                'description': 'Data breach notification requirements',
                'evaluator': self._check_gdpr_breach_notification
            }
        ]
        
        # HIPAA Rules
        rules[ComplianceFramework.HIPAA] = [
            {
                'rule_id': 'HIPAA-164.312',
                'description': 'Unauthorized access to PHI',
                'evaluator': self._check_hipaa_phi_access
            }
        ]
        
        # SOC2 Rules
        rules[ComplianceFramework.SOC2] = [
            {
                'rule_id': 'SOC2-CC6.1',
                'description': 'Logical access controls',
                'evaluator': self._check_soc2_access_controls
            }
        ]
        
        return rules
    
    def _check_sox_unauthorized_access(self, events: List[AuditEvent]) -> List[ComplianceViolation]:
        """Check for SOX unauthorized access violations."""
        violations = []
        
        # Look for access denied events to financial resources
        financial_resources = {'financial_', 'accounting_', 'revenue_', 'expense_'}
        
        for event in events:
            if (event.event_type == AuditEventType.ACCESS_DENIED.value and
                any(fr in event.resource.lower() for fr in financial_resources)):
                
                violations.append(ComplianceViolation(
                    framework=ComplianceFramework.SOX,
                    rule_id='SOX-404.1',
                    severity='high',
                    description=f'Unauthorized access attempt to financial resource: {event.resource}',
                    events=[event],
                    timestamp=event.timestamp,
                    resource=event.resource,
                    actor=event.actor,
                    remediation_steps=[
                        'Review access permissions for financial systems',
                        'Investigate actor authorization',
                        'Update access control policies if needed'
                    ]
                ))
        
        return violations
    
    def _check_sox_unauthorized_changes(self, events: List[AuditEvent]) -> List[ComplianceViolation]:
        """Check for SOX unauthorized changes violations."""
        violations = []
        
        # Look for configuration changes to financial systems
        change_events = [AuditEventType.CONFIGURATION_CHANGED.value, AuditEventType.PERMISSION_CHANGED.value]
        
        for event in events:
            if (event.event_type in change_events and
                'financial' in event.resource.lower()):
                
                # Check if change was approved (this would need to be enhanced with approval tracking)
                violations.append(ComplianceViolation(
                    framework=ComplianceFramework.SOX,
                    rule_id='SOX-302.1',
                    severity='medium',
                    description=f'Configuration change to financial system: {event.resource}',
                    events=[event],
                    timestamp=event.timestamp,
                    resource=event.resource,
                    actor=event.actor,
                    remediation_steps=[
                        'Verify change was properly approved',
                        'Document change rationale',
                        'Review change management process'
                    ]
                ))
        
        return violations
    
    def _check_gdpr_unauthorized_data_access(self, events: List[AuditEvent]) -> List[ComplianceViolation]:
        """Check for GDPR unauthorized data access violations."""
        violations = []
        
        # Look for access to personal data without proper authorization
        personal_data_indicators = {'personal_', 'user_', 'customer_', 'email_', 'phone_'}
        
        for event in events:
            if (event.event_type == AuditEventType.DATA_READ.value and
                any(pdi in event.resource.lower() for pdi in personal_data_indicators)):
                
                # Check if access was authorized (simplified check)
                if event.outcome != 'success' or not event.actor:
                    violations.append(ComplianceViolation(
                        framework=ComplianceFramework.GDPR,
                        rule_id='GDPR-32.1',
                        severity='high',
                        description=f'Unauthorized access to personal data: {event.resource}',
                        events=[event],
                        timestamp=event.timestamp,
                        resource=event.resource,
                        actor=event.actor,
                        remediation_steps=[
                            'Investigate data access purpose',
                            'Verify legal basis for processing',
                            'Update data access controls'
                        ]
                    ))
        
        return violations
    
    def _check_gdpr_breach_notification(self, events: List[AuditEvent]) -> List[ComplianceViolation]:
        """Check for GDPR breach notification requirements."""
        violations = []
        
        # Look for security incidents that may constitute data breaches
        breach_events = [
            AuditEventType.INTEGRITY_VIOLATION.value,
            AuditEventType.SUSPICIOUS_ACTIVITY.value,
            AuditEventType.REPLAY_DETECTED.value
        ]
        
        for event in events:
            if event.event_type in breach_events:
                violations.append(ComplianceViolation(
                    framework=ComplianceFramework.GDPR,
                    rule_id='GDPR-33.1',
                    severity='critical',
                    description=f'Potential data breach requiring notification: {event.event_type}',
                    events=[event],
                    timestamp=event.timestamp,
                    resource=event.resource,
                    actor=event.actor,
                    remediation_steps=[
                        'Assess breach scope and impact',
                        'Notify supervisory authority within 72 hours if required',
                        'Notify affected data subjects if high risk',
                        'Document breach response'
                    ]
                ))
        
        return violations
    
    def _check_hipaa_phi_access(self, events: List[AuditEvent]) -> List[ComplianceViolation]:
        """Check for HIPAA PHI access violations."""
        violations = []
        
        # Look for access to protected health information
        phi_indicators = {'health_', 'medical_', 'patient_', 'diagnosis_', 'treatment_'}
        
        for event in events:
            if (event.event_type in [AuditEventType.DATA_READ.value, AuditEventType.DATA_WRITE.value] and
                any(phi in event.resource.lower() for phi in phi_indicators)):
                
                violations.append(ComplianceViolation(
                    framework=ComplianceFramework.HIPAA,
                    rule_id='HIPAA-164.312',
                    severity='high',
                    description=f'Access to PHI: {event.resource}',
                    events=[event],
                    timestamp=event.timestamp,
                    resource=event.resource,
                    actor=event.actor,
                    remediation_steps=[
                        'Verify minimum necessary access',
                        'Check authorization for PHI access',
                        'Review audit logs for PHI access patterns'
                    ]
                ))
        
        return violations
    
    def _check_soc2_access_controls(self, events: List[AuditEvent]) -> List[ComplianceViolation]:
        """Check for SOC2 access control violations."""
        violations = []
        
        # Look for failed access attempts that might indicate weak controls
        failed_events = [AuditEventType.LOGIN_FAILED.value, AuditEventType.ACCESS_DENIED.value]
        
        # Group events by actor to detect patterns
        actor_failures = defaultdict(list)
        for event in events:
            if event.event_type in failed_events and event.actor:
                actor_failures[event.actor].append(event)
        
        # Check for excessive failures
        for actor, failures in actor_failures.items():
            if len(failures) >= 10:  # Threshold for excessive failures
                violations.append(ComplianceViolation(
                    framework=ComplianceFramework.SOC2,
                    rule_id='SOC2-CC6.1',
                    severity='medium',
                    description=f'Excessive access failures for actor: {actor}',
                    events=failures,
                    timestamp=max(e.timestamp for e in failures),
                    resource='access_control_system',
                    actor=actor,
                    remediation_steps=[
                        'Review access control effectiveness',
                        'Investigate potential brute force attack',
                        'Consider account lockout policies'
                    ]
                ))
        
        return violations


class ComplianceReporter:
    """
    Generates compliance reports from audit logs and violations.
    
    Supports multiple output formats and regulatory frameworks.
    """
    
    def __init__(self, audit_logger: AuditLogger, rule_engine: Optional[ComplianceRuleEngine] = None):
        """
        Initialize compliance reporter.
        
        Args:
            audit_logger: Audit logger to read events from
            rule_engine: Compliance rule engine for violations
        """
        self.audit_logger = audit_logger
        self.rule_engine = rule_engine or ComplianceRuleEngine()
        
        self.stats = {
            'reports_generated': 0,
            'events_analyzed': 0,
            'violations_reported': 0
        }
    
    def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        start_time: float,
        end_time: float,
        output_format: ReportFormat = ReportFormat.JSON,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report.
        
        Args:
            framework: Compliance framework to report on
            start_time: Report start time (Unix timestamp)
            end_time: Report end time (Unix timestamp)
            output_format: Output format for the report
            output_file: Optional file to save report to
            
        Returns:
            Compliance report data
        """
        # Read events from audit log
        events = self._read_audit_events(start_time, end_time)
        
        # Evaluate compliance violations
        violations = self.rule_engine.evaluate_events(events, [framework])
        
        # Generate metrics
        metrics = self._calculate_compliance_metrics(events, violations, framework)
        
        # Create report structure
        report = {
            'metadata': {
                'framework': framework.value,
                'report_period': {
                    'start': datetime.fromtimestamp(start_time).isoformat(),
                    'end': datetime.fromtimestamp(end_time).isoformat()
                },
                'generated_at': datetime.now().isoformat(),
                'events_analyzed': len(events),
                'violations_detected': len(violations)
            },
            'executive_summary': self._generate_executive_summary(violations, metrics),
            'violations': [self._violation_to_dict(v) for v in violations],
            'metrics': [asdict(m) for m in metrics],
            'recommendations': self._generate_recommendations(violations, framework)
        }
        
        # Save to file if requested
        if output_file:
            self._save_report(report, output_file, output_format)
        
        # Update statistics
        self.stats['reports_generated'] += 1
        self.stats['events_analyzed'] += len(events)
        self.stats['violations_reported'] += len(violations)
        
        return report
    
    def _read_audit_events(self, start_time: float, end_time: float) -> List[AuditEvent]:
        """Read audit events from the specified time period."""
        events = []
        
        try:
            # Read from audit log file
            with open(self.audit_logger.log_file, 'r') as f:
                for line in f:
                    try:
                        event_dict = json.loads(line.strip())
                        event_time = event_dict.get('timestamp', 0)
                        
                        if start_time <= event_time <= end_time:
                            # Convert back to AuditEvent
                            event = AuditEvent(
                                event_type=event_dict.get('event_type', ''),
                                timestamp=event_time,
                                resource=event_dict.get('resource', ''),
                                action=event_dict.get('action', ''),
                                outcome=event_dict.get('outcome', ''),
                                actor=event_dict.get('actor'),
                                actor_ip=event_dict.get('actor_ip'),
                                session_id=event_dict.get('session_id'),
                                metadata=event_dict.get('metadata', {})
                            )
                            events.append(event)
                    
                    except json.JSONDecodeError:
                        continue
        
        except FileNotFoundError:
            logging.warning(f"Audit log file not found: {self.audit_logger.log_file}")
        
        return events
    
    def _calculate_compliance_metrics(
        self,
        events: List[AuditEvent],
        violations: List[ComplianceViolation],
        framework: ComplianceFramework
    ) -> List[ComplianceMetric]:
        """Calculate compliance metrics."""
        metrics = []
        
        # Basic metrics
        total_events = len(events)
        total_violations = len(violations)
        
        metrics.append(ComplianceMetric(
            metric_name="compliance_score",
            current_value=max(0, (total_events - total_violations) / max(total_events, 1) * 100),
            threshold=95.0,
            status="compliant" if total_violations == 0 else "non_compliant",
            description="Overall compliance score percentage",
            measurement_time=time.time()
        ))
        
        # Violation severity distribution
        severity_counts = Counter(v.severity for v in violations)
        for severity, count in severity_counts.items():
            metrics.append(ComplianceMetric(
                metric_name=f"violations_{severity}",
                current_value=count,
                threshold=0,
                status="compliant" if count == 0 else "non_compliant",
                description=f"Number of {severity} severity violations",
                measurement_time=time.time()
            ))
        
        # Framework-specific metrics
        if framework == ComplianceFramework.GDPR:
            # Data subject access requests
            access_requests = len([e for e in events if 'data_subject_request' in e.metadata.get('type', '')])
            metrics.append(ComplianceMetric(
                metric_name="data_subject_requests",
                current_value=access_requests,
                threshold=None,
                status="info",
                description="Number of data subject access requests processed",
                measurement_time=time.time()
            ))
        
        elif framework == ComplianceFramework.SOX:
            # Financial system access events
            financial_access = len([e for e in events if 'financial' in e.resource.lower()])
            metrics.append(ComplianceMetric(
                metric_name="financial_system_access",
                current_value=financial_access,
                threshold=None,
                status="info",
                description="Number of financial system access events",
                measurement_time=time.time()
            ))
        
        return metrics
    
    def _generate_executive_summary(self, violations: List[ComplianceViolation], metrics: List[ComplianceMetric]) -> Dict[str, Any]:
        """Generate executive summary of compliance status."""
        total_violations = len(violations)
        critical_violations = len([v for v in violations if v.severity == 'critical'])
        high_violations = len([v for v in violations if v.severity == 'high'])
        
        compliance_score = next(
            (m.current_value for m in metrics if m.metric_name == "compliance_score"),
            0
        )
        
        return {
            'overall_status': 'compliant' if total_violations == 0 else 'non_compliant',
            'compliance_score': compliance_score,
            'total_violations': total_violations,
            'critical_violations': critical_violations,
            'high_violations': high_violations,
            'key_findings': self._extract_key_findings(violations),
            'risk_level': self._assess_risk_level(violations)
        }
    
    def _extract_key_findings(self, violations: List[ComplianceViolation]) -> List[str]:
        """Extract key findings from violations."""
        findings = []
        
        # Most frequent violation types
        violation_types = Counter(v.rule_id for v in violations)
        if violation_types:
            most_common = violation_types.most_common(3)
            for rule_id, count in most_common:
                findings.append(f"Most frequent violation: {rule_id} ({count} occurrences)")
        
        # Actors with most violations
        actor_violations = Counter(v.actor for v in violations if v.actor)
        if actor_violations:
            top_actor, count = actor_violations.most_common(1)[0]
            findings.append(f"Actor with most violations: {top_actor} ({count} violations)")
        
        return findings
    
    def _assess_risk_level(self, violations: List[ComplianceViolation]) -> str:
        """Assess overall risk level based on violations."""
        if not violations:
            return 'low'
        
        critical_count = len([v for v in violations if v.severity == 'critical'])
        high_count = len([v for v in violations if v.severity == 'high'])
        
        if critical_count > 0:
            return 'critical'
        elif high_count > 3:
            return 'high'
        elif len(violations) > 10:
            return 'medium'
        else:
            return 'low'
    
    def _generate_recommendations(self, violations: List[ComplianceViolation], framework: ComplianceFramework) -> List[str]:
        """Generate recommendations based on violations."""
        recommendations = []
        
        if not violations:
            recommendations.append("No compliance violations detected. Continue monitoring.")
            return recommendations
        
        # General recommendations based on violation patterns
        violation_types = Counter(v.rule_id for v in violations)
        
        if any('unauthorized_access' in rule_id for rule_id in violation_types):
            recommendations.append("Review and strengthen access control policies")
        
        if any('data_breach' in rule_id for rule_id in violation_types):
            recommendations.append("Implement incident response procedures")
        
        # Framework-specific recommendations
        if framework == ComplianceFramework.GDPR:
            recommendations.extend([
                "Conduct privacy impact assessment",
                "Review data processing lawfulness",
                "Update privacy notices if needed"
            ])
        elif framework == ComplianceFramework.SOX:
            recommendations.extend([
                "Strengthen internal controls over financial reporting",
                "Review segregation of duties",
                "Enhance change management processes"
            ])
        
        return recommendations
    
    def _violation_to_dict(self, violation: ComplianceViolation) -> Dict[str, Any]:
        """Convert violation to dictionary."""
        return {
            'framework': violation.framework.value,
            'rule_id': violation.rule_id,
            'severity': violation.severity,
            'description': violation.description,
            'timestamp': datetime.fromtimestamp(violation.timestamp).isoformat(),
            'resource': violation.resource,
            'actor': violation.actor,
            'event_count': len(violation.events),
            'remediation_steps': violation.remediation_steps
        }
    
    def _save_report(self, report: Dict[str, Any], output_file: str, format: ReportFormat) -> None:
        """Save report to file in specified format."""
        if format == ReportFormat.JSON:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
        
        elif format == ReportFormat.CSV:
            # Flatten violations for CSV
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Rule ID', 'Severity', 'Description', 'Timestamp', 'Resource', 'Actor'])
                
                for violation in report['violations']:
                    writer.writerow([
                        violation['rule_id'],
                        violation['severity'],
                        violation['description'],
                        violation['timestamp'],
                        violation['resource'],
                        violation['actor']
                    ])
        
        # HTML and PDF formats would require additional dependencies
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compliance reporter statistics."""
        return self.stats.copy()


# Factory function for easy setup
def create_compliance_reporter(audit_logger: AuditLogger) -> ComplianceReporter:
    """
    Create compliance reporter with default configuration.
    
    Args:
        audit_logger: Audit logger instance
        
    Returns:
        Configured compliance reporter
    """
    rule_engine = ComplianceRuleEngine()
    return ComplianceReporter(audit_logger, rule_engine)