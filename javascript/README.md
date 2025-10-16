# ResonaGraph - JavaScript/TypeScript Port

Prime-Resonant Graph Database - JavaScript/TypeScript implementation with server, CLI, and library.

## Overview

This is the JavaScript/TypeScript port of ResonaGraph, implementing the same core concepts as the Python version:

- **Phase Encoding**: Data encoded as phase angles in prime-indexed Hilbert spaces
- **Resonance Locking**: Iterative convergence for data reconstruction
- **Chinese Remainder Theorem**: Mathematical guarantee of reconstruction
- **Phase-Key Cryptography**: Built-in access control

## Installation

### From npm (Coming Soon)

```bash
npm install resonagraph
```

### From Source

```bash
cd javascript
npm install
npm run build
```

### Global Installation

To install the CLI and server globally:

```bash
cd javascript
npm install -g
```

This will make `resonagraph` and `resonagraph-server` available system-wide.

## Quick Start

### Using the Library

```typescript
import { Client, PhaseKey } from 'resonagraph';

// Initialize client
const client = new Client('http://localhost:8443');
const phaseKey = PhaseKey.fromPassphrase('my-secret-passphrase');

// Store data
const beacon = client.put(
  'user:alice',
  { name: 'Alice', email: 'alice@example.com', age: 30 },
  phaseKey,
  {
    kPrimes: 48,      // 32-64 primes
    taperAlpha: 0.1,  // Convergence speed
  }
);

console.log('Stored with beacon:', beacon);

// Retrieve data
const result = client.get('user:alice', phaseKey);
console.log('Retrieved:', result.payload);
console.log('Lock metrics:', result.metrics);
```

### Using the CLI

```bash
# Store data
resonagraph put user:alice '{"name":"Alice","email":"alice@example.com"}' \
  --key my-secret-key

# Retrieve data
resonagraph get user:alice --key my-secret-key

# Generate a new phase key
resonagraph genkey --output my-phase-key.txt

# View client statistics
resonagraph stats
```

### Running the Server

```bash
# Start the server
resonagraph-server

# Or with custom port
PORT=9000 resonagraph-server

# Or using npm
npm run server
```

The server will start on `http://0.0.0.0:8443` by default.

## API Reference

### Core Classes

#### `PhaseKey`

Manages cryptographic phase keys for access control.

```typescript
// Create from passphrase
const key = PhaseKey.fromPassphrase('my-passphrase');

// Create from raw bytes
const key = PhaseKey.fromSecret(Buffer.from('...'));

// Generate random key
const key = PhaseKey.generate();

// Derive child key
const childKey = key.deriveKey('topic-name');
```

#### `Client`

Main client for interacting with ResonaGraph.

```typescript
const client = new Client('http://localhost:8443');

// Put operation
client.put(key, payload, phaseKey, options);

// Get operation
client.get(key, phaseKey, options);

// Get statistics
client.getStats();
```

#### `PrimeSelector`

Deterministic prime selection based on keys.

```typescript
const selector = new PrimeSelector();
const primes = selector.selectPrimes('my-key', 48);
console.log(`Selected ${primes.length} primes`);
```

#### `PhaseEncoder`

Encodes data as phase angles.

```typescript
const encoder = new PhaseEncoder({ taperAlpha: 0.1 });
const encoded = encoder.encode(payload, primes, phaseKey);
```

### Server API

The ResonaGraph server provides a REST API:

#### `POST /v1/put`

Store data with phase encoding.

**Headers:**
- `X-Phase-Key`: Phase key secret (optional, defaults to 'default-secret')

**Body:**
```json
{
  "key": "user:alice",
  "payload": {
    "name": "Alice",
    "email": "alice@example.com"
  },
  "options": {
    "kPrimes": 48,
    "taperAlpha": 0.1
  }
}
```

**Response:**
```json
{
  "success": true,
  "beacon": {
    "key": "user:alice",
    "primes": [2, 3, 5, ...],
    "epoch": 1234567890,
    "timestamp": 1234567890123
  }
}
```

