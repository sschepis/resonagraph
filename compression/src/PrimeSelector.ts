/**
 * Prime selector for ResonaCompress
 * 
 * Uses deterministic prime selection based on file hash to ensure
 * the same file always gets the same primes for compression/decompression
 */

import * as crypto from 'crypto';

export class PrimeSelector {
  private primeCache: number[] = [];
  private readonly maxPrime = 10000; // Sufficient for file compression

  constructor() {
    this.generatePrimes();
  }

  /**
   * Generate primes using Sieve of Eratosthenes
   */
  private generatePrimes(): void {
    const isPrime = new Array(this.maxPrime + 1).fill(true);
    isPrime[0] = isPrime[1] = false;

    for (let i = 2; i * i <= this.maxPrime; i++) {
      if (isPrime[i]) {
        for (let j = i * i; j <= this.maxPrime; j += i) {
          isPrime[j] = false;
        }
      }
    }

    for (let i = 2; i <= this.maxPrime; i++) {
      if (isPrime[i]) {
        this.primeCache.push(i);
      }
    }
  }

  /**
   * Select primes deterministically based on seed
   * 
   * @param seed - Seed for prime selection (e.g., file hash)
   * @param count - Number of primes to select (default: 48)
   * @returns Array of selected primes
   */
  selectPrimes(seed: Buffer, count: number = 48): number[] {
    if (count > this.primeCache.length) {
      throw new Error(`Cannot select ${count} primes, only ${this.primeCache.length} available`);
    }

    // Use seed to create deterministic selection
    const selected: number[] = [];
    const hash = crypto.createHash('sha256').update(seed).digest();

    // Use hash bytes to select primes
    let offset = 0;
    for (let i = 0; i < count; i++) {
      // Get 4 bytes from hash (cycling if needed)
      const index = hash.readUInt32BE(offset % (hash.length - 3));
      const primeIndex = index % this.primeCache.length;
      
      // Avoid duplicates
      let prime = this.primeCache[primeIndex];
      let attempts = 0;
      while (selected.includes(prime) && attempts < 100) {
        const newIndex = (primeIndex + attempts + 1) % this.primeCache.length;
        prime = this.primeCache[newIndex];
        attempts++;
      }
      
      selected.push(prime);
      offset += 4;
    }

    return selected.sort((a, b) => a - b);
  }

  /**
   * Get total number of available primes
   */
  getPrimeCount(): number {
    return this.primeCache.length;
  }
}
