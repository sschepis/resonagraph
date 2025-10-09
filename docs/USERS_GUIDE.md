# ResonaGraph User's Guide

## Table of Contents
- [Introduction](#introduction)
- [Getting Started](#getting-started)
- [Basic Concepts](#basic-concepts)
- [Installation](#installation)
- [Configuration](#configuration)
- [Core Operations](#core-operations)
- [Query Language](#query-language)
- [Security and Access Control](#security-and-access-control)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Examples and Use Cases](#examples-and-use-cases)

## Introduction

ResonaGraph is a next-generation distributed graph database that implements phase-modulated superpositions over prime-based Hilbert spaces. Unlike traditional graph databases that rely on explicit data replication, ResonaGraph uses compact "resonance beacons" for coordination, achieving 80-90% bandwidth savings compared to traditional approaches.

### Key Benefits
- **High Performance**: Sub-second query latency at 1M+ nodes
- **Low Bandwidth**: 80-90% reduction in network overhead via beacon-only coordination
- **Partition Tolerance**: Resonant Eventual Consistency (REC) for graceful partition handling
- **Cryptographic Security**: Phase-key access control without central authentication
- **Familiar APIs**: Cypher-inspired query language with resonance extensions

### Core Innovation
Instead of traditional replication, ResonaGraph encodes graph elements as phase angles using prime numbers and Chinese Remainder Theorem (CRT). Data is reconstructed non-locally through "resonance locking" - a process where distributed probes align with stored phase information to recover original payloads.

## Getting Started

### Quick Start
```python
from resonagraph import Client, PhaseKey, Query

# 1. Initialize client and create phase key
client = Client("https://api.resonagraph.com/v1")
phase_key = PhaseKey.from_secret(b"your-32-byte-secret-key-here!")

# 2. Store a vertex
beacon = client.put(
    key="vertex:user_123",
    payload={"name": "Alice", "email": "alice@example.com", "age": 30},
    phase_key=phase_key,
    options={"k_primes": 48, "taper_alpha": 0.05}
)

# 3. Query with resonance extensions
query = Query("""
    MATCH (u:User {id: 'user_123'})-[:FOLLOWS*1..2]->(f) 
    COHERE ON u,f 
    RETURN f.name
""")
results = client.query(query, phase_key=phase_key)

print(f"Found {len(results['nodes'])} connected users")
```

## Basic Concepts

### Prime-Resonant Encoding
ResonaGraph represents data as phase angles in a prime-indexed space:
- **Prime Selection**: Each key gets k=32-64 primes via deterministic hash-seeded selection
- **Phase Encoding**: Payload symbols encoded as `θ_p = 2π(m_j mod p + α/φ + HMAC(p||j, K))`
- **Resonance Locking**: Probes iteratively align with stored phases to achieve R > 0.95 overlap
- **CRT Reconstruction**: Original data recovered via Chinese Remainder Theorem

### Key Components

#### Phase Keys
Cryptographic keys that control access to data:
```python
# Generate new key
phase_key = PhaseKey.generate()

# Derive from secret
phase_key = PhaseKey.from_secret(b"my-secret")

# Derive topic-specific keys
topic_key = PhaseKey.derive_topic_key(root_key, "users")
```

#### Beacons
Compact metadata structures (128-512 bytes) containing:
- Prime indices (128 bits, delta-coded)
- Epoch timestamp (32 bits)
- Phase fingerprint (64-128 bits)
- Signature/MAC (256+ bits)

#### Resonance Plane
The core computation layer:
- **Probe Synthesis**: `|Q⟩ = ∑ w_p e^{iφ_p} |p⟩`
- **Locking Dynamics**: Iterative convergence with entropy decay `S(t) = S_0 e^{-λt}`
- **Residue Extraction**: Phase differences converted to modular residues
- **CRT Reconstruction**: Payload recovery from residue system

### Data Model

#### Vertices
```python
vertex = {
    "key": "vertex:user_123",
    "payload": {
        "name": "Alice",
        "properties": {"age": 30, "role": "admin"}
    }
}
```

#### Edges
```python
edge = {
    "key": "edge:user_123:user_456:FOLLOWS",
    "src_key": "vertex:user_123",
    "dst_key": "vertex:user_456", 
    "edge_type": "FOLLOWS",
    "payload": {"since": "2024-01-15"}
}
```

## Installation

### Prerequisites
- Python 3.10+ 
- Operating System: Linux, macOS, or Windows
- Memory: ≥4GB RAM recommended
- Network: TCP/UDP access for gossip protocols

### Install from PyPI
```bash
pip install resonagraph
```

### Install from Source
```bash
git clone https://github.com/sschepis/resonagraph.git
cd resonagraph
pip install -r requirements.txt
pip install -e .
```

### Development Installation
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest resonagraph/tests/

# Run examples
PYTHONPATH=. python examples/phase1_demo.py
```

### Docker Deployment
```bash
# Run single node
docker run -p 8443:8443 resonagraph/node:latest

# Run cluster with docker-compose
docker-compose up -d
```

## Configuration

### Client Configuration
```python
from resonagraph import Client

# Basic configuration
client = Client(
    endpoint="https://api.resonagraph.com/v1",
    enable_gossip=False,  # For production, use dedicated gossip nodes
    timeout=30.0,
    retry_attempts=3
)
```

### Server Configuration
```yaml
# resonagraph.yaml
server:
  address: "0.0.0.0:8443"
  tls:
    cert_file: "/path/to/cert.pem"
    key_file: "/path/to/key.pem"

gossip:
  enabled: true
  epoch_interval: 5.0  # seconds
  heartbeat_interval: 2.0
  max_hops: 3

storage:
  backend: "rocksdb"  # Options: "rocksdb", "memory", "auto"
  path: "/var/lib/resonagraph/data"
  
  # RocksDB-specific settings (Phase 7.5)
  compression: "lz4"  # Options: "lz4", "snappy", "zstd", "none"
  block_cache_size: 268435456  # 256MB
  write_buffer_size: 134217728  # 128MB
  max_open_files: 2000
  
security:
  enable_audit: true
  audit_log: "/var/log/resonagraph/audit.log"
  anonymization_level: "high"

performance:
  k_primes: 32          # 32-64 range
  taper_alpha: 0.1      # 0.05-0.15 range
  r_min: 0.95          # Overlap threshold
  
  # Security monitoring
  threat_detection:
    enabled: true
    baseline_window: 86400  # 24 hours
    patterns:
      brute_force:
        threshold: 5
        window: 300  # 5 minutes
      key_enumeration:
        threshold: 20
        window: 60   # 1 minute
      replay_attack:
        threshold: 3
        window: 600  # 10 minutes
  
  alert_management:
    smtp:
      server: "smtp.company.com"
      port: 587
      from_email: "security@company.com"
      to_email: "soc@company.com"
      use_tls: true
      username: "security"
    webhooks:
      - "https://hooks.slack.com/services/YOUR/WEBHOOK"
      - "https://api.pagerduty.com/incidents"
    escalation:
      critical: 0      # Immediate
      high: 300        # 5 minutes
      medium: 1800     # 30 minutes
      low: 3600        # 1 hour
  
  compliance:
    enabled: true
    frameworks:
      - gdpr
      - sox
      - hipaa
      - soc2
    report_schedule: "monthly"
    output_format: "json"
    output_path: "/var/log/resonagraph/compliance/"
  
  log_analytics:
    enabled: true
    query_cache_size: 1000
    max_search_results: 10000
  s_min: 0.01          # Entropy threshold
  max_iterations: 50   # Locking iterations
```

### Tuning Parameters

#### Prime Selection (`k_primes`)
- **32**: Faster operations, lower security
- **48**: Balanced performance/security (recommended)
- **64**: Maximum security, slower operations

#### Taper Parameter (`taper_alpha`)
- **0.05**: Aggressive tapering, faster convergence
- **0.10**: Balanced (default)
- **0.15**: Gentle tapering, more robust in noisy environments

#### Resonance Thresholds
```python
# Conservative (high accuracy)
options = {"r_min": 0.98, "s_min": 0.005}

# Balanced (default)
options = {"r_min": 0.95, "s_min": 0.01}

# Aggressive (faster, lower accuracy)
options = {"r_min": 0.90, "s_min": 0.02}
```

## Core Operations

### Storing Data (`put`)
```python
# Store vertex
result = client.put(
    key="vertex:alice",
    payload={"name": "Alice", "email": "alice@company.com"},
    phase_key=phase_key,
    options={
        "k_primes": 48,
        "taper_alpha": 0.05
    }
)

# Store edge
result = client.put(
    key="edge:alice:bob:KNOWS",
    payload={"relationship": "colleague", "since": "2023-01-01"},
    phase_key=phase_key
)

print(f"Stored with {len(result['primes'])} primes")
print(f"Beacon size: {result['beacon_size']} bytes")
```

### Retrieving Data (`get`)
```python
# Simple retrieval
result = client.get("vertex:alice", phase_key)

if result['found']:
    print(f"Payload: {result['payload']}")
    print(f"Lock time: {result['metrics']['lock_time']:.3f}s")
    print(f"Converged: {result['metrics']['converged']}")
    
    # Check if conflict was resolved
    if result['conflict_resolved']:
        rec_info = result['rec_info']
        print(f"Resolved conflict between {rec_info['num_candidates']} epochs")
else:
    print("Data not found")
```

### Graph Traversal (`traverse`)
```python
# Traverse with coherence bias
results = client.traverse(
    start_key="vertex:alice",
    pattern="FOLLOWS",           # Edge type to follow
    phase_key=phase_key,
    max_depth=3,                 # Maximum hops
    use_coherence=True          # Apply H_G bias for efficiency
)

# Process results
vertices = [r for r in results if r['type'] == 'vertex']
edges = [r for r in results if r['type'] == 'edge']

print(f"Found {len(vertices)} vertices, {len(edges)} edges")
```

## Query Language

ResonaGraph supports a Cypher-inspired query language with resonance extensions.

### Basic Syntax
```cypher
MATCH (pattern)
[WHERE conditions]
[COHERE ON variables]
[EPOCH WINDOW ±n]
RETURN projection
```

### MATCH Patterns
```cypher
-- Simple vertex match
MATCH (u:User {id: "alice"})

-- Relationship traversal
MATCH (u:User)-[:FOLLOWS]->(f:User)

-- Variable-length paths
MATCH (u:User)-[:FOLLOWS*1..3]->(f:User)

-- Complex patterns
MATCH (u:User {active: true})-[:FOLLOWS]->(f)-[:LIKES]->(p:Post)
```

### WHERE Clauses
```cypher
-- Property filters
WHERE u.age > 18 AND u.active = true

-- Existence checks
WHERE exists(u.email)

-- Pattern filters
WHERE f.name STARTS WITH "A"
```

### Resonance Extensions

#### COHERE ON
Apply coherence bias for efficient subgraph traversal:
```cypher
MATCH (u:User {id: "alice"})-[:FOLLOWS*1..2]->(f)
COHERE ON u,f  -- Bias toward coherent subgraphs
RETURN f.name
```

#### EPOCH WINDOW
Filter beacons by epoch drift tolerance:
```cypher
MATCH (u:User)
EPOCH WINDOW +5  -- Only epochs within ±5 of latest
RETURN u.name
```

### Return Projections
```cypher
-- Simple properties
RETURN u.name, u.age

-- Entire nodes
RETURN u, f

-- Expressions
RETURN u.name AS user_name, count(f) AS follower_count

-- Aggregations  
RETURN avg(u.age), max(u.created_at)
```

### Complete Examples
```python
# Find mutual connections
query = Query("""
    MATCH (a:User {id: "alice"})-[:FOLLOWS]->(mutual)<-[:FOLLOWS]-(b:User {id: "bob"})
    COHERE ON a,b,mutual
    RETURN mutual.name, mutual.email
""")

# Recent posts from followed users
query = Query("""
    MATCH (u:User {id: "alice"})-[:FOLLOWS]->(f)-[:POSTED]->(p:Post)
    WHERE p.created_at > date('2024-01-01')
    EPOCH WINDOW +2
    RETURN f.name, p.title, p.created_at
    ORDER BY p.created_at DESC
    LIMIT 10
""")

# Execute query
results = client.query(query, phase_key, params={})
```

## Security and Access Control

### Phase Key Management
```python
# Generate root key (store securely!)
root_key = PhaseKey.generate()

# Derive application-specific keys
user_key = PhaseKey.derive_topic_key(root_key, "users")
post_key = PhaseKey.derive_topic_key(root_key, "posts")

# Key rotation (production)
from resonagraph.security import KeyHierarchy
hierarchy = KeyHierarchy(root_key)
new_key = hierarchy.rotate_key("users", retain_old=True)
```

### Access Control Policies
```python
from resonagraph.security import AccessControl, AccessPolicy, AccessLevel

ac = AccessControl(key_hierarchy)

# Create role-based policies
ac.add_policy(AccessPolicy(
    resource="vertex:user_*",
    action="read",
    principal="role:user",
    level=AccessLevel.READ_ONLY
))

ac.add_policy(AccessPolicy(
    resource="vertex:sensitive_*", 
    action="*",
    principal="role:admin",
    level=AccessLevel.ADMIN
))
```

### Audit Logging
```python
from resonagraph.security import AuditLogger, AnonymizationLevel

# Configure audit logging
audit_logger = AuditLogger(
    log_file="/var/log/resonagraph/audit.log",
    anonymization_level=AnonymizationLevel.HIGH,
    enable_hash_chain=True
)

# Audit logging is automatic for all operations
result = client.get("vertex:alice", phase_key)
# → Generates audit log entry with anonymized identifiers
```

### Best Practices
1. **Never hardcode phase keys** - use environment variables or key management systems
2. **Use topic-specific keys** - derive separate keys for different data types
3. **Enable audit logging** - especially for compliance requirements
4. **Rotate keys regularly** - every 24h for phase keys, 30d for signatures
5. **Monitor failed access attempts** - may indicate attack or misconfiguration

### Security Monitoring

ResonaGraph includes comprehensive security monitoring capabilities to detect threats, manage alerts, and ensure compliance.

#### Threat Detection
```python
from resonagraph.security import ThreatDetector, SecurityMonitor

# Create threat detector with custom callback
def handle_security_alert(alert):
    if alert.threat_level.value >= 4:  # HIGH or CRITICAL
        send_notification(alert)
    log_alert(alert)

detector = ThreatDetector(
    alert_callback=handle_security_alert,
    baseline_window=24 * 3600  # 24-hour behavioral baseline
)

# Process audit events
for event in audit_stream:
    alerts = detector.analyze_event(event)
    if alerts:
        print(f"Detected {len(alerts)} security alerts")
```

**Automatic Threat Detection Includes:**
- Brute force attacks (5 failed logins in 5 minutes)
- Key enumeration attempts (20 accesses in 1 minute)
- Replay attacks (3 replays in 10 minutes)
- Mass data exfiltration (100 reads in 5 minutes)
- Privilege escalation attempts (10 denials in 10 minutes)

#### Alert Management
```python
from resonagraph.security import AlertManager, ThreatLevel

# Configure multi-channel notifications
alert_manager = AlertManager(
    smtp_config={
        "smtp_server": "smtp.company.com",
        "smtp_port": 587,
        "from_email": "security@company.com",
        "to_email": "soc@company.com",
        "use_tls": True,
        "username": "security",
        "password": os.getenv("SMTP_PASSWORD")
    },
    webhook_urls=[
        "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    ]
)

# Process alerts automatically
alert_manager.process_alert(security_alert)

# Get active high-priority alerts
critical_alerts = alert_manager.get_active_alerts(
    threat_level=ThreatLevel.CRITICAL
)

# Resolve false positives
alert_manager.resolve_alert(
    alert_id="alert_1234567890_0001",
    resolution_notes="Authorized penetration test"
)

# View alert statistics
summary = alert_manager.get_alert_summary(time_window=86400)
print(f"Total alerts (24h): {summary['total_alerts']}")
print(f"Active alerts: {summary['active_alerts']}")
```

#### Compliance Reporting
```python
from resonagraph.security import (
    ComplianceReporter,
    ComplianceFramework,
    ReportFormat
)

# Create compliance reporter
reporter = ComplianceReporter(
    audit_logger=audit_logger,
    rule_engine=ComplianceRuleEngine()
)

# Generate GDPR compliance report
gdpr_report = reporter.generate_compliance_report(
    framework=ComplianceFramework.GDPR,
    start_time=start_of_quarter,
    end_time=end_of_quarter,
    output_format=ReportFormat.JSON,
    output_file="gdpr_q1_2024.json"
)

print(f"Compliance Score: {gdpr_report['executive_summary']['compliance_score']:.1f}%")
print(f"Violations: {gdpr_report['executive_summary']['total_violations']}")
print(f"Status: {gdpr_report['executive_summary']['overall_status']}")

# Supported frameworks
frameworks = [
    ComplianceFramework.GDPR,      # General Data Protection Regulation
    ComplianceFramework.SOX,       # Sarbanes-Oxley
    ComplianceFramework.HIPAA,     # Health Insurance Portability
    ComplianceFramework.SOC2,      # Service Organization Control 2
    ComplianceFramework.PCI_DSS,   # Payment Card Industry
    ComplianceFramework.ISO_27001, # Information Security
    ComplianceFramework.NIST       # Cybersecurity Framework
]
```

#### Log Analytics
```python
from resonagraph.security import LogAnalyzer, QueryFilter

# Create log analyzer
analyzer = LogAnalyzer("/var/log/resonagraph/audit.log")

# Query with filters
results = analyzer.query_events(
    filters=QueryFilter(
        event_types=["login_failed", "access_denied"],
        actors=["suspicious@example.com"],
        start_time=yesterday,
        end_time=now,
        outcomes=["failure"]
    ),
    limit=100
)

print(f"Found {len(results.events)} suspicious events")

# Analyze user behavior
behavior = analyzer.analyze_user_behavior(
    actor="alice@company.com",
    start_time=start_of_month,
    end_time=end_of_month
)

print(f"Total events: {behavior['total_events']}")
print(f"Unique resources: {behavior['unique_resources']}")
print(f"Success rate: {behavior['success_rate']:.1%}")
print(f"Most active hours: {behavior['peak_hours']}")

# Security event analysis
security_summary = analyzer.analyze_security_events(
    start_time=last_week,
    end_time=now
)

if security_summary['failed_logins'] > 100:
    print("WARNING: High number of failed login attempts")
```

#### Integrated Security Monitor
```python
from resonagraph.security import SecurityMonitor

# Create comprehensive security monitor
monitor = SecurityMonitor(
    threat_detector=ThreatDetector(),
    alert_manager=AlertManager(smtp_config=smtp_config),
    compliance_reporter=ComplianceReporter(audit_logger)
)

# Start continuous monitoring
monitor.start_monitoring()

# Process events automatically
for event in audit_stream:
    alerts = monitor.process_audit_event(event)
    # Automatically:
    # - Detects threats
    # - Generates alerts
    # - Sends notifications
    # - Updates baselines

# Get comprehensive status
status = monitor.get_monitoring_status()
print(f"Events analyzed: {status['threat_detector']['events_analyzed']}")
print(f"Active alerts: {status['alert_manager']['active_alerts']}")
print(f"Compliance reports: {status['compliance_reporter']['reports_generated']}")

# Stop monitoring when done
monitor.stop_monitoring()
```

#### Security Best Practices

**Monitoring Configuration:**
1. **Enable continuous monitoring** for production systems
2. **Configure multi-channel alerts** (email + webhooks + SMS for critical)
3. **Set appropriate baseline windows** (24h for most applications)
4. **Review alerts daily** and tune detection thresholds
5. **Generate compliance reports** monthly or quarterly

**Alert Escalation:**
- **CRITICAL**: Immediate notification via all channels
- **HIGH**: 5-minute escalation if not acknowledged
- **MEDIUM**: 30-minute escalation
- **LOW**: 1-hour escalation

**Compliance Workflow:**
```python
# Monthly compliance check
def monthly_compliance_check():
    reporter = ComplianceReporter(audit_logger)
    
    # Check all required frameworks
    frameworks = [
        ComplianceFramework.GDPR,
        ComplianceFramework.SOC2,
        ComplianceFramework.ISO_27001
    ]
    
    for framework in frameworks:
        report = reporter.generate_compliance_report(
            framework=framework,
            start_time=start_of_month,
            end_time=end_of_month,
            output_format=ReportFormat.JSON
        )
        
        if report['executive_summary']['overall_status'] != 'compliant':
            escalate_compliance_issue(framework, report)
        
        archive_report(framework, report)
```

**Incident Response:**
```python
# Automated incident response
def incident_response_handler(alert):
    if alert.threat_level == ThreatLevel.CRITICAL:
        # Immediate actions
        block_suspicious_actor(alert.actor)
        notify_security_team(alert)
        create_incident_ticket(alert)
        
        # Gather forensic evidence
        analyzer = LogAnalyzer("/var/log/resonagraph/audit.log")
        forensics = analyzer.query_events(
            filters=QueryFilter(
                actors=[alert.actor],
                start_time=alert.timestamp - 3600,
                end_time=alert.timestamp
            )
        )
        
        save_forensic_evidence(alert.alert_id, forensics)
```


### Persistent Storage

ResonaGraph uses a pluggable storage system that supports both in-memory and persistent RocksDB backends.

#### Storage Configuration

```python
from resonagraph.storage import StorageManager, ROCKSDB_AVAILABLE

# Auto-detect best backend (prefers RocksDB if available)
manager = StorageManager(backend_type='auto', path='/data/resonagraph')

# Force RocksDB backend
manager = StorageManager(
    backend_type='rocksdb',
    path='/var/lib/resonagraph/db',
    compression='lz4',
    block_cache_size=256 * 1024 * 1024,  # 256MB
    write_buffer_size=128 * 1024 * 1024  # 128MB
)

# Use in-memory backend (for development/testing)
manager = StorageManager(backend_type='memory')
```

#### Primary Indexes

Store and retrieve data with namespace isolation:

```python
# Create primary index for beacons
beacons = manager.create_primary_index('beacons')

# Store data
beacons.put(b'beacon_1', {
    'phase': 0.5,
    'residues': [2, 3, 5, 7, 11],
    'magnitude': 1.2
})

# Retrieve data
data = beacons.get(b'beacon_1')
print(f"Phase: {data['phase']}")

# Scan with prefix
for key, value in beacons.scan(prefix=b'beacon_'):
    print(f"{key}: {value}")

# Check existence
if beacons.exists(b'beacon_1'):
    print("Beacon exists")
```

#### Secondary Indexes

Enable alternate key lookups:

```python
# Create secondary index
by_prime = manager.create_secondary_index('by_prime')

# Map secondary key to primary key
for i in range(10):
    primary_key = f"data_{i}".encode()
    primes = [2, 3, 5, 7, 11][:i+1]
    
    # Store primary data
    index.put(primary_key, {'primes': primes})
    
    # Create secondary index entries
    for prime in primes:
        secondary_key = f"{prime}:{i}".encode()
        by_prime.put(secondary_key, primary_key)

# Query by secondary index
for sec_key, prim_key in by_prime.scan(prefix=b'7:'):
    data = index.get(prim_key)
    print(f"Found data with prime 7: {data}")
```

#### Batch Operations

Atomic multi-operation transactions:

```python
import pickle

# Batch write for atomicity
namespace = b'primary:beacons:'
with manager.batch_write() as batch:
    for i in range(1000):
        key = f"beacon_{i}".encode()
        value = pickle.dumps({'id': i, 'phase': i * 0.1})
        batch.put(namespace + key, value)
# All operations committed atomically
```

#### Storage Statistics

Monitor storage usage and performance:

```python
# Get storage statistics
stats = manager.get_stats()

print(f"Backend: {stats['backend']}")
print(f"Library: {stats.get('library', 'N/A')}")
print(f"Total keys: {stats.get('num_keys', 0)}")

if stats['backend'] == 'rocksdb':
    print(f"SST files size: {stats.get('total_sst_files_size', 0)} bytes")
elif stats['backend'] == 'in-memory':
    print(f"Memory usage: {stats.get('memory_bytes', 0)} bytes")

print(f"Indexes: {stats['indexes']}")
```

#### Persistence and Recovery

RocksDB provides full durability with Write-Ahead Log (WAL):

```python
# Write data with persistence
manager = StorageManager(backend_type='rocksdb', path='/data/db')
index = manager.create_primary_index('data')
index.put(b'key1', {'value': 'data'})
manager.close()

# Data survives restart
manager = StorageManager(backend_type='rocksdb', path='/data/db')
index = manager.create_primary_index('data')
data = index.get(b'key1')  # Data is still there
```

#### Performance Characteristics

**In-Memory Backend:**
- Write: ~1.7M ops/sec
- Read: ~2.0M ops/sec
- Best for: Development, testing, caching

**RocksDB Backend:**
- Write: ~350K ops/sec
- Read: ~970K ops/sec
- Compression: 75-85% size reduction (LZ4)
- Best for: Production, large datasets

#### Storage Best Practices

1. **Choose the right backend**: Use RocksDB for production, in-memory for development
2. **Configure compression**: LZ4 offers best balance of speed and compression
3. **Size caches appropriately**: Larger block cache improves read performance
4. **Use batch operations**: Group writes for better throughput
5. **Monitor statistics**: Track storage growth and performance metrics
6. **Plan for backups**: Regular snapshots of RocksDB directory

## Performance Optimization

### Tuning Guidelines

#### Prime Count (`k_primes`)
```python
# For high-throughput applications
options = {"k_primes": 32}  # Faster encoding/decoding

# For security-critical applications  
options = {"k_primes": 64}  # Maximum collision resistance

# Balanced (recommended)
options = {"k_primes": 48}
```

#### Coherence Optimization
```python
# Enable coherence bias for graph traversals
results = client.traverse(
    "vertex:alice", 
    "FOLLOWS", 
    phase_key,
    use_coherence=True  # 10-50x speedup on dense graphs
)

# Use COHERE ON in queries
query = Query("""
    MATCH (u)-[:FOLLOWS*1..3]->(f)
    COHERE ON u,f  -- Biases toward minimum Hamiltonian
    RETURN f
""")
```

#### Batch Operations
```python
# Batch multiple operations
with client.batch() as batch:
    for i in range(1000):
        batch.put(f"vertex:user_{i}", {"id": i}, phase_key)
    
# Results available after commit
results = batch.results
```

### Monitoring
```python
# Enable metrics collection
client.enable_metrics()

# Check performance metrics
metrics = client.get_metrics()
print(f"Average lock time: {metrics['avg_lock_time']:.3f}s")
print(f"Lock success rate: {metrics['lock_success_rate']:.2%}")
print(f"Beacon cache hit rate: {metrics['beacon_cache_hit_rate']:.2%}")
```

### Scaling Strategies

#### Horizontal Scaling
- Add more nodes to distribute load
- Shard by prime-hash prefixes
- Use dedicated gossip nodes

#### Vertical Scaling  
- Increase memory for larger beacon caches
- Use GPU acceleration for resonance locking
- SSD storage for faster phase lookups

## Troubleshooting

### Common Issues

#### Lock Convergence Failures
```python
# Symptoms: low final_overlap, converged=False
result = client.get("vertex:alice", phase_key)
if not result['metrics']['converged']:
    print(f"Lock failed: overlap={result['metrics']['final_overlap']:.3f}")
    
# Solutions:
# 1. Increase max_iterations
options = {"max_iterations": 100}

# 2. Lower thresholds (less strict)
options = {"r_min": 0.90, "s_min": 0.02}

# 3. Check phase key correctness
try:
    alt_key = PhaseKey.from_secret(b"different-secret")
    result = client.get("vertex:alice", alt_key)
except Exception as e:
    print("Phase key mismatch detected")
```

#### High Latency
```python
# Check lock metrics
metrics = result['metrics']
if metrics['lock_time'] > 0.1:  # >100ms is slow
    print(f"Slow lock: {metrics['lock_time']:.3f}s")
    print(f"Iterations: {metrics['iterations']}")
    
# Solutions:
# 1. Use fewer primes
options = {"k_primes": 32}

# 2. Enable coherence for traversals  
use_coherence = True

# 3. Increase learning rate
learning_rate = 0.2  # Default is 0.1
```

#### Memory Usage
```python
# Monitor memory usage
import psutil
process = psutil.Process()
memory_mb = process.memory_info().rss / 1024 / 1024
print(f"Memory usage: {memory_mb:.1f} MB")

# Solutions:
# 1. Clear beacon cache periodically
client.clear_beacon_cache()

# 2. Use smaller beacon fingerprints
options = {"fingerprint_bits": 64}  # Default is 128

# 3. Enable LZ4 compression (Phase 7)
options = {"enable_compression": True}
```

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Get detailed operation logs
client.set_log_level("DEBUG")
result = client.get("vertex:alice", phase_key)
# → Detailed logs of prime selection, phase encoding, locking dynamics
```

### Diagnostic Commands
```bash
# Check system status
resonagraph status

# Validate configuration
resonagraph config validate

# Test connectivity
resonagraph ping <node_address>

# Analyze performance
resonagraph benchmark --duration 60s

# Export diagnostics
resonagraph diagnostics export --output diagnostics.json
```

## Examples and Use Cases

### Social Network
```python
def build_social_network():
    client = Client("https://api.resonagraph.com/v1")
    phase_key = PhaseKey.from_secret(b"social-network-key-32-bytes-long")
    
    # Create users
    users = [
        {"id": "alice", "name": "Alice", "age": 30},
        {"id": "bob", "name": "Bob", "age": 25},
        {"id": "carol", "name": "Carol", "age": 28}
    ]
    
    for user in users:
        client.put(f"vertex:user_{user['id']}", user, phase_key)
    
    # Create relationships
    relationships = [
        ("alice", "bob", "FOLLOWS"),
        ("alice", "carol", "FOLLOWS"), 
        ("bob", "carol", "FOLLOWS")
    ]
    
    for src, dst, rel_type in relationships:
        client.put(
            f"edge:user_{src}:user_{dst}:{rel_type}",
            {"created_at": "2024-01-01"},
            phase_key
        )
    
    # Query for recommendations
    query = Query("""
        MATCH (u:User {id: "alice"})-[:FOLLOWS]->(f)-[:FOLLOWS]->(rec)
        WHERE rec.id <> "alice"
        COHERE ON u,f,rec
        RETURN rec.name, rec.age
    """)
    
    results = client.query(query, phase_key)
    return results['nodes']
```

### Knowledge Graph
```python
def build_knowledge_graph():
    client = Client("https://api.resonagraph.com/v1")
    phase_key = PhaseKey.from_secret(b"knowledge-graph-key-32-bytes___")
    
    # Create entities
    entities = [
        {"type": "Person", "name": "Albert Einstein", "born": 1879},
        {"type": "Theory", "name": "Theory of Relativity", "year": 1915},
        {"type": "Institution", "name": "Princeton University"}
    ]
    
    for entity in entities:
        key = f"entity:{entity['type'].lower()}_{entity['name'].replace(' ', '_')}"
        client.put(key, entity, phase_key)
    
    # Create relationships
    relations = [
        ("person_albert_einstein", "theory_theory_of_relativity", "DEVELOPED"),
        ("person_albert_einstein", "institution_princeton_university", "WORKED_AT")
    ]
    
    for src, dst, rel_type in relations:
        client.put(f"edge:entity:{src}:entity:{dst}:{rel_type}", {}, phase_key)
    
    # Query for related concepts
    query = Query("""
        MATCH (p:Person {name: "Albert Einstein"})-[r]->(related)
        COHERE ON p,related
        RETURN type(r) as relationship, related.name as name
    """)
    
    return client.query(query, phase_key)
```

### IoT Sensor Network
```python
def build_iot_network():
    from datetime import datetime, timedelta
    
    client = Client("https://api.resonagraph.com/v1")
    phase_key = PhaseKey.from_secret(b"iot-sensors-key-32-bytes-long___")
    
    # Create sensor nodes
    sensors = [
        {"id": "temp_01", "location": "Building A", "type": "temperature"},
        {"id": "humid_01", "location": "Building A", "type": "humidity"},
        {"id": "temp_02", "location": "Building B", "type": "temperature"}
    ]
    
    base_time = datetime.now()
    
    for sensor in sensors:
        client.put(f"sensor:{sensor['id']}", sensor, phase_key)
        
        # Add recent readings
        for i in range(24):  # Last 24 hours
            reading_time = base_time - timedelta(hours=i)
            reading = {
                "sensor_id": sensor['id'],
                "timestamp": reading_time.isoformat(),
                "value": 20 + (i % 10),  # Simulated values
                "unit": "celsius" if sensor['type'] == "temperature" else "percent"
            }
            
            reading_key = f"reading:{sensor['id']}_{reading_time.strftime('%Y%m%d_%H')}"
            client.put(reading_key, reading, phase_key)
            
            # Link reading to sensor
            client.put(f"edge:sensor:{sensor['id']}:{reading_key}:HAS_READING", {}, phase_key)
    
    # Query for recent temperature readings
    query = Query("""
        MATCH (s:Sensor {type: "temperature"})-[:HAS_READING]->(r:Reading)
        WHERE r.timestamp > date('2024-01-01')
        EPOCH WINDOW +1
        RETURN s.location, r.value, r.timestamp
        ORDER BY r.timestamp DESC
        LIMIT 10
    """)
    
    return client.query(query, phase_key)
```

### Real-Time Analytics
```python
def real_time_analytics():
    client = Client("https://api.resonagraph.com/v1")
    phase_key = PhaseKey.from_secret(b"analytics-key-32-bytes-long____")
    
    # Stream processing simulation
    events = [
        {"user_id": "alice", "action": "login", "timestamp": "2024-01-01T10:00:00"},
        {"user_id": "alice", "action": "view_page", "page": "/dashboard", "timestamp": "2024-01-01T10:01:00"},
        {"user_id": "bob", "action": "login", "timestamp": "2024-01-01T10:02:00"}
    ]
    
    for event in events:
        # Store event
        event_key = f"event:{event['user_id']}_{event['timestamp']}"
        client.put(event_key, event, phase_key)
        
        # Link to user
        client.put(f"edge:user:{event['user_id']}:{event_key}:PERFORMED", {}, phase_key)
    
    # Real-time query for user activity
    query = Query("""
        MATCH (u:User {id: "alice"})-[:PERFORMED]->(e:Event)
        WHERE e.timestamp > datetime() - duration({hours: 1})
        COHERE ON u,e
        RETURN e.action, e.timestamp
        ORDER BY e.timestamp DESC
    """)
    
    return client.query(query, phase_key)
```

For more examples, see the `examples/` directory in the repository.

---

## Next Steps

- Read the [System Reference Guide](SYSTEM_REFERENCE.md) for technical details
- Check out the [Security Guidelines](SECURITY.md) for production deployments
- Browse the [API Reference](API_REFERENCE.md) for complete method documentation
- Join the community at [GitHub Discussions](https://github.com/sschepis/resonagraph/discussions)

## Support

- **Documentation**: [https://resonagraph.readthedocs.io](https://resonagraph.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/sschepis/resonagraph/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sschepis/resonagraph/discussions)
- **Email**: support@resonagraph.io