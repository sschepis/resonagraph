/**
 * Phase encoder for ResonaCompress
 * 
 * Encodes file data as phase angles in prime-indexed space
 * Based on ResonaGraph encoding: θ_p = 2π(m_j mod p + α/φ + HMAC(p||j))
 */

import * as crypto from 'crypto';

const PHI = (1 + Math.sqrt(5)) / 2; // Golden ratio
const TWO_PI = 2 * Math.PI;
const DEFAULT_TAPER_ALPHA = 0.1;

export interface EncodedData {
  phases: number[];
  primes: number[];
  metadata: {
    originalSize: number;
    symbolCount: number;
    checksum: string;
  };
}

export class PhaseEncoder {
  private taperAlpha: number;

  constructor(taperAlpha: number = DEFAULT_TAPER_ALPHA) {
    this.taperAlpha = taperAlpha;
  }

  /**
   * Encode file data into phase angles
   * 
   * @param data - File data buffer
   * @param primes - Selected primes
   * @param secret - Optional secret for HMAC
   * @returns Encoded phase data
   */
  encode(data: Buffer, primes: number[], secret?: Buffer): EncodedData {
    // Compute checksum for integrity
    const checksum = crypto.createHash('sha256').update(data).digest('hex');

    // Encode each byte as a symbol
    const phases: number[] = [];
    
    for (let j = 0; j < data.length; j++) {
      const symbol = data[j]; // Each byte is a symbol
      
      for (let i = 0; i < primes.length; i++) {
        const prime = primes[i];
        const phase = this.computePhase(symbol, prime, j, secret);
        phases.push(phase);
      }
    }

    return {
      phases,
      primes,
      metadata: {
        originalSize: data.length,
        symbolCount: data.length,
        checksum,
      },
    };
  }

  /**
   * Compute phase angle for symbol-prime pair
   * 
   * θ_p = 2π((m_j mod p)/p + α/φ + HMAC(p||j))
   * 
   * We normalize the residue by dividing by prime to get a value in [0,1)
   * 
   * @param symbol - Byte value (0-255)
   * @param prime - Prime number
   * @param index - Symbol index
   * @param secret - Optional secret for HMAC
   * @returns Phase angle in radians
   */
  private computePhase(
    symbol: number,
    prime: number,
    index: number,
    secret?: Buffer
  ): number {
    // m_j mod p (this is the residue we want to encode)
    const residue = symbol % prime;

    // Normalize residue to [0, 1) by dividing by prime
    const normalizedResidue = residue / prime;

    // α/φ (taper contribution)
    const taperTerm = this.taperAlpha / PHI;

    // HMAC contribution (if secret provided)
    let hmacValue = 0;
    if (secret) {
      const data = Buffer.alloc(8);
      data.writeUInt32BE(prime, 0);
      data.writeUInt32BE(index, 4);
      const hmac = crypto.createHmac('sha256', secret).update(data).digest();
      hmacValue = hmac.readUInt32BE(0) / 0x100000000;
    }

    // Combine terms: (residue/p) + α/φ + HMAC
    const combinedValue = normalizedResidue + taperTerm + hmacValue;

    // Apply 2π modulation and ensure in [0, 2π)
    const phase = TWO_PI * (combinedValue % 1.0);

    return phase;
  }

  /**
   * Reconstruct data from phases using Chinese Remainder Theorem
   * 
   * @param encoded - Encoded data
   * @param secret - Optional secret for verification
   * @returns Reconstructed buffer
   */
  decode(encoded: EncodedData, secret?: Buffer): Buffer {
    const { phases, primes, metadata } = encoded;
    const symbolCount = metadata.symbolCount;
    const result = Buffer.alloc(symbolCount);

    // Reconstruct each symbol
    for (let j = 0; j < symbolCount; j++) {
      // Extract phases for this symbol
      const symbolPhases: number[] = [];
      for (let i = 0; i < primes.length; i++) {
        const phaseIndex = j * primes.length + i;
        symbolPhases.push(phases[phaseIndex]);
      }

      // Reconstruct symbol using CRT
      const symbol = this.reconstructSymbol(symbolPhases, primes, j, secret);
      result[j] = symbol;
    }

    return result;
  }

