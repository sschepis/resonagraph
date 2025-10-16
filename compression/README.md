# ResonaCompress

File compression tool based on ResonaGraph phase-encoding principles.

## Overview

ResonaCompress reimagines the ResonaGraph distributed graph database as a file compression algorithm. Instead of encoding graph data across distributed nodes, it encodes file data as phase angles in prime-indexed mathematical spaces.

### Core Innovation

Rather than traditional compression algorithms (Huffman, LZ77, etc.), ResonaCompress uses:

- **Phase Encoding**: File bytes encoded as phase angles using prime numbers
- **Chinese Remainder Theorem**: Mathematical reconstruction guarantees
- **Cryptographic Binding**: Optional HMAC-based encryption
- **Golden Ratio Distribution**: Uniform phase distribution using φ = (1+√5)/2

## How It Works

### 1. Prime Selection

For each file, a deterministic set of 32-64 prime numbers is selected based on the file's hash. This ensures the same primes are always used for compression and decompression.

### 2. Phase Encoding

Each byte in the file is encoded as a set of phase angles using the formula:

```
θ_p = 2π(m_j mod p + α/φ + HMAC(p||j, K))
```

Where:
- **m_j**: Byte value (0-255)
- **p**: Prime number from selected set
- **α**: Taper parameter (typically 0.1)
- **φ**: Golden ratio (1+√5)/2
- **HMAC**: Optional cryptographic hash for encryption

### 3. Reconstruction

During decompression, the original bytes are reconstructed using the Chinese Remainder Theorem (CRT), which guarantees exact recovery when enough primes are used.

## Installation

```bash
cd compression
npm install
npm run build
```

### Global Installation

```bash
npm install -g
```

This makes the `resonacompress` command available system-wide.

## Usage

### Command Line

#### Compress a File

```bash
# Basic compression
resonacompress compress input.txt

# Specify output file
resonacompress compress input.txt output.resc

# Use more primes for better security (32-64 range)
resonacompress compress input.txt -p 64

# Adjust taper parameter (0.05-0.15 range)
resonacompress compress input.txt -a 0.05

# Enable encryption with secret
resonacompress compress input.txt -s
```

#### Decompress a File

```bash
# Basic decompression
resonacompress decompress input.txt.resc

# Specify output file
resonacompress decompress input.txt.resc output.txt
```

#### View File Information

```bash
# Display compressed file metadata
resonacompress info input.txt.resc
```

### Programmatic API

```typescript
import { ResonaCompress } from 'resonacompress';

const compressor = new ResonaCompress();

// Compress a file
const result = await compressor.compressFile('input.txt', 'output.resc', {
  primeCount: 48,      // Number of primes (32-64)
  taperAlpha: 0.1,     // Taper parameter (0.05-0.15)
  useSecret: false,    // Enable encryption
});

console.log(`Compressed ${result.originalSize} bytes to ${result.compressedSize} bytes`);
console.log(`Compression ratio: ${result.compressionRatio.toFixed(2)}x`);

// Decompress a file
const decompressed = await compressor.decompressFile('output.resc', 'restored.txt');
console.log(`Decompressed ${decompressed.data.length} bytes in ${decompressed.decodingTime}ms`);
console.log(`Checksum valid: ${decompressed.checksumValid}`);
```

## File Format

ResonaCompress files use the `.resc` extension and have the following binary format:

```
Header:
- Magic bytes (4 bytes): "RESC"
- Version (1 byte): 1
- Has secret flag (1 byte): 0 or 1
- Secret (32 bytes, if encrypted)

Prime Data:
- Prime count (2 bytes)
- Primes array (2 bytes each)

Metadata:
- Original size (4 bytes)
- Symbol count (4 bytes)
- SHA-256 checksum (32 bytes)

Phase Data:
- Phase count (4 bytes)
- Phases array (8 bytes each, double precision)
```

## Features

### ✅ Lossless Compression

Uses Chinese Remainder Theorem for mathematically guaranteed exact reconstruction.

### 🔒 Optional Encryption

Enable the `-s` flag to add HMAC-based cryptographic binding, making files unreadable without the secret key.

### 🎯 Deterministic

Same input file always produces the same compressed output (when not using encryption).

### 📊 Checksum Verification

SHA-256 checksums ensure data integrity during decompression.

### ⚡ Performance

- **Compression**: O(n × k) where n = file size, k = prime count
- **Decompression**: O(n × k²) due to CRT computation
- **Memory**: Minimal overhead, processes data in single pass

## Performance Characteristics

**Note**: ResonaCompress is a demonstration of applying graph database concepts to file compression. It is **not optimized for production use** and will produce larger files than traditional compression algorithms.

### Expected Behavior

- **File size**: Compressed files will be **larger** than originals due to phase storage overhead
- **Use case**: Educational demonstration of phase-encoding principles
- **Comparison**: Traditional algorithms (gzip, bzip2) will be faster and achieve better compression

### Why Larger Files?

