"""
Residue extraction module for ResonaGraph.

Implements residue extraction from design.md Section 2.2.2:
- Extract phase differences Δθ_p → r_j ≡ m_j mod p_i
- Phase measurement and quantization

According to copilot-instructions.md:
- Extract phase differences Δθ_p → r_j ≡ m_j mod p_i
- Quantize phases for symbol recovery
"""

import math
from typing import List, Dict, Any, Tuple


class ResidueExtractor:
    """
    Extracts residues from phase differences for CRT reconstruction.
    
    According to design.md Section 2.2.2:
    - Residue Extraction: Δθ_p → r_j ≡ m_j mod p_i
    - Phase measurement and quantization
    """
    
    def __init__(self):
        """Initialize residue extractor."""
        pass
    
    def extract_residues(
        self,
        locked_probe_phases: List[float],
        address_phases: List[float],
        prime: int
    ) -> List[int]:
        """
        Extract residues from phase differences for a single prime.
        
        According to design.md Eq. 6:
        Δθ_p → r_j ≡ m_j mod p_i
        
        Args:
            locked_probe_phases: Phase angles from locked probe
            address_phases: Phase angles from address state
            prime: Prime number p for modular arithmetic
            
        Returns:
            List of residues r_j for each symbol position
        """
        if len(locked_probe_phases) != len(address_phases):
            # Handle length mismatch by using the shorter length
            min_len = min(len(locked_probe_phases), len(address_phases))
            locked_probe_phases = locked_probe_phases[:min_len]
            address_phases = address_phases[:min_len]
        
        residues = []
        
        for probe_phase, addr_phase in zip(locked_probe_phases, address_phases):
            # Compute phase difference Δθ_p
            phase_diff = self._compute_phase_difference(probe_phase, addr_phase)
            
            # Quantize phase difference to symbol residue
            residue = self._quantize_to_residue(phase_diff, prime)
            
            residues.append(residue)
        
        return residues
    
    def _compute_phase_difference(
        self,
        probe_phase: float,
        address_phase: float
    ) -> float:
        """
        Compute phase difference Δθ = θ_probe - θ_address.
        
        Normalizes to [0, 2π) range.
        
        Args:
            probe_phase: Phase from locked probe
            address_phase: Phase from address state
            
        Returns:
            Phase difference in [0, 2π)
        """
        # Compute difference
        delta_theta = probe_phase - address_phase
        
        # Normalize to [0, 2π) range
        two_pi = 2 * math.pi
        delta_theta = delta_theta % two_pi
        
        return delta_theta
    
    def _quantize_to_residue(
        self,
        phase_diff: float,
        prime: int
    ) -> int:
        """
        Quantize phase difference to symbol residue modulo prime.
        
        According to design.md:
        θ_p = 2π(m_j mod p + ...), so we extract m_j mod p
        
        Args:
            phase_diff: Phase difference Δθ
            prime: Prime number p
            
        Returns:
            Residue r = m_j mod p
        """
        # Normalize phase to [0, 1) by dividing by 2π
        two_pi = 2 * math.pi
        normalized_phase = phase_diff / two_pi
        
        # Scale by prime to get approximate symbol modulo prime
        scaled_value = normalized_phase * prime
        
        # Round to nearest integer and take modulo prime
        residue = round(scaled_value) % prime
        
        return residue
    
    def extract_all_residues(
        self,
        locked_probe: Any,  # ProbeState
        address_phases: Dict[int, List[float]]
    ) -> Dict[int, List[int]]:
        """
        Extract residues for all primes in the probe.
        
        Args:
            locked_probe: Locked probe state with refined phases
            address_phases: Address phases for all primes
            
        Returns:
            Dictionary mapping each prime to list of residues
        """
        all_residues = {}
        
        for i, prime in enumerate(locked_probe.primes):
            if prime not in address_phases:
                continue
            
            # Get probe phase (single value per prime for simplicity)
            probe_phases = [locked_probe.phase_angles[i]]
            
            # Get address phases for this prime
            addr_phases = address_phases[prime]
            
            # Extract residues
            residues = self.extract_residues(probe_phases, addr_phases, prime)
            all_residues[prime] = residues
        
        return all_residues
    
    def validate_residues(
        self,
        residues: List[Tuple[int, int]]
    ) -> bool:
        """
        Validate that residues are within valid range.
        
        Args:
            residues: List of (residue, prime) tuples
            
        Returns:
            True if all residues are valid
        """
        for residue, prime in residues:
            if not (0 <= residue < prime):
                return False
        
        return True
    
    def compute_confidence(
        self,
        residues: Dict[int, List[int]],
        overlap: float,
        entropy: float
    ) -> float:
        """
        Compute confidence score for extracted residues.
        
        Based on locking metrics (overlap and entropy).
        
        Args:
            residues: Extracted residues
            overlap: Final overlap from locking
            entropy: Final entropy from locking
            
        Returns:
            Confidence score (0 to 1)
        """
        # Higher overlap and lower entropy → higher confidence
        # Simple linear combination
        overlap_weight = 0.7
        entropy_weight = 0.3
        
        # Normalize entropy (assume max ~1.0)
        normalized_entropy = max(0.0, min(1.0, entropy))
        
        confidence = (
            overlap_weight * overlap +
            entropy_weight * (1.0 - normalized_entropy)
        )
        
        return confidence
