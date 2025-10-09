"""
ResonaGraph Security Module

Provides comprehensive security infrastructure including:
- Key hierarchy management and HSM integration
- Audit logging with tamper-evident hash chains
- Access control and RBAC policy engine
- Digital signatures and integrity verification
- Security monitoring and threat detection
- Compliance reporting and regulatory support
- Advanced log analytics and investigation tools
"""

# Core security components
from resonagraph.security.key_hierarchy import (
    KeyHierarchy,
    KeyMetadata
)

from resonagraph.security.hsm import (
    HSMInterface,
    MockHSM,
    create_hsm
)

from resonagraph.security.audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AnonymizationLevel,
    Anonymizer,
    HashChain,
    create_audit_logger
)

from resonagraph.security.access_control import (
    AccessControl,
    AccessPolicy,
    AccessLevel,
    Action,
    AccessRequest,
    AccessDecision
)

from resonagraph.security.signatures import (
    SignatureKeyManager,
    BeaconSigner,
    SignatureKeyInfo
)

from resonagraph.security.integrity import (
    IntegrityManager,
    PhaseMAC,
    ReplayDetector,
    MACInfo
)

# Security monitoring and alerting
from resonagraph.security.threat_detection import (
    ThreatDetector,
    ThreatPattern,
    ThreatLevel,
    AnomalyBaseline
)

from resonagraph.security.alerts import (
    SecurityAlert,
    AlertType
)

from resonagraph.security.alert_manager import (
    AlertManager
)

from resonagraph.security.monitoring import (
    SecurityMonitor,
    create_security_monitor
)

# Compliance and analytics
from resonagraph.security.compliance import (
    ComplianceReporter,
    ComplianceRuleEngine,
    ComplianceFramework,
    ComplianceViolation,
    ComplianceMetric,
    ReportFormat,
    create_compliance_reporter
)

from resonagraph.security.log_analytics import (
    LogAnalyzer,
    QueryFilter,
    QueryResult,
    AnalyticsReport,
    create_log_analyzer
)

__all__ = [
    # Key management
    'KeyHierarchy',
    'KeyMetadata',
    'HSMInterface',
    'MockHSM',
    'create_hsm',
    
    # Audit logging
    'AuditLogger',
    'AuditEvent',
    'AuditEventType',
    'AnonymizationLevel',
    'Anonymizer',
    'HashChain',
    'create_audit_logger',
    
    # Access control
    'AccessControl',
    'AccessPolicy',
    'AccessLevel',
    'Action',
    'AccessRequest',
    'AccessDecision',
    
    # Signatures and integrity
    'SignatureKeyManager',
    'BeaconSigner',
    'SignatureKeyInfo',
    'IntegrityManager',
    'PhaseMAC',
    'ReplayDetector',
    'MACInfo',
    
    # Monitoring and alerts
    'ThreatDetector',
    'ThreatPattern',
    'ThreatLevel',
    'AnomalyBaseline',
    'SecurityAlert',
    'AlertType',
    'AlertManager',
    'SecurityMonitor',
    'create_security_monitor',
    
    # Compliance and analytics
    'ComplianceReporter',
    'ComplianceRuleEngine',
    'ComplianceFramework',
    'ComplianceViolation',
    'ComplianceMetric',
    'ReportFormat',
    'create_compliance_reporter',
    'LogAnalyzer',
    'QueryFilter',
    'QueryResult',
    'AnalyticsReport',
    'create_log_analyzer'
]
