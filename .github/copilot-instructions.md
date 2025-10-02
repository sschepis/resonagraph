# Copilot Instructions for resonagraph

## About This Project
ResonaGraph is a next-generation distributed graph database implementing the Prime-Resonant Graph Database formalism by Sebastian Schepis (2025). It encodes graph elements as phase-modulated superpositions over prime-based Hilbert spaces, enabling non-local data reconstruction via resonance locking and Chinese Remainder Theorem (CRT) synthesis.

### Core Innovation
Instead of traditional replication, ResonaGraph uses compact "resonance beacons" for coordination, achieving 80-90% bandwidth savings while maintaining eventual consistency through entropy-guided conflict resolution (Resonant Eventual Consistency - REC).

## System Architecture Components

### 1. Layered Architecture
When implementing ResonaGraph components, follow this layered plane-based structure:

#### Client SDK Layer
- **Probe Synthesis**: Generate probe states |Q⟩ = ∑ w_p e^{iφ_p} |p⟩ for data retrieval
- **Query Execution**: Parse and execute Cypher-like queries with resonance extensions
- **Caching**: Implement local cache for beacons and reconstructed payloads
- **Phase Key Management**: Handle cryptographic phase keys for access control

#### Gossip Plane
- **Protocol**: Use QUIC for low-latency multicast; UDP as fallback
- **Beacon Structure**: Implement compact beacons (128-512 bytes):
  - Prime Index ID (delta-coded, 128 bits for 32 primes)
  - Epoch timestamp (32-bit, τ=2-13 seconds)
  - Phase Fingerprint (quantized phases, 64-128 bits)
  - Signature/MAC (Ed25519 + HMAC for integrity)
- **Discovery**: Kademlia DHT keyed on prime hashes with Bloom filters for deduplication
- **Gossip Mechanics**: Periodic floods (every τ/2) with TTL=3 hops, heartbeat beacons for liveness

#### Resonance Plane
- **Locking Dynamics**: Implement iterative overlap computation R = |⟨Q|A⟩|
  - Target thresholds: R_min=0.95, S_min=0.01 (tunable)
  - Iterations: O(k log(1/ε)), typically k=32 primes, ε=10^-6
  - Track entropy S(t) decay via S(t) = S_0 e^{-λt}
  - Track resonance score RS(t) ≈ RS_★(1 - e^{-γt})
- **Residue Extraction**: Extract phase differences Δθ_p → r_j ≡ m_j mod p_i
- **CRT Reconstruction**: Implement Chinese Remainder Theorem for payload reconstruction
  - Ensure product ∏ p_i ≥ 2^{8b} for b-byte symbols

#### Storage Layer
- **Local KV Store**: Use RocksDB for encoded phases θ_p and prime indices
- **No Cross-Node Replication**: Data is reconstructable via beacons
- **WAL**: Write-Ahead Log for phase durability

#### Monitoring Layer
- **Entropy Dashboards**: Track S(t) and RS(t) histograms
- **Drift Alerts**: Alert when drift > τ/2, trigger auto-epoch reset
- **Prometheus Endpoints**: Export metrics for observability

### 2. Data Model Implementation

#### Graph Primitives
- **Vertex**: Key (string), Payload (JSON dict), Address |A(v)⟩ (latent phases)
- **Edge**: Tuple (src_key, dst_key, type), Payload (dict), Salt s_e for randomness
- **Property**: Attached to vertex/edge, chunked into symbols m_j ≤ M=2^16

#### Encoding Formalism
- **Prime Selection**: Hash key, seed Eratosthenes sieve, select k=32-64 primes (2 to 10^12 range)
- **Phase Coding**: θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
  - Use golden ratio φ=(1+√5)/2
  - Apply taper_alpha for weighted probes (default α=0.1)
- **Subgraph Coherence**: Bias queries toward minimum Hamiltonian H_G for efficient locks

### 3. Resonant Eventual Consistency (REC)

#### Conflict Resolution Algorithm
When implementing REC conflict resolution:

1. **Detect Conflict**: Fetch beacons for key's primes P(a), multiple epochs indicate fork
2. **Simulate Dynamics**: For each candidate epoch:
   - Initialize S_0 (from payload complexity) and RS_0 (from fingerprint mismatch)
   - Evolve S(t) = S_0 e^{-λt} where λ depends on prime count k
   - Evolve RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt} where γ depends on phase alignment
   - Run until t_max (e.g., 10τ) or steady state reached
3. **Compute Steady States**: Extract S_stable and RS_stable at convergence
4. **Select Winner**: Choose epoch e where S_stable^e < S_stable^e' AND RS_stable^e > RS_stable^e'
   - Tiebreak by epoch recency or quorum vote
