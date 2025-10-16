/**
 * Phase encoding module implementing the phase coding formalism.
 * 
 * According to design.md Section 3.2 and copilot-instructions.md:
 * - Phase Coding: θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
 * - Golden ratio φ = (1+√5)/2
 * - Taper alpha for weighted probes (default α=0.1)
 */

import { PhaseKey } from './PhaseKey';

// Mathematical constants
const PHI = (1 + Math.sqrt(5)) / 2; // Golden ratio
const TWO_PI = 2 * Math.PI;

// Default parameters from copilot-instructions.md
const DEFAULT_TAPER_ALPHA = 0.1;
const MIN_TAPER_ALPHA = 0.05;
const MAX_TAPER_ALPHA = 0.15;

// Symbol chunking
const DEFAULT_SYMBOL_SIZE = 2; // 2 bytes per symbol (m_j ≤ 2^16)
const MAX_SYMBOL_VALUE = 65536; // 2^16

export interface EncodingOptions {
  taperAlpha?: number;
  symbolSize?: number;
}

export interface EncodedPhases {
  phases: number[]; // θ_p for each prime
  primes: number[]; // Prime indices
  metadata: {
    symbolCount: number;
    taperAlpha: number;
  };
}

export class PhaseEncoder {
  private taperAlpha: number;
  private symbolSize: number;

  /**
   * Initialize the phase encoder.
   * 
   * @param options - Encoding options
   */
  constructor(options: EncodingOptions = {}) {
    this.taperAlpha = options.taperAlpha ?? DEFAULT_TAPER_ALPHA;
    this.symbolSize = options.symbolSize ?? DEFAULT_SYMBOL_SIZE;

    if (this.taperAlpha < MIN_TAPER_ALPHA || this.taperAlpha > MAX_TAPER_ALPHA) {
      throw new Error(
        `taperAlpha must be between ${MIN_TAPER_ALPHA} and ${MAX_TAPER_ALPHA}, got ${this.taperAlpha}`
      );
    }
  }

  /**
   * Encode payload into phase angles.
   * 
   * According to design.md Section 3.2:
   * θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
   * 
   * @param payload - Data to encode (JSON object)
   * @param primes - Selected prime indices
   * @param phaseKey - Cryptographic phase key
   * @returns Encoded phases and metadata
   */
  encode(payload: any, primes: number[], phaseKey: PhaseKey): EncodedPhases {
    // Serialize payload to bytes
    const payloadStr = JSON.stringify(payload);
    const payloadBytes = Buffer.from(payloadStr, 'utf-8');

    // Chunk into symbols
    const symbols = this.chunkIntoSymbols(payloadBytes);

    // Encode each symbol with each prime
    const phases: number[] = [];
    
    for (let j = 0; j < symbols.length; j++) {
      const symbol = symbols[j];
      
      for (let i = 0; i < primes.length; i++) {
        const prime = primes[i];
        const phase = this.computePhase(symbol, prime, j, phaseKey);
        phases.push(phase);
      }
    }

    return {
      phases,
      primes,
      metadata: {
        symbolCount: symbols.length,
        taperAlpha: this.taperAlpha,
      },
    };
  }

  /**
   * Compute phase angle for a symbol-prime pair.
   * 
   * θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
   * 
   * @param symbol - Symbol value m_j
   * @param prime - Prime p
   * @param symbolIndex - Symbol index j
   * @param phaseKey - Phase key K
   * @returns Phase angle θ_p in radians
   */
  private computePhase(
    symbol: number,
    prime: number,
    symbolIndex: number,
    phaseKey: PhaseKey
  ): number {
    // m_j mod p
    const residue = symbol % prime;

    // α/φ (taper contribution)
    const taperTerm = this.taperAlpha / PHI;

    // β/δ - additional distribution (simplified: using 0 for now)
    const distributionTerm = 0;

    // HMAC(p||j, K) - cryptographic binding
    const hmacData = Buffer.alloc(8);
    hmacData.writeUInt32BE(prime, 0);
    hmacData.writeUInt32BE(symbolIndex, 4);
    const hmac = phaseKey.computeHMAC(hmacData);
    
    // Normalize HMAC to [0, 1) range
    const hmacValue = hmac.readUInt32BE(0) / 0x100000000;

    // Combine all terms
    const combinedValue = residue + taperTerm + distributionTerm + hmacValue;

    // Apply 2π modulation
    const phase = TWO_PI * (combinedValue % 1.0);

    return phase;
  }

  /**
   * Chunk payload bytes into symbols.
   * 
   * @param bytes - Payload bytes
   * @returns Array of symbol values
   */
  private chunkIntoSymbols(bytes: Buffer): number[] {
    const symbols: number[] = [];
    
    for (let i = 0; i < bytes.length; i += this.symbolSize) {
      let symbol = 0;
      
      // Read up to symbolSize bytes
      for (let j = 0; j < this.symbolSize && i + j < bytes.length; j++) {
        symbol = (symbol << 8) | bytes[i + j];
      }
      
      // Ensure symbol fits in expected range
      if (symbol >= MAX_SYMBOL_VALUE) {
        symbol = symbol % MAX_SYMBOL_VALUE;
      }
      
      symbols.push(symbol);
    }
    
    return symbols;
  }

  /**
   * Decode phases back to payload.
   * 
   * Note: Full decoding requires resonance locking and CRT reconstruction.
   * This is a placeholder for the interface.
   * 
   * @param encoded - Encoded phases
   * @param phaseKey - Phase key for verification
   * @returns Decoded payload
   */
  decode(encoded: EncodedPhases, phaseKey: PhaseKey): any {
    // Decoding is handled by ResonanceLock and ResidueExtractor
    // This method is a placeholder for future implementation
    throw new Error('Decoding requires resonance locking - use Client.get() instead');
  }
}
