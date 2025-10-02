# ResonaGraph Threat Model

## Overview

This document outlines the threat model for ResonaGraph, a distributed graph database using phase-resonant encoding. It defines the adversary capabilities, attack vectors, security assumptions, and mitigation strategies.

**Version**: 1.0  
**Date**: 2025-01  
**Status**: Active

## Security Goals

According to copilot-instructions.md Section 5, ResonaGraph aims to provide:

1. **Confidentiality**: Data is only accessible with correct phase keys
2. **Integrity**: Beacons and data are protected against tampering
3. **Availability**: System resists partition and denial-of-service attacks
4. **Authenticity**: All beacons are cryptographically signed
5. **Non-repudiation**: Audit logs provide tamper-evident record of actions

## Trust Model

### Assumptions

1. **Honest-Majority Nodes**: We assume at least 2/3 of nodes are honest
2. **Secure Cryptography**: Ed25519, HMAC-SHA256, and HKDF are secure
3. **Secure Key Storage**: Root keys (K_root) are protected by HSM in production
4. **Network**: Adversary can eavesdrop but not break TLS/QUIC encryption
5. **Time Synchronization**: Nodes have reasonably synchronized clocks (±60s)

### Trusted Components

- HSM for root key storage (production)
- Key hierarchy implementation (HKDF)
- Signature verification (Ed25519)
- Audit logging system
- Access control policy engine

### Untrusted Components

- Network infrastructure (can be compromised)
- Individual node storage (assume some nodes may be compromised)
- Client applications (may be malicious)
- Gossip protocol participants (may lie or withhold data)

## Adversary Model

### Adversary Capabilities

**Passive Adversary**:
- Can eavesdrop on network traffic
- Can observe beacon metadata (epochs, fingerprints)
- Cannot decrypt phase-encoded data without keys
- Cannot forge signatures without private keys

**Active Adversary**:
- Can send malicious beacons
- Can replay captured beacons
- Can attempt to impersonate nodes
- Can attempt brute-force attacks on phase keys
- Can compromise individual nodes (but not majority)
- Can perform timing attacks

**Limitations**:
- Cannot break modern cryptography (Ed25519, SHA-256)
- Cannot compromise HSM-protected root keys
- Cannot compromise majority of nodes simultaneously
- Cannot reverse time or violate epoch ordering

## Attack Vectors and Mitigations

### 1. Phase Key Attacks

#### Attack: Brute Force Phase Keys
**Threat**: Adversary attempts to guess phase keys to decode data

**Likelihood**: Low  
**Impact**: High (data confidentiality breach)

**Mitigations**:
- 256-bit phase keys provide 2^256 keyspace
- Keys derived via HKDF with salt
- No direct key exposure in logs (anonymized)
- Key rotation every 24 hours limits exposure window

#### Attack: Key Leakage
**Threat**: Phase keys leaked through logs, memory dumps, or side channels

**Likelihood**: Medium  
**Impact**: High

**Mitigations**:
- Keys never logged in plaintext (audit.py line 180)
- Constant-time comparisons prevent timing attacks (phase_key.py line 122)
- Memory protection via secure key storage
- Key rotation limits damage from compromise

### 2. Beacon Attacks

#### Attack: Replay Attack
**Threat**: Adversary captures and replays old beacons to cause conflicts

**Likelihood**: High  
**Impact**: Medium (can disrupt consistency)

**Mitigations**:
- Epoch-based replay detection with sliding window (integrity.py ReplayDetector)
- Nonce tracking prevents duplicate beacons
- Beacons expire after epoch window (default 10 epochs)
- Old epochs automatically pruned

#### Attack: Beacon Forgery
**Threat**: Adversary creates fake beacons with forged signatures

**Likelihood**: Low  
**Impact**: High (data integrity breach)

**Mitigations**:
- Ed25519 signatures on all beacons (signatures.py)
- Public key distribution via trusted channels
- Signature verification before accepting beacons
- Revoked keys tracked and rejected

#### Attack: Beacon Tampering
**Threat**: Adversary modifies beacon content in transit

**Likelihood**: Medium  
**Impact**: Medium

**Mitigations**:
- HMAC-SHA256 for beacon authentication
- TLS/QUIC encryption for network transport
- Hash chain in audit logs detects tampering
- Signature covers all beacon metadata

### 3. Access Control Attacks

#### Attack: Privilege Escalation
**Threat**: User gains unauthorized access to higher privilege levels

**Likelihood**: Medium  
**Impact**: High

**Mitigations**:
- Hierarchical access levels (ADMIN > USER > READ_ONLY)
- Policy evaluation engine with strict matching (access_control.py)
- All access decisions logged to audit trail
- Default deny policy when no match found

