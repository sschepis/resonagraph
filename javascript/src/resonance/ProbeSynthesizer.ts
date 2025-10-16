/**
 * Probe synthesis module for generating probe states.
 * 
 * According to design.md Section 2.3:
 * - Generate probe states |Q⟩ = ∑ w_p e^{iφ_p} |p⟩
 * - Use tapered weights for faster convergence
 */

export interface ProbeState {
  weights: number[]; // w_p for each prime
  phases: number[]; // φ_p for each prime
  primes: number[]; // Prime indices
}

export class ProbeSynthesizer {
  /**
   * Synthesize a probe state for data retrieval.
   * 
   * According to design.md Section 2.3:
   * |Q⟩ = ∑ w_p e^{iφ_p} |p⟩
   * 
   * @param primes - Prime indices
   * @param taperAlpha - Taper parameter for weighted probes
   * @returns Probe state
   */
  synthesize(primes: number[], taperAlpha: number = 0.1): ProbeState {
    const n = primes.length;
    const weights: number[] = [];
    const phases: number[] = [];

    // Generate tapered weights
    // Use exponential taper: w_i = exp(-α * i / n)
    for (let i = 0; i < n; i++) {
      const weight = Math.exp(-taperAlpha * i / n);
      weights.push(weight);
      
      // Initialize phases to zero (will be updated during locking)
      phases.push(0);
    }

    // Normalize weights
    const totalWeight = weights.reduce((sum, w) => sum + w, 0);
    const normalizedWeights = weights.map(w => w / totalWeight);

    return {
      weights: normalizedWeights,
      phases,
      primes,
    };
  }

  /**
   * Update probe phases during locking iteration.
   * 
   * @param probe - Current probe state
   * @param targetPhases - Target phase angles
   * @param learningRate - Learning rate for phase updates
   * @returns Updated probe state
   */
  updateProbe(probe: ProbeState, targetPhases: number[], learningRate: number = 0.1): ProbeState {
    const updatedPhases = probe.phases.map((phase, i) => {
      const target = targetPhases[i];
      // Gradient descent step
      return phase + learningRate * (target - phase);
    });

    return {
      ...probe,
      phases: updatedPhases,
    };
  }

  /**
   * Compute overlap between probe and address state.
   * 
   * R = |⟨Q|A⟩| - overlap magnitude
   * 
   * @param probe - Probe state
   * @param addressPhases - Address state phases
   * @returns Overlap magnitude R
   */
  computeOverlap(probe: ProbeState, addressPhases: number[]): number {
    let realPart = 0;
    let imagPart = 0;

    for (let i = 0; i < probe.primes.length; i++) {
      const weight = probe.weights[i];
      const probePhase = probe.phases[i];
      const addressPhase = addressPhases[i];

      // ⟨Q|A⟩ = ∑ w_p e^{i(φ_p^Q - φ_p^A)}
      const phaseDiff = probePhase - addressPhase;
      realPart += weight * Math.cos(phaseDiff);
      imagPart += weight * Math.sin(phaseDiff);
    }

    // |⟨Q|A⟩|
    return Math.sqrt(realPart * realPart + imagPart * imagPart);
  }
}