  /**
   * Reconstruct a single symbol from its phases using CRT
   * 
   * @param phases - Phase angles for this symbol
   * @param primes - Prime numbers used
   * @param index - Symbol index
   * @param secret - Optional secret
   * @returns Reconstructed byte value
   */
  private reconstructSymbol(
    phases: number[],
    primes: number[],
    index: number,
    secret?: Buffer
  ): number {
    // Extract residues from phases
    const residues: number[] = [];
    
    for (let i = 0; i < primes.length; i++) {
      const prime = primes[i];
      const phase = phases[i];
      
      // Reverse the phase computation
      // θ_p = 2π(residue/prime + α/φ + HMAC(p||j))
      // So: residue/prime = (θ_p / 2π) - α/φ - HMAC(p||j)
      let normalizedPhase = phase / TWO_PI;
      
      // Subtract taper term
      const taperTerm = this.taperAlpha / PHI;
      normalizedPhase -= taperTerm;
      
      // Subtract HMAC if present
      if (secret) {
        const data = Buffer.alloc(8);
        data.writeUInt32BE(prime, 0);
        data.writeUInt32BE(index, 4);
        const hmac = crypto.createHmac('sha256', secret).update(data).digest();
        const hmacValue = hmac.readUInt32BE(0) / 0x100000000;
        normalizedPhase -= hmacValue;
      }
      
      // Normalize to [0, 1)
      while (normalizedPhase < 0) normalizedPhase += 1;
      while (normalizedPhase >= 1) normalizedPhase -= 1;
      
      // Extract residue: residue = round(normalizedPhase * prime) mod prime
      // But we stored residue/prime, so multiply back
      let residue = Math.round(normalizedPhase * prime);
      residue = ((residue % prime) + prime) % prime; // Ensure positive
      
      residues.push(residue);
    }

    // Apply Chinese Remainder Theorem
    return this.applyCRT(residues, primes);
  }

  /**
   * Apply Chinese Remainder Theorem to reconstruct value
   * 
   * Find x such that:
   *   x ≡ r_i (mod p_i) for all i
   * 
   * Solution: x = sum(r_i * (P/p_i) * inv(P/p_i, p_i)) mod P
   * where P = product of all primes
   * 
   * @param residues - Residues r_i where x ≡ r_i (mod p_i)
   * @param primes - Prime moduli p_i
   * @returns Reconstructed value x (constrained to byte range)
   */
  private applyCRT(residues: number[], primes: number[]): number {
    // Use BigInt for accurate calculations
    const primeBigInts = primes.map(p => BigInt(p));
    const residueBigInts = residues.map(r => BigInt(r));
    
    // Calculate product of all primes
    const product = primeBigInts.reduce((acc, p) => acc * p, 1n);
    
    let result = 0n;

    for (let i = 0; i < primes.length; i++) {
      const p_i = primeBigInts[i];
      const r_i = residueBigInts[i];
      
      // P / p_i
      const pp = product / p_i;
      
      // Find modular inverse of pp mod p_i
      const inv = this.modInverseBigInt(pp, p_i);
      
      // Add contribution: r_i * pp * inv
      result += r_i * pp * inv;
    }

    // Result mod product
    result = ((result % product) + product) % product;
    
    // Since we're reconstructing bytes (0-255), take mod 256
    return Number(result % 256n);
  }

  /**
   * Compute modular multiplicative inverse using Extended Euclidean Algorithm (BigInt version)
   * 
   * Find x such that (a * x) ≡ 1 (mod m)
   * 
   * @param a - Number to invert
   * @param m - Modulus
   * @returns Modular inverse of a mod m
   */
  private modInverseBigInt(a: bigint, m: bigint): bigint {
    // Ensure a is in range [0, m)
    a = ((a % m) + m) % m;
    
    // Extended Euclidean Algorithm
    let [oldR, r] = [a, m];
    let [oldS, s] = [1n, 0n];
    
    while (r !== 0n) {
      const quotient = oldR / r;
      [oldR, r] = [r, oldR - quotient * r];
      [oldS, s] = [s, oldS - quotient * s];
    }
    
    // oldR is gcd(a, m), should be 1 for inverse to exist
    if (oldR !== 1n) {
      throw new Error(`No modular inverse: gcd(${a}, ${m}) = ${oldR}`);
    }
    
    // Ensure result is positive
    return ((oldS % m) + m) % m;
  }
}