#### Attack: Policy Bypass
**Threat**: Adversary bypasses access control policies

**Likelihood**: Low  
**Impact**: High

**Mitigations**:
- Policy enforcement at SDK level (mandatory)
- Cannot access phase-encoded data without correct role key
- Audit logging tracks all access attempts
- Failed access attempts trigger alerts

### 4. Network Attacks

#### Attack: Man-in-the-Middle (MITM)
**Threat**: Adversary intercepts and modifies network traffic

**Likelihood**: Medium (without TLS)  
**Impact**: High

**Mitigations**:
- QUIC protocol with TLS 1.3 encryption
- Mutual authentication via certificates
- Beacon signatures prevent content modification
- Replay protection via epochs and nonces

#### Attack: Denial of Service (DoS)
**Threat**: Adversary floods network with fake beacons or requests

**Likelihood**: High  
**Impact**: Medium

**Mitigations**:
- Rate limiting on lock attempts
- Bloom filters prevent redundant beacon processing
- Signature verification rejects invalid beacons early
- Network-level DoS protection (firewall, rate limiting)

### 5. Side Channel Attacks

#### Attack: Timing Attack
**Threat**: Adversary infers information from operation timings

**Likelihood**: Medium  
**Impact**: Low

**Mitigations**:
- Constant-time key comparisons (hmac.compare_digest)
- Constant-time cryptographic operations
- Random delays can be added for high-security deployments

#### Attack: Memory Analysis
**Threat**: Adversary extracts keys from memory dumps

**Likelihood**: Low (requires physical access)  
**Impact**: High

**Mitigations**:
- Secure key storage in HSM for production
- Memory protection via OS-level security
- Key rotation limits exposure window
- Clear sensitive data from memory after use

## Compliance and Standards

### Security Standards

- **Cryptography**: NIST-approved algorithms (Ed25519, SHA-256, HKDF)
- **Key Management**: NIST SP 800-57 guidelines
- **Audit Logging**: Common Log Format with tamper evidence
- **Access Control**: RBAC following NIST SP 800-162

### Privacy Regulations

- **GDPR**: Anonymization level HIGH provides compliant logging
- **CCPA**: Audit logs support data access requests
- **HIPAA**: Cryptographic access control supports healthcare use cases

## Future Considerations

### Post-Quantum Cryptography

**Threat**: Quantum computers may break Ed25519 and current signature schemes

**Timeline**: 5-10 years (according to NIST estimates)  
**Impact**: Critical (all signatures compromised)

**Mitigation Strategy**:
1. Design crypto abstraction layer for algorithm swapping
2. Monitor NIST post-quantum standardization
3. Plan migration to Kyber (key exchange) and Dilithium (signatures)
4. Implement hybrid classical+PQ schemes
5. Test with NIST PQ candidates

### Advanced Persistent Threats (APT)

**Considerations**:
- Long-term compromise detection via anomaly detection
- Periodic security audits and penetration testing
- Incident response procedures
- Forensic capabilities in audit logs

## Security Testing Requirements

### Required Tests

1. **Penetration Testing**:
   - Attempt key recovery attacks
   - Test replay attack prevention
   - Verify MITM protection
   - Test privilege escalation

2. **Fuzzing**:
   - Signature verification with malformed input
   - Phase MAC verification edge cases
   - Key derivation with invalid parameters
   - Beacon parsing with corrupted data

3. **Audit**:
   - Code review by security experts
   - Dependency vulnerability scanning
   - Static analysis (Bandit for Python)
   - Dynamic analysis with security tools

## Incident Response

### Detection

- Audit log monitoring for suspicious patterns
- Failed signature/MAC verification alerts
- Replay attack detection triggers
- Unusual access pattern detection

### Response Procedures

1. **Immediate**: Isolate compromised nodes
2. **Short-term**: Rotate affected keys
3. **Medium-term**: Forensic analysis via audit logs
4. **Long-term**: Update security policies and procedures

### Recovery

- Restore from last known good state
- Re-encrypt data with new keys if needed
- Update access control policies
- Deploy security patches

## Conclusion

ResonaGraph's security model provides defense-in-depth through:
- Strong cryptographic foundations
- Multiple layers of authentication and authorization
- Comprehensive audit logging
- Proactive threat detection and mitigation

Regular security assessments and updates to this threat model are essential to maintain security posture.

## References

- [NIST Cryptographic Standards](https://csrc.nist.gov/publications)
- [OWASP Threat Modeling](https://owasp.org/www-community/Threat_Modeling)
- [copilot-instructions.md Section 5](../.github/copilot-instructions.md)
- [design.md Security Section](../design.md)