5. **Propagate**: Gossip winning beacon, prune losers via Bloom filters

#### Consistency Guarantees
- **REC Mode** (default): Entropy-guided conflict resolution, partition-tolerant
- **Snapshot Mode**: Strong consistency via leader election
- **Causal Mode**: Vector clocks for causal ordering
- **Linearizability**: For single-key reads with phase key

### 4. API Design Patterns

#### SDK Operations
Implement these core operations in Python 3.10+, Node.js 18+, Go 1.21:

- **put(key, payload, phase_key, options)**: Write vertex/edge with encoding
  - Options: k_primes (32-64), taper_alpha (0.05-0.15)
  - Returns beacon metadata
- **get(key, phase_key)**: Retrieve by resonance locking
  - Returns payload + metrics (lock_time, entropy_final)
- **traverse(start_key, pattern, phase_key)**: Graph traversal with coherence bias
- **query(cypher_query, phase_key, params)**: Execute Cypher-like query

#### Query Language Extensions
Extend Cypher with resonance primitives:
- **COHERE ON path**: Apply H_G bias for coherent subgraph traversal
- **EPOCH WINDOW ±n**: Filter beacons by epoch drift tolerance
- **Lazy Evaluation**: Support partial locks for approximate results

#### REST/GraphQL Gateway
- Endpoint: `/v1/query` (POST, JSON body)
- Auth: Bearer token + phase_key in headers
- Response: Include nodes, edges, and metrics (lock_time, entropy_final)

### 5. Security and Access Control

#### Phase-Key Cryptographic Model
- **Enforcement**: Without correct phase key K, probes misalign (R < R_min)
- **Key Hierarchy**: 
  - Root K_root derives per-topic K_topic via HKDF
  - Rotate keys every 24h for security
- **Cloaking**: Fold semantic keys into HMAC for role-based access views

#### Integrity and Authentication
- **Beacon Signatures**: Use Ed25519 for beacon integrity
- **Phase MACs**: Per-chunk HMAC for phase authenticity
- **Audit Logs**: Track lock attempts with anonymized fingerprints

#### Threat Model
- Assume honest-majority nodes
- Resist replay attacks via epochs
- Resist MITM via QUIC TLS
- Future: Post-quantum crypto (Kyber) for v2

### 6. Performance and Scalability

#### Complexity Targets
- **Write**: O(k) encoding + O(k log n) gossip overhead
- **Read**: O(k·iter) lock iterations (iter≤50) + O(k log² M) CRT
- **Traversal**: O(|E|·k) with 10-50x coherence speedup on dense graphs
- **Benchmark Target**: 200 QPS on 1k-node cluster, p99 latency <50ms

#### Scaling Strategies
- **Horizontal**: Auto-join for new nodes, shard by prime-hash
- **Vertical**: GPU acceleration for locking (CuPy bindings)
- **Compression**: LZ4 for 2:1 beacon compression
- **Limits**: Design for 10M edges per node

#### Optimization Guidelines
- Use tapered weights (α=0.05-0.1) for faster convergence
- Increase k_primes (48-64) for collision resistance in high-load scenarios
- Tune λ and γ parameters based on network characteristics
- Cache beacon fingerprints for frequently accessed keys

### 7. Testing Strategies

#### Unit Testing
- **Mock Resonance**: Use fixed primes for deterministic tests
- **Phase Encoding**: Verify θ_p calculations match specifications
- **CRT Reconstruction**: Test symbol recovery across various prime sets
- **Entropy Dynamics**: Validate S(t) and RS(t) evolution equations

#### Integration Testing
- **Beacon Gossip**: Test multi-node beacon propagation
- **Conflict Resolution**: Simulate partition scenarios, verify REC selection
- **Lock Convergence**: Measure iterations to reach R_min, S_min thresholds
- **ChaosMonkey**: Introduce random partitions and failures

#### Performance Testing
- **Lock Time Distribution**: Measure p50, p95, p99 latencies
- **Gossip Overhead**: Track beacon bandwidth vs. payload size
- **Scaling Tests**: Verify linear scaling with node count
- **Memory Profiling**: Ensure RocksDB memory usage stays within bounds

#### Fuzz Testing
- **Phase Perturbations**: Random noise injection in phases
- **Malformed Beacons**: Test parser robustness
- **Prime Collisions**: Simulate rare collision scenarios

## Code Style and Standards

### Mathematical and Cryptographic Code
- Use descriptive variable names aligned with mathematical notation:
  - `theta_p` for phase angles, `prime_indices` for P(a)
  - `entropy_t` for S(t), `resonance_score` for RS(t)
