"""
Probe synthesis module for ResonaGraph.

Implements probe state generation from design.md Section 2.2.2:
- Probe Formation: |Q⟩ = ∑ w_p e^{iφ_p} |p⟩
- Weighted probes with taper_alpha
- Uniform or tapered weight distribution

According to copilot-instructions.md:
- Generate probe states for data retrieval
- Support weighted probes with taper_alpha (default 0.1)
"""

import numpy as np
from typing import List, Dict, Any, Optional
import math


class ProbeState:
    """
    Represents a probe state |Q⟩ in the prime-based Hilbert space.
    
    According to design.md Section 2.2.2:
    |Q⟩ = ∑ w_p e^{iφ_p} |p⟩
    
    Where:
    - w_p: Weight for prime p (uniform or tapered)
    - φ_p: Phase angle for prime p
    - |p⟩: Basis state for prime p
    """
    
    def __init__(
        self,
        primes: List[int],
        phase_angles: List[float],
        weights: Optional[List[float]] = None
    ):
        """
        Initialize a probe state.
        
        Args:
            primes: List of prime numbers
            phase_angles: Phase angles φ_p for each prime
            weights: Optional weights w_p for each prime (uniform if None)
        """
        if len(primes) != len(phase_angles):
            raise ValueError("primes and phase_angles must have same length")
        
        if weights is not None and len(weights) != len(primes):
            raise ValueError("weights must have same length as primes")
        
        self.primes = primes
        self.phase_angles = phase_angles
        self.weights = weights if weights is not None else [1.0] * len(primes)
        
        # Normalize weights
        total_weight = sum(self.weights)
        if total_weight > 0:
            self.weights = [w / total_weight for w in self.weights]
    
    def compute_amplitude(self, prime_idx: int) -> complex:
        """
        Compute the complex amplitude for a given prime index.
        
        Returns: w_p * e^{iφ_p}
        """
        weight = self.weights[prime_idx]
        phase = self.phase_angles[prime_idx]
        return weight * np.exp(1j * phase)
    
    def __repr__(self) -> str:
        return f"ProbeState(primes={len(self.primes)}, weighted={self.weights[0] != 1.0})"


class ProbeSynthesizer:
    """
    Synthesizes probe states for resonance locking.
    
    According to design.md Section 2.2.2 and copilot-instructions.md:
    - Generate probe states |Q⟩ = ∑ w_p e^{iφ_p} |p⟩
    - Support uniform or tapered weights (α parameter)
    """
    
    # Default parameters from copilot-instructions.md
    DEFAULT_TAPER_ALPHA = 0.1
    MIN_TAPER_ALPHA = 0.05
    MAX_TAPER_ALPHA = 0.15
    
    def __init__(self, taper_alpha: float = DEFAULT_TAPER_ALPHA):
        """
        Initialize probe synthesizer.
        
        Args:
            taper_alpha: Taper parameter for weighted probes (0.05-0.15)
        """
        if not (self.MIN_TAPER_ALPHA <= taper_alpha <= self.MAX_TAPER_ALPHA):
            raise ValueError(
                f"taper_alpha must be between {self.MIN_TAPER_ALPHA} "
                f"and {self.MAX_TAPER_ALPHA}"
            )
        self.taper_alpha = taper_alpha
    
    def synthesize_probe(
        self,
        primes: List[int],
        phase_angles: List[float],
        use_tapered: bool = True
    ) -> ProbeState:
        """
        Synthesize a probe state for the given primes and phase angles.
        
        Args:
            primes: List of prime numbers
            phase_angles: Phase angles φ_p for each prime
            use_tapered: If True, use tapered weights; otherwise uniform
            
        Returns:
            ProbeState object
        """
        if len(primes) != len(phase_angles):
            raise ValueError("primes and phase_angles must have same length")
        
        # Generate weights
        if use_tapered:
            weights = self._compute_tapered_weights(len(primes))
        else:
            weights = None  # Uniform weights
        
        return ProbeState(primes, phase_angles, weights)
    
    def _compute_tapered_weights(self, k: int) -> List[float]:
        """
        Compute tapered weights for k primes.
        
        Uses exponential taper: w_i = e^{-α * i / k}
        
        Args:
            k: Number of primes
            
        Returns:
            List of tapered weights
        """
        weights = []
        for i in range(k):
            # Exponential taper based on position
            weight = math.exp(-self.taper_alpha * i / k)
            weights.append(weight)
        
        return weights
    
    def compute_overlap(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]]
    ) -> float:
        """
        Compute overlap R = |⟨Q|A⟩| between probe and address state.
        
        According to design.md Section 2.2.2:
        R = |⟨Q|A⟩| = |∑_p w_p e^{i(φ_p^Q - φ_p^A)}|
        
        Args:
            probe: Probe state |Q⟩
            address_phases: Address state phases φ_p^A for each prime
            
        Returns:
            Overlap magnitude R (0 to 1)
        """
        total_overlap = 0.0 + 0.0j
        
        for i, prime in enumerate(probe.primes):
            if prime not in address_phases:
                continue
            
            # Get probe phase and weight
            probe_phase = probe.phase_angles[i]
            weight = probe.weights[i]
            
            # For simplicity, compute overlap with first symbol's phase
            # In a full implementation, this would iterate over all symbols
            if address_phases[prime]:
                address_phase = address_phases[prime][0]
                
                # Compute phase difference
                phase_diff = probe_phase - address_phase
                
                # Add weighted contribution
                total_overlap += weight * np.exp(1j * phase_diff)
        
        # Return magnitude (already normalized by weights which sum to 1)
        return abs(total_overlap)
    
    def refine_probe(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]],
        learning_rate: float = 0.1
    ) -> ProbeState:
        """
        Refine probe phases based on current overlap.
        
        Implements gradient descent on phase perturbations to improve overlap.
        
        Args:
            probe: Current probe state
            address_phases: Target address phases
            learning_rate: Step size for phase adjustment
            
        Returns:
            Refined ProbeState
        """
        refined_phases = []
        
        for i, prime in enumerate(probe.primes):
            if prime not in address_phases or not address_phases[prime]:
                refined_phases.append(probe.phase_angles[i])
                continue
            
            # Current probe phase
            probe_phase = probe.phase_angles[i]
            address_phase = address_phases[prime][0]
            
            # Compute phase difference
            phase_diff = probe_phase - address_phase
            
            # Adjust probe phase toward address phase
            # Wrap to [0, 2π) range
            adjustment = -learning_rate * math.sin(phase_diff)
            new_phase = (probe_phase + adjustment) % (2 * math.pi)
            
            refined_phases.append(new_phase)
        
        return ProbeState(probe.primes, refined_phases, probe.weights)