Each byte is encoded as 48 phase angles (8 bytes each), resulting in:
- Original: 1 byte
- Compressed: 48 × 8 = 384 bytes
- **Overhead**: ~384x larger!

Plus metadata: primes, checksums, headers (~500-2000 bytes)

## Parameters

### Prime Count (`-p, --primes`)

- **Range**: 32-64
- **Default**: 48
- **Effect**: More primes = better security, larger files, slower processing
- **Recommendation**: Use 32 for speed, 64 for maximum security

### Taper Alpha (`-a, --alpha`)

- **Range**: 0.05-0.15
- **Default**: 0.1
- **Effect**: Affects phase distribution uniformity
- **Recommendation**: Use default 0.1 for balanced performance

### Encryption (`-s, --secret`)

- **Default**: Disabled
- **Effect**: Adds HMAC-based cryptographic binding
- **Note**: Secret is stored in file (for demo purposes)
- **Production**: Would require separate key management

## Examples

### Example 1: Basic Text File

```bash
# Create a sample text file
echo "Hello, ResonaCompress!" > hello.txt

# Compress it
resonacompress compress hello.txt

# View information
resonacompress info hello.txt.resc

# Decompress it
resonacompress decompress hello.txt.resc hello-restored.txt

# Verify
diff hello.txt hello-restored.txt
```

### Example 2: With Encryption

```bash
# Compress with encryption
resonacompress compress secret.txt -s

# Decompress (secret is embedded in file for demo)
resonacompress decompress secret.txt.resc
```

### Example 3: Custom Parameters

```bash
# Maximum security (slower, larger file)
resonacompress compress important.txt -p 64 -a 0.15 -s

# Fast compression (less secure, still large)
resonacompress compress quick.txt -p 32 -a 0.05
```

## Technical Details

### Phase Encoding Mathematics

The encoding formula is derived from ResonaGraph's phase-modulated superposition principle:

```
θ_p = 2π(m_j mod p + α/φ + HMAC(p||j, K))
```

This creates a unique phase angle for each byte-prime pair, distributing data across the prime space.

### Chinese Remainder Theorem

Given residues r₁, r₂, ..., rₖ and coprime moduli p₁, p₂, ..., pₖ, there exists a unique solution x (mod ∏pᵢ) such that:

```
x ≡ r₁ (mod p₁)
x ≡ r₂ (mod p₂)
...
x ≡ rₖ (mod pₖ)
```

This guarantees exact reconstruction of the original byte values.

### Prime Selection

Primes are selected using Sieve of Eratosthenes up to 10,000, then deterministically chosen based on SHA-256 hash of the file content.

## Comparison with Traditional Compression

| Feature | ResonaCompress | gzip | bzip2 |
|---------|---------------|------|-------|
| Algorithm | Phase encoding + CRT | LZ77 + Huffman | Burrows-Wheeler |
| Compression Ratio | ~0.003x (larger!) | 2-10x | 3-15x |
| Speed | Slow | Fast | Medium |
| Use Case | Educational | General | Archives |
| Encryption | Built-in | External | External |
| Mathematical | Yes | No | Partial |

## Limitations

1. **File Size**: Produces much larger files than traditional compression
2. **Performance**: Slower than optimized compression algorithms
3. **Use Case**: Educational demonstration, not production-ready
4. **CRT Complexity**: O(k²) reconstruction cost per byte

## Future Enhancements

Potential optimizations for production use:

- [ ] Sparse phase representation (only store non-zero phases)
- [ ] Adaptive prime selection based on data patterns
- [ ] Streaming compression for large files
- [ ] GPU acceleration for parallel CRT computation
- [ ] Hybrid approach: combine with LZ77 preprocessing
- [ ] External key management for encryption
- [ ] Compression quality modes (lossy variants)

## Development

### Build

```bash
npm run build
```

### Test

```bash
npm test
```

### Example Scripts

Run the example compression demo:

```bash
node dist/cli.js compress examples/sample.txt
node dist/cli.js info examples/sample.txt.resc
node dist/cli.js decompress examples/sample.txt.resc examples/restored.txt
```

## Connection to ResonaGraph

ResonaCompress demonstrates how ResonaGraph's core principles can be applied beyond distributed databases:

| ResonaGraph Concept | ResonaCompress Application |
|---------------------|----------------------------|
| Graph vertices | File bytes |
| Prime-indexed Hilbert space | Prime-indexed phase space |
| Resonance beacons | Compressed file format |
| Gossip protocol | (N/A - single file) |
| Phase-key cryptography | Optional file encryption |
| Resonance locking | CRT reconstruction |
| REC conflict resolution | (N/A - single file) |

## License

MIT License - see [LICENSE](../LICENSE) file for details.

## Acknowledgments

Based on the ResonaGraph Prime-Resonant Graph Database formalism by Sebastian Schepis (2025).

## Support

- **Issues**: [GitHub Issues](https://github.com/sschepis/resonagraph/issues)
- **Documentation**: See main [ResonaGraph README](../README.md)

---

Built with ❤️ as a demonstration of phase-encoding principles
