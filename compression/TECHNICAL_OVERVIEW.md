# ResonaCompress - Technical Overview

## Introduction

ResonaCompress is a file compression tool that demonstrates how the phase-encoding principles from ResonaGraph (a distributed graph database) can be applied to file compression. This document provides a technical overview of how the algorithm works.

## Core Principle

Instead of using traditional compression techniques like Huffman coding or LZ77, ResonaCompress encodes each byte as a set of **phase angles** in a prime-indexed mathematical space, then reconstructs them using the **Chinese Remainder Theorem (CRT)**.

## Algorithm Steps

### 1. Prime Selection (PrimeSelector)

For each file, we:
1. Compute SHA-256 hash of the file content
2. Use this hash as a seed for deterministic prime selection
3. Select 32-64 primes from our cache (generated via Sieve of Eratosthenes up to 10,000)
4. This ensures the same file always gets the same primes

**Why deterministic?** So decompression knows which primes to use without storing them redundantly.

### 2. Phase Encoding (PhaseEncoder)

For each byte `b` in the file:
1. For each prime `p` in our selected set:
   - Compute residue: `r = b mod p`
   - Encode as phase angle: `θ_p = 2π((r/p) + α/φ + HMAC(p,i))`
     - `α/φ`: Golden ratio distribution term (α=0.1, φ=(1+√5)/2)
     - `HMAC(p,i)`: Optional cryptographic term for encryption
2. Store all phase angles

**Example**: For byte value 65 ('A') with primes [2,3,5,7,11]:
- Residues: [1, 2, 0, 2, 10]
- Phase angles: [3.141..., 4.712..., 0.785..., 2.513..., 5.890...]

### 3. Serialization

The encoded data is serialized to a binary format:

```
[Header: Magic bytes, version, encryption flag]
[Prime data: count + array of primes]
[Metadata: original size, checksum]
[Phase data: count + array of phase angles (float64)]
```

### 4. Reconstruction (Decoding)

During decompression:

1. Read header and metadata
2. For each byte position:
   - Extract the k phase angles (one per prime)
   - Reverse the encoding: `(θ_p / 2π) - α/φ - HMAC(p,i)` → `r/p`
   - Multiply by prime: `r/p × p` → `r`
   - Now we have k residues

3. Apply Chinese Remainder Theorem:
   - Find unique value `x` such that:
     - `x ≡ r₁ (mod p₁)`
     - `x ≡ r₂ (mod p₂)`
     - ...
     - `x ≡ rₖ (mod pₖ)`
   - Result: original byte value

### 5. CRT Implementation

The Chinese Remainder Theorem reconstruction uses:

```
x = Σ(rᵢ × (P/pᵢ) × inv(P/pᵢ, pᵢ)) mod P
```

Where:
- `P = ∏pᵢ` (product of all primes)
- `inv(a, m)` is modular multiplicative inverse of `a mod m`
- Computed using Extended Euclidean Algorithm
- Uses BigInt for accuracy with large prime products

## Why Does This Work?

The Chinese Remainder Theorem states that if we have coprime moduli (our primes), then the system of congruences has a unique solution modulo their product. Since our smallest prime is 2 and we use 48 primes, the product is much larger than 256 (the byte range), guaranteeing unique reconstruction.

## Performance Analysis

### Time Complexity

- **Encoding**: O(n × k) where n = file size, k = prime count
  - For each of n bytes, compute k phase angles
  
- **Decoding**: O(n × k²) 
  - For each of n bytes: extract k residues (O(k)) + CRT reconstruction (O(k²))

### Space Complexity

- **Original**: n bytes
- **Compressed**: ~(n × k × 8) + overhead
  - Each byte becomes k float64 values (8 bytes each)
  - Overhead: ~500-2000 bytes for headers, primes, metadata

### Compression Ratio

For default parameters (k=48):
- **Expansion factor**: ~384x (each byte → 48 × 8 bytes)
- This is why it's called "educational" - not practical for real compression!

## Connection to ResonaGraph

| ResonaGraph Concept | ResonaCompress Application |
|---------------------|----------------------------|
| Graph vertex encoding | Byte encoding |
| Prime-indexed Hilbert space | Prime-indexed phase space |
| Resonance beacons | Compressed file format |
| Phase-key cryptography | Optional HMAC encryption |
| CRT reconstruction | Byte recovery |
| Resonance locking | (Not used in compression) |

## Advantages

1. **Mathematically guaranteed** lossless reconstruction
2. **Built-in encryption** via HMAC in phase calculation
3. **Deterministic** - same input always produces same output
4. **Demonstrates versatility** of ResonaGraph's mathematical foundations

## Limitations

1. **File size expansion** rather than compression
2. **Slower** than traditional algorithms
3. **High memory usage** for large files
4. **Not suitable** for production use

## Potential Optimizations

If this were to be made practical:

1. **Sparse representation**: Only store non-zero phase components
2. **Quantization**: Use lower precision for phase angles
3. **Hybrid approach**: Combine with LZ77 preprocessing
4. **Streaming**: Process file in chunks instead of all at once
5. **Adaptive primes**: Select fewer primes for low-entropy data
6. **GPU acceleration**: Parallelize phase computation and CRT

## Educational Value

ResonaCompress demonstrates:
- **Number theory** (prime numbers, modular arithmetic, CRT)
- **Cryptography** (HMAC, deterministic key derivation)
- **Phase mathematics** (trigonometric encoding)
- **Systems programming** (binary formats, CLI tools)
- **Algorithm design** (encoding/decoding symmetry)

## Conclusion

While ResonaCompress is not practical for actual file compression, it serves as an excellent demonstration of how mathematical concepts from distributed systems can be creatively applied to different problem domains. It shows that the phase-encoding principles of ResonaGraph are versatile and can be adapted beyond their original use case.

The tool provides a hands-on way to understand:
- How phase encoding works
- How CRT enables exact reconstruction
- The trade-offs between mathematical elegance and practical efficiency

For real compression needs, use gzip, bzip2, or other established algorithms. Use ResonaCompress to learn and experiment with phase-encoding concepts!
