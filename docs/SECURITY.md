# ResonaGraph Security Guidelines

## Document Information

**Version**: 1.0  
**Last Updated**: 2025-01-09  
**Target Audience**: DevOps, Security Engineers, System Administrators  
**Status**: Production Ready

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Deployment Security](#deployment-security)
3. [Key Management](#key-management)
4. [Network Security](#network-security)
5. [Access Control](#access-control)
6. [Monitoring and Alerting](#monitoring-and-alerting)
7. [Compliance](#compliance)
8. [Incident Response](#incident-response)
9. [Security Checklist](#security-checklist)
10. [Vulnerability Reporting](#vulnerability-reporting)

---

## Security Overview

### Security Architecture

ResonaGraph implements defense-in-depth with multiple security layers:

```
┌─────────────────────────────────────────────────────┐
│         Layer 1: Network Security                    │
│  TLS 1.3, Certificate Pinning, Rate Limiting        │
└─────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────┐
│         Layer 2: Cryptographic Security              │
│  Ed25519 Signatures, HMAC-SHA256, HKDF              │
└─────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────┐
│         Layer 3: Access Control                      │
│  Phase-Key Auth, RBAC Policies, Key Hierarchy       │
└─────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────┐
│         Layer 4: Monitoring & Response               │
│  Threat Detection, Alerts, Audit Logs, Compliance   │
└─────────────────────────────────────────────────────┘
```

### Core Security Features

- ✅ **Cryptographic Access Control**: Phase-key based with 256-bit security
- ✅ **Beacon Integrity**: Ed25519 signatures on all beacons
- ✅ **Data Authenticity**: HMAC-SHA256 phase MACs
- ✅ **Audit Logging**: Tamper-evident hash-chain logs
- ✅ **Threat Detection**: Real-time pattern-based detection
- ✅ **Compliance**: Automated reporting for 7 frameworks
- ✅ **Key Rotation**: Automatic 24-hour rotation
- ✅ **HSM Integration**: Hardware security module support

---

## Deployment Security

### Production Deployment Checklist

#### 1. Infrastructure Security

```yaml
# Minimum security requirements for production
infrastructure:
  compute:
    - Dedicated servers (no shared hosting)
    - Hardened OS (CIS benchmark compliant)
    - SELinux/AppArmor enabled
    - Regular security patching
  
  network:
    - Private network for node communication
    - Firewall rules (whitelist only)
    - DDoS protection
    - Network segmentation
  
  storage:
    - Encrypted volumes (LUKS/dm-crypt)
    - Secure backup procedures
    - Off-site backup storage
    - Regular backup testing
```

#### 2. TLS Configuration

**Minimum TLS Settings**:
```yaml
tls:
  min_version: "1.3"
  cipher_suites:
    - TLS_AES_256_GCM_SHA384
    - TLS_CHACHA20_POLY1305_SHA256
  
  certificates:
    cert_file: "/etc/resonagraph/certs/server.crt"
    key_file: "/etc/resonagraph/certs/server.key"
    ca_file: "/etc/resonagraph/certs/ca.crt"
  
  mutual_tls: true  # Require client certificates
  cert_pinning: true  # Enable certificate pinning
```

**Certificate Management**:
- Use certificates from trusted CA
- Set appropriate validity periods (≤ 1 year)
- Implement certificate rotation
- Monitor certificate expiration
- Use strong key sizes (≥ 2048 bits RSA or 256 bits ECDSA)

#### 3. Service Hardening

```yaml
security:
  # Run as non-root user
  user: resonagraph
  group: resonagraph
  
  # Restrict file permissions
  file_permissions:
    config: 0600
    keys: 0400
    logs: 0640
    data: 0700
  
  # Resource limits
  limits:
    max_memory: "8GB"
    max_cpu: "4"
    max_files: 65536
    max_processes: 1024
  
  # Security features
  features:
    no_new_privileges: true
    read_only_root: true
    temp_filesystem: "tmpfs"
```

#### 4. Container Security (Docker/K8s)

**Docker Security**:
```dockerfile
# Use minimal base image
FROM gcr.io/distroless/python3:nonroot

# Run as non-root
USER nonroot:nonroot

# Read-only root filesystem
VOLUME ["/tmp"]

# Drop capabilities
SECURITY_OPTS:
  - no-new-privileges:true
  - seccomp:default.json
```

**Kubernetes Security**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: resonagraph-node
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  
  containers:
  - name: resonagraph
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    
    resources:
      limits:
        memory: "8Gi"
        cpu: "4"
      requests:
        memory: "4Gi"
        cpu: "2"
```

---

## Key Management

### Key Hierarchy

```
Root Key (K_root)
    │
    ├─→ Topic Key (K_users)
    │       ├─→ Admin Key
    │       ├─→ User Key
    │       └─→ Read-Only Key
    │
    ├─→ Topic Key (K_posts)
    │       └─→ [same hierarchy]
    │
    └─→ Signature Key (per-node)
            └─→ Ed25519 keypair
```

### Root Key Management

**Generation**:
```python
from resonagraph.security import KeyHierarchy
import secrets

# Generate cryptographically secure root key
root_key_bytes = secrets.token_bytes(32)

# Store in HSM (production) or secure key management system
hierarchy = KeyHierarchy(
    root_key=root_key_bytes,
    use_hsm=True,
    hsm_config={
        "type": "pkcs11",
        "library_path": "/usr/lib/libsofthsm2.so",
        "slot": 0,
        "pin": os.getenv("HSM_PIN")
    }
)
```

**Storage Options**:

1. **Hardware Security Module (HSM)** - RECOMMENDED
   ```yaml
   hsm:
     type: "pkcs11"  # or "aws_cloudhsm", "azure_keyvault"
     library_path: "/usr/lib/libsofthsm2.so"
     slot: 0
     pin: "${HSM_PIN}"  # From environment/secrets manager
   ```

2. **Cloud Key Management**
   ```yaml
   kms:
     provider: "aws"  # or "gcp", "azure"
     key_id: "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
     region: "us-east-1"
   ```

3. **Encrypted File Storage** - DEVELOPMENT ONLY
   ```bash
   # Encrypt root key with strong passphrase
   openssl enc -aes-256-cbc -salt -in root_key.bin -out root_key.enc
   
   # Set restrictive permissions
   chmod 400 root_key.enc
   chown resonagraph:resonagraph root_key.enc
   ```

### Key Rotation

**Automatic Rotation**:
```python
from resonagraph.security import KeyHierarchy

hierarchy = KeyHierarchy(
    root_key=root_key,
    rotation_interval=86400,  # 24 hours
    auto_rotate=True
)

# Keys are automatically rotated
# Old keys retained for grace period (default: 7 days)
```

**Manual Rotation**:
```python
# Rotate specific topic key
new_key = hierarchy.rotate_key(
    topic="users",
    retain_old=True,
    grace_period=604800  # 7 days
)

# Audit log entry created automatically
```

**Emergency Key Revocation**:
```python
# Immediate revocation (no grace period)
hierarchy.revoke_key(
    topic="users",
    reason="suspected_compromise",
    immediate=True
)

# All beacons with old key immediately invalid
```

### Backup and Recovery

**Key Backup**:
```bash
# Export encrypted key backup
resonagraph-admin export-keys \
  --output /secure/backup/keys.enc \
  --encrypt-with-passphrase \
  --include-metadata

# Store backup in secure, off-site location
# Use separate encryption key for backup
```

**Key Recovery**:
```bash
# Restore from backup
resonagraph-admin import-keys \
  --input /secure/backup/keys.enc \
  --verify-integrity \
  --dry-run  # Test before applying

# Actual restoration
resonagraph-admin import-keys \
  --input /secure/backup/keys.enc \
  --apply
```

---

## Network Security

### Firewall Configuration

**Minimum Firewall Rules**:
```bash
# Allow QUIC/TLS traffic (API)
iptables -A INPUT -p udp --dport 8443 -m state --state NEW,ESTABLISHED -j ACCEPT

# Allow gossip protocol
iptables -A INPUT -p udp --dport 8444 -m state --state NEW,ESTABLISHED -j ACCEPT

# Allow monitoring (Prometheus)
iptables -A INPUT -p tcp --dport 9090 -s 10.0.0.0/8 -j ACCEPT

# Drop all other traffic
iptables -A INPUT -j DROP
```

### Rate Limiting

```yaml
rate_limiting:
  # Per-IP limits
  per_ip:
    read_ops: 100/minute
    write_ops: 50/minute
    query_ops: 20/minute
  
  # Global limits
  global:
    read_ops: 10000/minute
    write_ops: 5000/minute
    query_ops: 2000/minute
  
  # Connection limits
  connections:
    max_per_ip: 10
    max_total: 1000
    timeout: 30s
```

### DDoS Protection

**Network-Level**:
- Use DDoS protection service (Cloudflare, AWS Shield)
- Implement SYN flood protection
- Enable connection tracking
- Use geofencing if appropriate

**Application-Level**:
```yaml
ddos_protection:
  # Enable proof-of-work for expensive operations
  proof_of_work:
    enabled: true
    difficulty: 20  # bits
    operations: ["write", "traverse"]
  
  # Circuit breaker
  circuit_breaker:
    failure_threshold: 50%
    timeout: 60s
    half_open_requests: 10
```

---

## Access Control

### Role-Based Access Control

**Define Roles**:
```python
from resonagraph.security import AccessControl, AccessPolicy, AccessLevel

ac = AccessControl(key_hierarchy)

# Read-only role
ac.add_policy(AccessPolicy(
    resource="vertex:*",
    action="read",
    principal="role:readonly",
    level=AccessLevel.READ_ONLY
))

# User role
ac.add_policy(AccessPolicy(
    resource="vertex:user_*",
    action=["read", "write"],
    principal="role:user",
    level=AccessLevel.READ_WRITE
))

# Admin role
ac.add_policy(AccessPolicy(
    resource="*",
    action="*",
    principal="role:admin",
    level=AccessLevel.ADMIN
))
```

### Principle of Least Privilege

**Application Example**:
```python
# Derive separate keys for different access levels
admin_key = hierarchy.derive_key("users", context={"role": "admin"})
user_key = hierarchy.derive_key("users", context={"role": "user"})
readonly_key = hierarchy.derive_key("users", context={"role": "readonly"})

# Grant only necessary access
analytics_service.configure(phase_key=readonly_key)  # Read-only
user_api.configure(phase_key=user_key)              # Read-write
admin_panel.configure(phase_key=admin_key)          # Full access
```

### Access Audit

```python
# Enable access audit logging
audit_logger = AuditLogger(
    log_file="/var/log/resonagraph/access.log",
    anonymization_level=AnonymizationLevel.MEDIUM,
    enable_hash_chain=True
)

# All access attempts logged automatically
# Review logs regularly
resonagraph-admin audit review \
  --since "24h ago" \
  --filter "access_denied" \
  --output access_denials.json
```

---

## Monitoring and Alerting

### Threat Detection Configuration

```yaml
threat_detection:
  enabled: true
  baseline_window: 86400  # 24 hours
  
  patterns:
    brute_force:
      threshold: 5
      window: 300
      action: "alert_and_block"
    
    key_enumeration:
      threshold: 20
      window: 60
      action: "alert_and_throttle"
    
    mass_data_access:
      threshold: 100
      window: 300
      action: "alert_critical"
    
    privilege_escalation:
      threshold: 10
      window: 600
      action: "alert_and_block"
```

### Alert Configuration

**Critical Alerts** (Immediate Response):
```yaml
alerts:
  critical:
    channels:
      - smtp
      - webhook
      - pagerduty
    escalation: 0  # Immediate
    recipients:
      - security@company.com
      - oncall@company.com
```

**High Alerts** (5-minute Escalation):
```yaml
  high:
    channels:
      - smtp
      - webhook
    escalation: 300  # 5 minutes
    recipients:
      - security@company.com
```

### Security Monitoring Dashboard

**Key Metrics to Monitor**:

1. **Authentication Metrics**
   - Failed login attempts
   - Successful logins
   - Concurrent sessions
   - Key rotation events

2. **Access Metrics**
   - Read/write operation rates
   - Access denials
   - Policy violations
   - Privilege escalation attempts

3. **Integrity Metrics**
   - Signature verification failures
   - MAC verification failures
   - Replay attack detections
   - Beacon tampering attempts

4. **Performance Metrics**
   - Lock success rate
   - Average lock time
   - Query latency (p50, p95, p99)
   - Resource utilization

**Prometheus Integration**:
```yaml
prometheus:
  enabled: true
  port: 9090
  metrics_path: "/metrics"
  
  metrics:
    - resonagraph_lock_attempts_total
    - resonagraph_lock_failures_total
    - resonagraph_access_denials_total
    - resonagraph_signature_failures_total
    - resonagraph_security_alerts_total
```

---

## Compliance

### GDPR Compliance

**Data Protection Measures**:
- ✅ Encryption at rest and in transit
- ✅ Access control and audit logging
- ✅ Data anonymization (3 levels)
- ✅ Right to erasure support
- ✅ Breach notification (automated)

**Configuration**:
```yaml
compliance:
  gdpr:
    enabled: true
    data_retention: 90days
    anonymization_level: "high"
    breach_notification:
      enabled: true
      threshold: "any_unauthorized_access"
      notify_within: "72h"
```

### HIPAA Compliance

**PHI Protection**:
- ✅ Encryption (256-bit)
- ✅ Access controls
- ✅ Audit logging (tamper-evident)
- ✅ Minimum necessary access
- ✅ Business associate agreements

**Configuration**:
```yaml
compliance:
  hipaa:
    enabled: true
    phi_encryption: true
    minimum_necessary: true
    audit_retention: 6years
    automatic_logoff: 15min
```

### SOX Compliance

**Financial Controls**:
- ✅ Audit trail completeness
- ✅ Segregation of duties
- ✅ Change management
- ✅ Access controls

**Configuration**:
```yaml
compliance:
  sox:
    enabled: true
    change_approval: required
    dual_control: true
    audit_retention: 7years
```

### Automated Compliance Reporting

```python
from resonagraph.security import ComplianceReporter, ComplianceFramework

reporter = ComplianceReporter(audit_logger)

# Generate quarterly GDPR report
gdpr_report = reporter.generate_compliance_report(
    framework=ComplianceFramework.GDPR,
    start_time=quarter_start,
    end_time=quarter_end,
    output_format=ReportFormat.JSON,
    output_file="gdpr_q1_2024.json"
)

# Schedule automated reporting
reporter.schedule_report(
    framework=ComplianceFramework.GDPR,
    frequency="monthly",
    recipients=["compliance@company.com"]
)
```

---

## Incident Response

### Incident Response Plan

#### 1. Detection Phase
```yaml
detection:
  sources:
    - Threat detection alerts
    - Security monitoring dashboards
    - User reports
    - Compliance violations
  
  triage:
    severity_levels:
      critical: "< 15 minutes"
      high: "< 1 hour"
      medium: "< 4 hours"
      low: "< 24 hours"
```

#### 2. Containment Phase
```python
# Automated containment for critical threats
def handle_critical_alert(alert):
    if alert.threat_level == ThreatLevel.CRITICAL:
        # Immediate actions
        incident_response.block_actor(alert.actor)
        incident_response.revoke_credentials(alert.actor)
        incident_response.isolate_affected_nodes()
        
        # Notify security team
        incident_response.escalate_to_oncall(alert)
        
        # Preserve evidence
        incident_response.snapshot_logs(alert.timestamp)
        incident_response.capture_network_traffic()
```

#### 3. Investigation Phase
```python
# Forensic analysis
from resonagraph.security import LogAnalyzer

analyzer = LogAnalyzer("/var/log/resonagraph/audit.log")

# Gather evidence
evidence = analyzer.query_events(
    filters=QueryFilter(
        actors=[suspected_actor],
        start_time=incident_start - 3600,  # 1 hour before
        end_time=incident_end
    )
)

# Analyze behavior
behavior = analyzer.analyze_user_behavior(
    actor=suspected_actor,
    start_time=incident_start - 86400,  # 24 hours before
    end_time=incident_end
)

# Generate forensic report
forensic_report = analyzer.generate_forensic_report(
    incident_id="INC-2024-001",
    evidence=evidence,
    behavior=behavior
)
```

#### 4. Recovery Phase
```yaml
recovery:
  steps:
    - Verify threat eliminated
    - Restore from clean backup if needed
    - Rotate compromised keys
    - Update security controls
    - Resume normal operations
  
  validation:
    - Run security scans
    - Verify audit log integrity
    - Test key rotation
    - Monitor for recurrence
```

#### 5. Lessons Learned
```yaml
post_incident:
  documentation:
    - Incident timeline
    - Root cause analysis
    - Actions taken
    - Lessons learned
    - Recommendations
  
  improvements:
    - Update threat detection rules
    - Enhance monitoring
    - Adjust alert thresholds
    - Update incident playbooks
```

---

## Security Checklist

### Pre-Deployment Checklist

- [ ] **Infrastructure Security**
  - [ ] Hardened OS with latest security patches
  - [ ] SELinux/AppArmor enabled
  - [ ] Firewall configured (whitelist only)
  - [ ] DDoS protection enabled
  - [ ] Encrypted storage volumes

- [ ] **TLS Configuration**
  - [ ] TLS 1.3 minimum version
  - [ ] Strong cipher suites only
  - [ ] Valid certificates from trusted CA
  - [ ] Certificate pinning enabled
  - [ ] Mutual TLS configured

- [ ] **Key Management**
  - [ ] Root key stored in HSM or KMS
  - [ ] Key rotation configured (24h)
  - [ ] Backup procedures tested
  - [ ] Recovery procedures documented
  - [ ] Emergency revocation tested

- [ ] **Access Control**
  - [ ] RBAC policies defined
  - [ ] Least privilege enforced
  - [ ] Access audit enabled
  - [ ] Strong authentication required

- [ ] **Monitoring**
  - [ ] Threat detection enabled
  - [ ] Alert channels configured
  - [ ] Escalation rules set
  - [ ] Monitoring dashboard deployed
  - [ ] On-call rotation established

- [ ] **Compliance**
  - [ ] Required frameworks enabled
  - [ ] Audit retention configured
  - [ ] Automated reporting scheduled
  - [ ] Data protection verified

- [ ] **Incident Response**
  - [ ] IR plan documented
  - [ ] IR team identified
  - [ ] Escalation procedures tested
  - [ ] Forensic tools ready
  - [ ] Communication plan defined

### Post-Deployment Checklist

- [ ] **Operational Security**
  - [ ] Security scans passed
  - [ ] Penetration testing completed
  - [ ] Audit logs reviewed
  - [ ] Access controls verified
  - [ ] Backup restoration tested

- [ ] **Continuous Monitoring**
  - [ ] Daily security reviews
  - [ ] Weekly alert analysis
  - [ ] Monthly compliance reports
  - [ ] Quarterly security audits
  - [ ] Annual penetration testing

---

## Vulnerability Reporting

### Responsible Disclosure

If you discover a security vulnerability in ResonaGraph:

1. **DO NOT** disclose publicly
2. **DO NOT** exploit the vulnerability
3. **DO** report to: security@resonagraph.io

### Report Should Include

- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)
- Your contact information

### Response Timeline

- **Initial Response**: Within 24 hours
- **Triage**: Within 72 hours
- **Fix Development**: Severity-dependent
  - Critical: 7 days
  - High: 14 days
  - Medium: 30 days
  - Low: 90 days
- **Disclosure**: After fix deployed + 90 days

### Hall of Fame

We maintain a security hall of fame for responsible disclosure:
https://resonagraph.io/security/hall-of-fame

---

## Security Contact

**Security Team**: security@resonagraph.io  
**PGP Key**: Available at https://resonagraph.io/security/pgp-key.asc  
**Emergency Contact**: +1-XXX-XXX-XXXX (24/7 security hotline)

---

## References

### Standards
- NIST SP 800-53: Security and Privacy Controls
- CIS Benchmarks: System Hardening
- OWASP Top 10: Application Security
- PCI DSS: Payment Card Security

### Related Documents
- [THREAT_MODEL.md](THREAT_MODEL.md) - Comprehensive threat analysis
- [SYSTEM_REFERENCE.md](SYSTEM_REFERENCE.md) - Technical reference
- [USERS_GUIDE.md](USERS_GUIDE.md) - User documentation
- [PHASE6_SUMMARY.md](PHASE6_SUMMARY.md) - Security implementation

---

**Document Version**: 1.0  
**Classification**: Public  
**Last Review**: 2025-01-09  
**Next Review**: 2025-04-09