/**
 * Residue extraction and CRT reconstruction module.
 * 
 * According to design.md Section 2.3:
 * - Extract residues from phase differences
 * - Apply Chinese Remainder Theorem for payload reconstruction
 * - Ensure product ∏ p_i ≥ 2^{8b} for b-byte symbols
 */

const TWO_PI = 2 * Math.PI;

export class ResidueExtractor {
  /**
   * Extract residues from phase differences.
   * 
   * Convert phase differences Δθ_p to residues r_j ≡ m_j mod p_i
   * 
   * @param phaseDifferences - Phase differences Δθ_p
   * @param primes - Prime moduli
   * @returns Residue values
   */
  extractResidues(phaseDifferences: number[], primes: number[]): number[] {
    const residues: number[] = [];

    for (let i = 0; i < primes.length; i++) {
      const phaseDiff = phaseDifferences[i];
      const prime = primes[i];

      // Convert phase to residue
      // θ = 2π * (residue / prime) (simplified)
      const normalizedPhase = (phaseDiff % TWO_PI) / TWO_PI;
      const residue = Math.round(normalizedPhase * prime) % prime;

      residues.push(residue >= 0 ? residue : residue + prime);
    }

    return residues;
  }

  /**
   * Reconstruct payload using Chinese Remainder Theorem.
   * 
   * Given: r_j ≡ m_j mod p_i for all i
   * Find: m_j such that m_j ≡ r_j mod p_i
   * 
   * @param residues - Residue values for each prime
   * @param primes - Prime moduli
   * @returns Reconstructed symbol value
   */
  crtReconstruct(residues: number[], primes: number[]): bigint {
    if (residues.length !== primes.length) {
      throw new Error('Residues and primes arrays must have same length');
    }

    // Compute product of all primes
    const N = primes.reduce((prod, p) => prod * BigInt(p), BigInt(1));

    let result = BigInt(0);

    for (let i = 0; i < primes.length; i++) {
      const prime = BigInt(primes[i]);
      const residue = BigInt(residues[i]);
      
      // N_i = N / p_i
      const Ni = N / prime;
      
      // Find modular inverse: M_i = N_i^{-1} mod p_i
      const Mi = this.modInverse(Ni, prime);
      
      // Add contribution: r_i * N_i * M_i
      result = (result + residue * Ni * Mi) % N;
    }

    return result >= BigInt(0) ? result : result + N;
  }

  /**
   * Compute modular inverse using Extended Euclidean Algorithm.
   * 
   * Find x such that a * x ≡ 1 mod m
   * 
   * @param a - Value to invert
   * @param m - Modulus
   * @returns Modular inverse
   */
  private modInverse(a: bigint, m: bigint): bigint {
    const originalM = m;
    let x0 = BigInt(0);
    let x1 = BigInt(1);

    if (m === BigInt(1)) return BigInt(0);

    let tempA = a % m;
    
    while (tempA > BigInt(1)) {
      // q is quotient
      const q = tempA / m;

      // m is remainder now, process same as Euclid's algorithm
      let t = m;
      m = tempA % m;
      tempA = t;

      // Update x0 and x1
      t = x0;
      x0 = x1 - q * x0;
      x1 = t;
    }

    // Make x1 positive
    if (x1 < BigInt(0)) {
      x1 += originalM;
    }

    return x1;
  }

  /**
   * Reconstruct full payload from multiple symbols.
   * 
   * @param residueSets - Array of residue sets (one per symbol)
   * @param primes - Prime moduli
   * @param symbolSize - Size of each symbol in bytes
   * @returns Reconstructed payload buffer
   */
  reconstructPayload(
    residueSets: number[][],
    primes: number[],
    symbolSize: number = 2
  ): Buffer {
    const symbols: bigint[] = [];

    // Reconstruct each symbol using CRT
    for (const residues of residueSets) {
      const symbol = this.crtReconstruct(residues, primes);
      symbols.push(symbol);
    }

    // Convert symbols back to bytes
    const bytes: number[] = [];
    for (const symbol of symbols) {
      const symbolNum = Number(symbol);
      
      // Extract bytes from symbol (big-endian)
      for (let i = symbolSize - 1; i >= 0; i--) {
        const byte = (symbolNum >> (i * 8)) & 0xff;
        if (byte !== 0 || bytes.length > 0) { // Skip leading zeros
          bytes.push(byte);
        }
      }
    }

    return Buffer.from(bytes);
  }

  /**
   * Parse reconstructed bytes back to JSON payload.
   * 
   * @param bytes - Reconstructed bytes
   * @returns Parsed JSON object
   */
  parsePayload(bytes: Buffer): any {
    const payloadStr = bytes.toString('utf-8');
    return JSON.parse(payloadStr);
  }
}
