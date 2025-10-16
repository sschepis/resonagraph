/**
 * Resonance locking module for data reconstruction.
 * 
 * According to design.md Section 2.3:
 * - Iterative convergence: R > R_min AND S < S_min
 * - Track entropy decay S(t) = S_0 e^{-λt}
 * - Track resonance score RS(t) = RS_★(1 - e^{-γt})
 */

import { ProbeState, ProbeSynthesizer } from './ProbeSynthesizer';

// Constants from copilot-instructions.md
const R_MIN = 0.95; // Minimum overlap threshold
const S_MIN = 0.01; // Minimum entropy threshold
const MAX_ITERATIONS = 100; // Prevent infinite loops
const LEARNING_RATE = 0.1;

export interface LockResult {
  converged: boolean;
  iterations: number;
  finalOverlap: number;
  finalEntropy: number;
  phases: number[];
  metrics: {
    lockTime: number; // milliseconds
    entropyFinal: number;
  };
}

export class ResonanceLock {
  private synthesizer: ProbeSynthesizer;
  private rMin: number;
  private sMin: number;
  private maxIterations: number;

  constructor(options: {
    rMin?: number;
    sMin?: number;
    maxIterations?: number;
  } = {}) {
    this.synthesizer = new ProbeSynthesizer();
    this.rMin = options.rMin ?? R_MIN;
    this.sMin = options.sMin ?? S_MIN;
    this.maxIterations = options.maxIterations ?? MAX_ITERATIONS;
  }

  /**
   * Perform resonance locking to recover data.
   * 
   * According to design.md Section 2.3:
   * - Initialize probe state
   * - Iterate: compute overlap, update phases
   * - Check convergence: R > R_min AND S < S_min
   * 
   * @param addressPhases - Target address phases
   * @param primes - Prime indices
   * @param taperAlpha - Taper parameter
   * @returns Lock result with convergence status
   */
  lock(addressPhases: number[], primes: number[], taperAlpha: number = 0.1): LockResult {
    const startTime = Date.now();

    // Initialize probe state
    let probe = this.synthesizer.synthesize(primes, taperAlpha);

    let iteration = 0;
    let overlap = 0;
    let entropy = 1.0; // Initial high entropy

    // Thermodynamic parameters
    const lambda = 0.1; // Entropy decay rate
    const gamma = 0.2; // Resonance growth rate
    const initialEntropy = 1.0;

    while (iteration < this.maxIterations) {
      // Compute overlap R = |⟨Q|A⟩|
      overlap = this.synthesizer.computeOverlap(probe, addressPhases);

      // Update entropy: S(t) = S_0 e^{-λt}
      entropy = initialEntropy * Math.exp(-lambda * iteration);

      // Check convergence
      if (overlap >= this.rMin && entropy <= this.sMin) {
        const lockTime = Date.now() - startTime;
        return {
          converged: true,
          iterations: iteration + 1,
          finalOverlap: overlap,
          finalEntropy: entropy,
          phases: probe.phases,
          metrics: {
            lockTime,
            entropyFinal: entropy,
          },
        };
      }

      // Update probe phases
      probe = this.synthesizer.updateProbe(probe, addressPhases, LEARNING_RATE);

      iteration++;
    }

    // Failed to converge
    const lockTime = Date.now() - startTime;
    return {
      converged: false,
      iterations: iteration,
      finalOverlap: overlap,
      finalEntropy: entropy,
      phases: probe.phases,
      metrics: {
        lockTime,
        entropyFinal: entropy,
      },
    };
  }

  /**
   * Compute phase differences for residue extraction.
   * 
   * Δθ_p = θ_p^probe - θ_p^address
   * 
   * @param probePhases - Locked probe phases
   * @param addressPhases - Address phases
   * @returns Phase differences
   */
  getPhaseDifferences(probePhases: number[], addressPhases: number[]): number[] {
    return probePhases.map((phase, i) => phase - addressPhases[i]);
  }
}
