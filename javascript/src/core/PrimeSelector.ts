/**
 * Prime selection module for deterministic prime set generation.
 * 
 * According to design.md Section 3.1:
 * - Hash key, seed Eratosthenes sieve
 * - Select k=32-64 primes (range 2 to 10^12)
 * - Deterministic selection based on key hash
 */

import * as crypto from 'crypto';

// Constants from copilot-instructions.md
const DEFAULT_K_PRIMES = 48; // Balanced security/performance
const MIN_K_PRIMES = 32;
const MAX_K_PRIMES = 64;

// Prime range
const MIN_PRIME = 2;
const MAX_PRIME_FOR_SIEVE = 100000; // Practical limit for sieve

/**
 * Generate primes up to n using Sieve of Eratosthenes.
 */
function sieveOfEratosthenes(n: number): number[] {
  const isPrime = new Array(n + 1).fill(true);
  isPrime[0] = isPrime[1] = false;

  for (let i = 2; i * i <= n; i++) {
    if (isPrime[i]) {
      for (let j = i * i; j <= n; j += i) {
        isPrime[j] = false;
      }
    }
  }

  const primes: number[] = [];
  for (let i = 2; i <= n; i++) {
    if (isPrime[i]) {
      primes.push(i);
    }
  }
  return primes;
}

export class PrimeSelector {
  private primeCache: number[];

  constructor() {
    // Pre-generate prime cache
    this.primeCache = sieveOfEratosthenes(MAX_PRIME_FOR_SIEVE);
  }

  /**
   * Select k primes deterministically based on key.
   * 
   * According to design.md Section 3.1:
   * - Hash key to get seed
   * - Use seed to select primes from cached set
   * - Return k primes in sorted order
   * 
   * @param key - String key to hash
   * @param k - Number of primes to select (32-64)
   * @returns Array of k selected primes
   */
  selectPrimes(key: string, k: number = DEFAULT_K_PRIMES): number[] {
    if (k < MIN_K_PRIMES || k > MAX_K_PRIMES) {
      throw new Error(`k_primes must be between ${MIN_K_PRIMES} and ${MAX_K_PRIMES}, got ${k}`);
    }

    if (k > this.primeCache.length) {
      throw new Error(`Requested ${k} primes but only ${this.primeCache.length} available in cache`);
    }

    // Hash the key to get a seed
    const hash = crypto.createHash('sha256');
    hash.update(key);
    const hashBytes = hash.digest();

    // Use hash to seed selection
    const selected: number[] = [];
    const available = [...this.primeCache]; // Copy for modification
    
    let seedOffset = 0;
    for (let i = 0; i < k; i++) {
      // Use hash bytes to create pseudo-random index
      const indexSeed = hashBytes.readUInt32BE(seedOffset % (hashBytes.length - 4));
      const index = indexSeed % available.length;
      
      selected.push(available[index]);
      available.splice(index, 1); // Remove selected prime
      
      seedOffset += 4;
    }

    // Return sorted primes
    return selected.sort((a, b) => a - b);
  }

  /**
   * Get the total number of cached primes.
   * 
   * @returns Number of primes in cache
   */
  getCacheSize(): number {
    return this.primeCache.length;
  }

  /**
   * Get product of primes (for CRT modulus).
   * 
   * @param primes - Array of primes
   * @returns Product of all primes
   */
  static getProduct(primes: number[]): bigint {
    return primes.reduce((prod, p) => prod * BigInt(p), BigInt(1));
  }

  /**
   * Check if product is sufficient for given byte size.
   * According to design.md: Product ∏ p_i ≥ 2^{8b} for b-byte symbols
   * 
   * @param primes - Array of primes
   * @param byteSize - Expected byte size
   * @returns true if product is sufficient
   */
  static checkProductSufficiency(primes: number[], byteSize: number): boolean {
    const product = PrimeSelector.getProduct(primes);
    const required = BigInt(2) ** BigInt(8 * byteSize);
    return product >= required;
  }
}
