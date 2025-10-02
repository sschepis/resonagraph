# ResonaGraph

**Prime-Resonant Graph Database** - A next-generation distributed graph database implementing phase-modulated superpositions over prime-based Hilbert spaces.

## Overview

ResonaGraph implements the Prime-Resonant Graph Database formalism by Sebastian Schepis (2025). It encodes graph elements as phase-modulated superpositions, enabling non-local data reconstruction via resonance locking and Chinese Remainder Theorem (CRT) synthesis.

### Core Innovation

Instead of traditional replication, ResonaGraph uses compact "resonance beacons" for coordination:
- **80-90% bandwidth savings** compared to traditional replication
- **Eventual consistency** through entropy-guided conflict resolution (REC)
- **Phase-key cryptographic access control** for security

## Quick Start

```python
from resonagraph import Client, PhaseKey, Query

# Initialize client
client = Client("https://api.resonagraph.com/v1")
pk = PhaseKey.from_secret(b"32-byte-secret")

# Write data with encoding
beacon = client.put(
    key="vertex:user_123",
    payload={"name": "Alice", "props": {"age": 30}},
    phase_key=pk,
    options={"k_primes": 48, "taper_alpha": 0.05}
)

# Query with Cypher-like syntax + resonance extensions
q = Query("MATCH (u:User {id: 'user_123'})-[:FOLLOWS*1..2]->(f) COHERE ON u,f RETURN f.name")
results = client.query(q, phase_key=pk, params={"depth": 2})
```

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Development

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest resonagraph/tests/

# Run specific test
python -m pytest resonagraph/tests/test_prime_selection.py -v
```

## Architecture

ResonaGraph implements a layered architecture:

1. **Client SDK Layer**: Probe synthesis, query execution, caching
2. **Gossip Plane**: QUIC protocol, beacon structure, DHT discovery
3. **Resonance Plane**: Locking dynamics, residue extraction, CRT reconstruction
4. **Storage Layer**: RocksDB for encoded phases and prime indices
5. **Monitoring Layer**: Entropy dashboards, drift alerts, Prometheus endpoints

See [design.md](design.md) for detailed architecture documentation.

## Implementation Status

### Phase 1: Foundation ✓
- [x] Prime selection module (Eratosthenes sieve)
- [x] Phase encoding module (θ_p calculations)
- [x] Phase key management (HKDF)
- [x] Basic client SDK structure
- [x] Unit tests

### Phase 2: Gossip Plane ✓
- [x] Beacon structure implementation (192 bytes)
- [x] Kademlia DHT for discovery
- [x] Bloom filters for deduplication
- [x] Gossip manager with periodic flooding
- [x] Client SDK integration
- [x] Comprehensive unit tests (59 gossip tests)

### Phase 3: Resonance Plane (Planned)
- [ ] Probe synthesis
- [ ] Locking dynamics
- [ ] CRT reconstruction

### Phase 4-7: See [copilot-instructions.md](.github/copilot-instructions.md)

## Key Concepts

### Phase Encoding
θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))

Where:
- **m_j**: Symbol (byte chunk) from payload
- **p**: Prime from selected set
- **α**: Taper parameter (default 0.1)
- **φ**: Golden ratio (1+√5)/2
- **K**: Phase key for cryptographic access control

### Resonant Eventual Consistency (REC)
Conflict resolution via thermodynamic selection:
- Track entropy S(t) = S_0 e^{-λt}
- Track resonance score RS(t) = RS_★(1 - e^{-γt})
- Select winner: min(S_stable) AND max(RS_stable)

See [rec.md](rec.md) for detailed algorithm.

## Documentation

- [Design Document](design.md) - Complete system architecture
- [REC Algorithm](rec.md) - Resonant Eventual Consistency details
- [Copilot Instructions](.github/copilot-instructions.md) - Implementation guidelines

## Testing

According to copilot-instructions.md testing strategy:
- **Unit Tests**: Mock resonance with fixed primes for deterministic tests
- **Integration Tests**: Multi-node beacon propagation, conflict resolution
- **Performance Tests**: Lock time distribution, scaling tests
- **Fuzz Tests**: Phase perturbations, malformed beacons

Run tests:
```bash
python -m pytest resonagraph/tests/ -v
python -m pytest resonagraph/tests/ --cov=resonagraph
```

## Contributing

See [copilot-instructions.md](.github/copilot-instructions.md) for:
- Implementation phases
- Code style and standards
- Naming conventions
- Best practices
- Security considerations

## License

See LICENSE file for details.

## References

- Schepis, S. (2025). *Prime-Resonant Graph Databases*. xAI Technical Report.
- Design document: [design.md](design.md)
- REC formalism: [rec.md](rec.md)