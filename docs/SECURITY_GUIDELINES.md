# ResonaGraph Security Guidelines

## Overview

This document provides security guidelines for deploying, operating, and developing ResonaGraph. It covers best practices for key management, access control, monitoring, and incident response.

**Audience**: Operators, Developers, Security Teams  
**Version**: 1.0  
**Last Updated**: 2025-01

## Quick Start Security Checklist

For production deployments:

- [ ] Use HSM for root key storage (K_root)
- [ ] Enable TLS/QUIC for all network communications
- [ ] Configure audit logging with HIGH anonymization
- [ ] Set up log monitoring and alerting
- [ ] Enable automatic key rotation (24h for phase keys, 30d for signatures)
- [ ] Implement network segmentation and firewalls
- [ ] Regular security updates and patches
- [ ] Conduct security assessment before production

## Key Management

### Root Key Protection

The root phase key (K_root) is the most critical secret in ResonaGraph.

**Production Requirements**:
```python
from resonagraph.security import KeyHierarchy

# DO: Use HSM for root key in production
root_key = load_key_from_hsm()
hierarchy = KeyHierarchy(root_key)

# DON'T: Generate or store root key in code/config
# root_key = PhaseKey.generate()  # NEVER in production!
```

**Backup and Recovery**:
1. Store root key backup in secure offline location
2. Use key splitting (Shamir's Secret Sharing) for multi-party recovery
3. Document key recovery procedures
4. Test recovery process regularly

### Key Rotation

**Automatic Rotation**:
```python
from resonagraph.security import KeyRotationScheduler

# Set up automatic rotation
scheduler = KeyRotationScheduler(
    hierarchy,
    rotation_interval=86400,  # 24 hours for phase keys
    overlap_period=3600        # 1 hour graceful transition
)

# Monitor rotation
if scheduler.should_rotate("topic_name"):
    new_key = scheduler.rotate_key("topic_name")
    # Log rotation event
    audit_logger.log_key_operation("rotate", new_key.key_id, "topic")
```

**Manual Rotation**:
Rotate immediately when:
- Key compromise suspected
- Employee with key access leaves
- Security incident detected
- Compliance requirement

### Key Distribution

**Public Key Distribution**:
```python
from resonagraph.security import SignatureKeyManager

manager = SignatureKeyManager("node1")

# Export public key for distribution
pem_data = manager.export_public_key()

# Other nodes import the public key
other_manager.import_public_key("node1:12345", pem_data)
```

**Security Notes**:
- Distribute public keys via authenticated channels
- Verify key fingerprints out-of-band
- Use key server with audit trail for large deployments

## Access Control

### Policy Configuration

**Default Policies**:
```python
from resonagraph.security import AccessControl, AccessPolicy, AccessLevel

ac = AccessControl(hierarchy)

# Create default policies
ac.create_default_policies()

# Customize for your needs
ac.add_policy(AccessPolicy(
    resource="vertex:sensitive_*",
    action="read",
    principal="role:auditor",
    level=AccessLevel.READ_ONLY
))
```

**Best Practices**:
1. Follow principle of least privilege
2. Use role-based access control (RBAC)
3. Regular policy reviews
4. Audit all policy changes

### Role Management

**Recommended Roles**:
- **admin**: Full system access (use sparingly)
- **user**: Read/write own data
- **read-only**: Read access only
- **auditor**: Read audit logs only
- **service**: Automated service accounts

**Role Assignment**:
```python
# Set custom role level
ac.set_role_level("auditor", AccessLevel.READ_ONLY)

# Get role-specific key
auditor_key = ac.get_role_key("auditor", "audit_logs", version=1)
```

## Audit Logging

### Configuration

**Production Setup**:
```python
from resonagraph.security import AuditLogger, AnonymizationLevel, Anonymizer, AnonymizedAuditLogger

# Base audit logger with rotation
base_logger = AuditLogger(
    log_file="/var/log/resonagraph/audit.log",
    max_bytes=10 * 1024 * 1024,  # 10 MB
    backup_count=10,
    enable_hash_chain=True
)

# Wrap with anonymization for GDPR compliance
anonymizer = Anonymizer(level=AnonymizationLevel.HIGH)
audit_logger = AnonymizedAuditLogger(base_logger, anonymizer)
```

**What to Log**:
- All access control decisions
- Key operations (generation, rotation, revocation)
- Lock attempts (success and failure)
- Signature/MAC verification failures
- Replay attack detections
- Configuration changes

**What NOT to Log**:
- Raw phase keys (always anonymized)
- User passwords or secrets
- Full payload contents
- PII without anonymization

### Monitoring and Alerts

**Critical Alerts**:
```python
# Monitor for security events
def monitor_security_events(audit_log_file):
    with open(audit_log_file, 'r') as f:
        for line in f:
            event = json.loads(line)
            
            # Alert on repeated failures
            if event['event_type'] == 'signature_failed':
                alert_security_team(event)
            
            # Alert on replay attacks
            if event['event_type'] == 'replay_detected':
                alert_security_team(event)
            
            # Alert on access denials
            if event['event_type'] == 'access_denied':
                track_failed_attempts(event)
```

**Monitoring Metrics**:
- Failed lock attempts per hour
- Signature verification failures
- Replay attack detections
- Access denial rate
- Key rotation compliance

## Network Security

### TLS/QUIC Configuration

**Enable Encryption**:
```python
# Configure QUIC with TLS
quic_config = {
    'certfile': '/path/to/cert.pem',
    'keyfile': '/path/to/key.pem',
    'ca_certs': '/path/to/ca.pem',
    'verify_mode': ssl.CERT_REQUIRED
}
```

**Best Practices**:
1. Use TLS 1.3 or later
2. Strong cipher suites only
3. Certificate pinning for known nodes
4. Regular certificate rotation

### Firewall Rules

**Recommended Configuration**:
```bash
# Allow only necessary ports
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT  # QUIC/HTTPS
iptables -A INPUT -p udp --dport 8443 -j ACCEPT  # QUIC

# Rate limiting
iptables -A INPUT -p tcp --dport 8443 -m limit --limit 100/minute -j ACCEPT

# Drop everything else
iptables -A INPUT -j DROP
```

## Secure Development

### Code Security Guidelines

**Cryptographic Operations**:
```python
# DO: Use constant-time comparisons
import hmac
if hmac.compare_digest(key1.get_bytes(), key2.get_bytes()):
    # keys match

# DON'T: Use regular equality
# if key1.get_bytes() == key2.get_bytes():  # Timing attack!
```

**Input Validation**:
```python
# Validate all external inputs
def validate_epoch(epoch: int, current_epoch: int, window: int = 10):
    if not isinstance(epoch, int):
        raise ValueError("Epoch must be integer")
    if epoch < current_epoch - window:
        raise ValueError("Epoch too old")
    if epoch > current_epoch + 1:
        raise ValueError("Epoch too far in future")
```

**Error Handling**:
```python
# DO: Generic error messages externally
try:
    process_beacon(beacon)
except SignatureError as e:
    # Log detailed error internally
    audit_logger.log_signature_verification(beacon.key_id, False)
    # Return generic error externally
    raise ValueError("Invalid beacon")

# DON'T: Expose internal details
# raise SignatureError(f"Invalid signature for key {key_id}")
```

### Dependency Management

**Security Scanning**:
```bash
# Regular vulnerability scanning
pip-audit
safety check
bandit -r resonagraph/

# Keep dependencies updated
pip list --outdated
```

**Dependency Pinning**:
```txt
# requirements.txt - pin versions
cryptography==41.0.7
```

## Testing

### Security Tests

**Run Security Test Suite**:
```bash
# Run all security tests
pytest resonagraph/tests/test_key_hierarchy.py
pytest resonagraph/tests/test_access_control.py
pytest resonagraph/tests/test_signatures.py
pytest resonagraph/tests/test_integrity.py
pytest resonagraph/tests/test_audit.py

# Run with coverage
pytest --cov=resonagraph/security --cov-report=html
```

**Fuzzing**:
```python
# Fuzz signature verification
def fuzz_signature_verification():
    manager = SignatureKeyManager("node1")
    
    for _ in range(10000):
        # Random message and signature
        message = os.urandom(random.randint(1, 1000))
        signature = os.urandom(64)
        
        # Should not crash
        try:
            manager.verify_signature(message, signature)
        except Exception as e:
            # Log but don't fail
            pass
```

## Incident Response

### Detection

**Indicators of Compromise**:
- Sudden spike in failed signature verifications
- Unusual access patterns in audit logs
- Replay attack detections
- Unauthorized key operations
- Anomalous network traffic

### Response Steps

1. **Identify**: Determine scope and impact via audit logs
2. **Contain**: Isolate compromised nodes, revoke affected keys
3. **Eradicate**: Remove malicious code, patch vulnerabilities
4. **Recover**: Restore from backups, re-key if needed
5. **Lessons Learned**: Update procedures, improve detection

### Forensics

**Audit Log Analysis**:
```python
def analyze_incident(audit_log, start_time, end_time):
    """Analyze audit logs for incident forensics."""
    events = []
    with open(audit_log, 'r') as f:
        for line in f:
            event = json.loads(line)
            if start_time <= event['timestamp'] <= end_time:
                events.append(event)
    
    # Verify hash chain
    if not verify_hash_chain(events):
        print("WARNING: Audit log tampering detected!")
    
    # Analyze patterns
    failed_sigs = [e for e in events if e['event_type'] == 'signature_failed']
    # ... further analysis
```

## Compliance

### GDPR

**Data Protection**:
- Use AnonymizationLevel.HIGH for EU deployments
- Support data subject access requests via audit logs
- Implement right to be forgotten
- Data processing agreements with customers

### HIPAA

**Healthcare Use Cases**:
- Enable full audit logging
- Encrypt all data in transit and at rest
- Access control with least privilege
- Regular security risk assessments

## Production Deployment

### Pre-Deployment Checklist

- [ ] Security assessment completed
- [ ] Penetration testing done
- [ ] HSM configured for root keys
- [ ] TLS/QUIC certificates installed
- [ ] Firewall rules configured
- [ ] Monitoring and alerting set up
- [ ] Incident response plan documented
- [ ] Backup and recovery tested
- [ ] Staff security training completed

### Ongoing Security

**Regular Tasks**:
- Weekly: Review audit logs for anomalies
- Monthly: Security updates and patches
- Quarterly: Access control policy review
- Annually: Full security assessment and penetration test

## Resources

- [Threat Model](THREAT_MODEL.md)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Controls](https://www.cisecurity.org/controls/)

## Support

For security issues or questions:
- Email: security@resonagraph.io
- Report vulnerabilities via GitHub Security Advisories
- Emergency hotline: [contact information]

## Disclaimer

This document provides guidelines, not guarantees. Security is a shared responsibility between ResonaGraph developers and operators. Regular security assessments and updates are essential.