- Comment complex equations with references to design.md sections
- Keep cryptographic operations in isolated, auditable modules
- Use constant-time comparisons for security-critical paths

### Performance-Critical Sections
- Profile before optimizing; target hot paths in locking iterations
- Prefer NumPy/SciPy vectorized operations for phase computations
- Use GMP for large integer operations in CRT
- Consider GPU acceleration for batch locking operations

### Naming Conventions
- **Classes**: PascalCase (e.g., `ResonancePlane`, `PhaseKey`)
- **Functions**: snake_case (e.g., `synthesize_probe`, `extract_residue`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `R_MIN`, `S_MIN`, `TAU_EPOCH`)
- **Mathematical symbols**: Follow paper notation where practical

## Dependencies and Tools

### Core Dependencies
- **QUIC**: quiche library for low-latency networking
- **Bigints**: GMP for modular arithmetic and CRT
- **Numerics**: NumPy/SciPy for entropy simulations
- **Storage**: RocksDB for local KV store
- **Crypto**: Ed25519, HMAC-SHA256, HKDF for phase keys

### Development Tools
- **Monitoring**: Prometheus for metrics, Grafana for dashboards
- **Deployment**: Helm charts for Kubernetes
- **Testing**: pytest (Python), Jest (Node.js), go test (Go)
- **Profiling**: cProfile (Python), pprof (Go) for performance analysis

## Documentation Requirements

### API Documentation
- Document all public SDK methods with:
  - Parameter types and ranges (e.g., k_primes: 32-64)
  - Return values including metrics
  - Example usage with phase_key handling
  - Complexity analysis (Big-O notation)

### Algorithm Documentation
- Reference design.md sections for equations
- Include numerical examples for complex operations (encoding, CRT, REC)
- Provide convergence criteria and iteration bounds
- Document tunable parameters with recommended ranges

### Deployment Documentation
- Configuration YAML structure and parameter ranges
- Multi-node setup procedures
- Monitoring and alerting setup
- Backup and recovery procedures

## Contribution Workflow

### Implementation Phases
1. **Foundation**: Storage layer, prime selection, phase encoding
2. **Gossip**: Beacon structure, DHT, QUIC networking
3. **Resonance**: Locking dynamics, residue extraction, CRT
4. **REC**: Conflict detection, thermodynamic selection
5. **APIs**: SDK implementation, query language parser
6. **Security**: Phase-key system, signatures, auditing
7. **Optimization**: GPU acceleration, caching, compression

### Commit Guidelines
- Reference design.md sections in commit messages
- Include performance metrics for optimization commits
- Tag security-related changes for review
- Keep mathematical changes separate from refactoring

### Code Review Focus
- Verify cryptographic implementations against specifications
- Check convergence guarantees in locking algorithms
- Validate beacon structure matches design.md Section 2.2.1
- Ensure REC resolution follows algorithm in rec.md
- Review performance impacts of prime selection strategies

## Best Practices

### Resonance Locking
- Always check convergence (R > R_min AND S < S_min) before returning
- Limit iterations to prevent infinite loops (max ~50-100)
- Log entropy metrics for debugging convergence issues
- Cache probe states for repeated queries on same key

### Beacon Management
- Compress beacons with LZ4 before gossip transmission
- Use Bloom filters to avoid redundant beacon storage
- Implement exponential backoff for gossip retries
- Prune old epochs (>10τ) to bound memory

### Error Handling
- Distinguish between:
  - **Lock failures**: R < R_min (likely wrong phase key)
  - **Timeout failures**: Iterations exceeded (increase k_primes or check network)
  - **Conflict failures**: REC unable to resolve (manual intervention needed)
- Provide actionable error messages with metrics
- Implement graceful degradation (return partial results with warnings)

### Security Considerations
- Never log phase keys or raw phase values
- Use HSM for K_root in production
- Rotate phase keys on schedule (default 24h)
- Validate beacon signatures before processing
- Rate-limit lock attempts to prevent DoS

### Backward Compatibility
- Version beacon structures with format field
- Support multiple prime selection algorithms
- Allow graceful migration between consistency modes
- Maintain API compatibility within major versions

## Future Considerations

### Roadmap Alignment
When implementing, consider future extensions:
- **v1.1**: Vector embeddings in phases for semantic resonance
- **Integrations**: Kafka for event streams, Spark for analytics
- **Quantum**: Qiskit integration for true Hilbert space operations
- **Post-Quantum**: Kyber/Dilithium for quantum-resistant crypto

### Research Areas
- Machine learning for adaptive λ/γ tuning
- Elliptic curve alternatives for prime collisions
- Semantic coherence metrics for knowledge graphs
- Edge computing optimizations for IoT deployments