#### `POST /v1/get`

Retrieve data by resonance locking.

**Headers:**
- `X-Phase-Key`: Phase key secret (optional)

**Body:**
```json
{
  "key": "user:alice",
  "options": {}
}
```

**Response:**
```json
{
  "success": true,
  "payload": {
    "name": "Alice",
    "email": "alice@example.com"
  },
  "metrics": {
    "converged": true,
    "iterations": 15,
    "finalOverlap": 0.9876,
    "finalEntropy": 0.0012,
    "metrics": {
      "lockTime": 23,
      "entropyFinal": 0.0012
    }
  }
}
```

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2025-01-01T00:00:00.000Z"
}
```

#### `GET /stats`

Server statistics.

**Response:**
```json
{
  "endpoint": "http://localhost:8443",
  "storedKeys": 42,
  "primeCacheSize": 9592
}
```

## Architecture

The JavaScript port follows the same layered architecture as the Python version:

```
┌─────────────────────────────────────┐
│       Client SDK (api/Client.ts)    │
│   • put  • get  • query  • traverse │
└─────────────────────────────────────┘
                 ↕
┌─────────────────────────────────────┐
│      Resonance Plane (resonance/)   │
│  • ProbeSynthesizer                 │
│  • ResonanceLock                    │
│  • ResidueExtractor (CRT)           │
└─────────────────────────────────────┘
                 ↕
┌─────────────────────────────────────┐
│        Core Modules (core/)         │
│  • PhaseKey                         │
│  • PrimeSelector                    │
│  • PhaseEncoder                     │
└─────────────────────────────────────┘
```

## Development

### Build

```bash
npm run build
```

### Test

```bash
npm test
```

### Lint

```bash
npm run lint
```

### Format

```bash
npm run format
```

## Key Features

### 🔢 Prime Selection

Deterministic selection of 32-64 primes based on key hashing:

```typescript
const primes = selector.selectPrimes('my-key', 48);
// Always returns same primes for same key
```

### 🌊 Phase Encoding

Data encoded as phase angles using the formalism:

```
θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
```

Where:
- `m_j`: Symbol (byte chunk)
- `p`: Prime from selected set
- `α`: Taper parameter (0.05-0.15)
- `φ`: Golden ratio (1+√5)/2
- `HMAC`: Cryptographic MAC

### 🔄 Resonance Locking

Iterative convergence process:

1. Initialize probe state with tapered weights
2. Compute overlap: `R = |⟨Q|A⟩|`
3. Update probe phases
4. Check convergence: `R > 0.95 AND S < 0.01`
5. Repeat until convergence or max iterations

### 🔐 Phase-Key Cryptography

Built-in access control:
- Without correct phase key, probes misalign (R < R_min)
- Key hierarchy via HKDF
- Automatic key rotation support (24h recommended)

## Differences from Python Version

1. **Storage**: Current implementation uses in-memory Map for demo purposes. Production would use RocksDB or network storage.

2. **Gossip Layer**: Not yet implemented. Current version is single-node only.

3. **GPU Acceleration**: Not yet implemented. Pure CPU implementation.

4. **Query Language**: Basic Cypher support not yet implemented.

5. **Compression**: LZ4 compression planned but not yet implemented.

## Roadmap

- [ ] RocksDB storage layer integration
- [ ] Gossip protocol with Kademlia DHT
- [ ] Query language parser (Cypher-like)
- [ ] WebSocket real-time updates
- [ ] GPU acceleration via WebGPU
- [ ] LZ4 compression for beacons
- [ ] Full test suite
- [ ] Benchmarks and performance testing

## License

MIT License - see [LICENSE](../LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/sschepis/resonagraph/issues)
- **Documentation**: See main [README](../README.md)
- **Email**: support@resonagraph.io

---

Built with ❤️ by the ResonaGraph Team
