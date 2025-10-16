/**
 * ResonaGraph - Prime-Resonant Graph Database
 * JavaScript/TypeScript Implementation
 * 
 * A next-generation distributed graph database implementing phase-modulated
 * superpositions over prime-based Hilbert spaces for non-local data reconstruction.
 */

export { PhaseKey } from './core/PhaseKey';
export { PrimeSelector } from './core/PrimeSelector';
export { PhaseEncoder, EncodedPhases, EncodingOptions } from './core/PhaseEncoder';
export { ProbeSynthesizer, ProbeState } from './resonance/ProbeSynthesizer';
export { ResonanceLock, LockResult } from './resonance/ResonanceLock';
export { ResidueExtractor } from './resonance/ResidueExtractor';
export { Client, PutOptions, GetOptions, BeaconMetadata } from './api/Client';

// Version
export const VERSION = '0.1.0';
