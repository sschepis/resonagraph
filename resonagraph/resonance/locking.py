"""
Locking dynamics module for ResonaGraph.

Implements resonance locking from design.md Section 2.2.2:
- Iterative overlap computation R = |⟨Q|A⟩|
- Entropy tracking S(t) = S_0 e^{-λt}
- Resonance score RS(t) = RS_★(1 - e^{-γt})
- Convergence thresholds (R_min=0.95, S_min=0.01)

According to copilot-instructions.md:
- Track entropy S(t) decay
- Track resonance score RS(t)
- Iterations: O(k log(1/ε)), typically k=32 primes, ε=10^-6
- Limit iterations to prevent infinite loops (max ~50-100)
"""

import math
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from resonagraph.resonance.probe import ProbeState, ProbeSynthesizer


# Convergence thresholds from copilot-instructions.md
R_MIN = 0.95  # Minimum overlap for convergence
S_MIN = 0.01  # Minimum entropy for convergence

# Default parameters for entropy and resonance dynamics
DEFAULT_LAMBDA = 0.5  # Entropy decay rate
DEFAULT_GAMMA = 0.3   # Resonance score growth rate
DEFAULT_RS_STAR = 1.0 # Target resonance score

# Iteration limits
DEFAULT_MAX_ITERATIONS = 100
DEFAULT_MIN_ITERATIONS = 1


@dataclass
class LockMetrics:
    """
    Metrics from a resonance locking operation.
    
    According to design.md Section 4.1:
    Returns payload + metrics (lock_time, entropy_final)
    """
    converged: bool
    iterations: int
    final_overlap: float
    final_entropy: float
    final_resonance_score: float
    lock_time: float  # In seconds
    convergence_reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format."""
        return {
            'converged': self.converged,
            'iterations': self.iterations,
            'final_overlap': self.final_overlap,
            'final_entropy': self.final_entropy,
            'final_resonance_score': self.final_resonance_score,
            'lock_time': self.lock_time,
            'convergence_reason': self.convergence_reason
        }


class ResonanceLock:
    """
    Implements resonance locking dynamics.
    
    According to design.md Section 2.2.2 and copilot-instructions.md:
    - Iterative overlap computation R = |⟨Q|A⟩|
    - Entropy tracking S(t) = S_0 e^{-λt}
    - Resonance score RS(t) = RS_★(1 - e^{-γt})
    - Convergence: R > R_min AND S < S_min
    """
    
    def __init__(
        self,
        r_min: float = R_MIN,
        s_min: float = S_MIN,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        lambda_decay: float = DEFAULT_LAMBDA,
        gamma_growth: float = DEFAULT_GAMMA,
        rs_star: float = DEFAULT_RS_STAR
    ):
        """
        Initialize resonance lock engine.
        
        Args:
            r_min: Minimum overlap threshold for convergence
            s_min: Minimum entropy threshold for convergence
            max_iterations: Maximum number of locking iterations
            lambda_decay: Entropy decay rate λ
            gamma_growth: Resonance score growth rate γ
            rs_star: Target resonance score RS_★
        """
        self.r_min = r_min
        self.s_min = s_min
        self.max_iterations = max_iterations
        self.lambda_decay = lambda_decay
        self.gamma_growth = gamma_growth
        self.rs_star = rs_star
        
        self.synthesizer = ProbeSynthesizer()
    
    def lock(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]],
        learning_rate: float = 0.1
    ) -> Tuple[ProbeState, LockMetrics]:
        """
        Perform resonance locking to align probe with address state.
        
        According to design.md Section 2.2.2:
        - Iterative overlap computation until R > R_min and S < S_min
        - Track entropy S(t) and resonance score RS(t)
        
        Args:
            probe: Initial probe state |Q⟩
            address_phases: Target address phases
            learning_rate: Phase adjustment rate for refinement
            
        Returns:
            Tuple of (locked_probe, metrics)
        """
        start_time = time.time()
        
        # Initialize entropy and resonance score
        s_0 = self._compute_initial_entropy(probe, address_phases)
        rs_0 = self._compute_initial_resonance_score(probe, address_phases)
        
        current_probe = probe
        
        for iteration in range(self.max_iterations):
            # Compute current overlap
            overlap = self.synthesizer.compute_overlap(current_probe, address_phases)
            
            # Compute entropy S(t) = S_0 e^{-λt}
            entropy = s_0 * math.exp(-self.lambda_decay * iteration)
            
            # Compute resonance score RS(t) = RS_★(1 - e^{-γt})
            resonance_score = self.rs_star * (1 - math.exp(-self.gamma_growth * iteration))
            
            # Check convergence: R > R_min AND S < S_min
            if overlap >= self.r_min and entropy <= self.s_min:
                lock_time = time.time() - start_time
                return current_probe, LockMetrics(
                    converged=True,
                    iterations=iteration + 1,
                    final_overlap=overlap,
                    final_entropy=entropy,
                    final_resonance_score=resonance_score,
                    lock_time=lock_time,
                    convergence_reason=f"Converged: R={overlap:.4f} >= {self.r_min}, S={entropy:.6f} <= {self.s_min}"
                )
            
            # Refine probe for next iteration
            current_probe = self.synthesizer.refine_probe(
                current_probe, address_phases, learning_rate
            )
        
        # Max iterations reached without convergence
        lock_time = time.time() - start_time
        final_overlap = self.synthesizer.compute_overlap(current_probe, address_phases)
        final_entropy = s_0 * math.exp(-self.lambda_decay * self.max_iterations)
        final_rs = self.rs_star * (1 - math.exp(-self.gamma_growth * self.max_iterations))
        
        return current_probe, LockMetrics(
            converged=False,
            iterations=self.max_iterations,
            final_overlap=final_overlap,
            final_entropy=final_entropy,
            final_resonance_score=final_rs,
            lock_time=lock_time,
            convergence_reason=f"Max iterations reached: R={final_overlap:.4f}, S={final_entropy:.6f}"
        )
    
    def _compute_initial_entropy(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]]
    ) -> float:
        """
        Compute initial entropy S_0 based on payload complexity.
        
        According to copilot-instructions.md:
        Initialize S_0 from payload complexity
        
        Args:
            probe: Probe state
            address_phases: Address phases
            
        Returns:
            Initial entropy S_0
        """
        # Estimate complexity from number of symbols across all primes
        total_symbols = sum(len(phases) for phases in address_phases.values())
        
        # Higher complexity → higher initial entropy
        # Normalize to reasonable range (0.1 to 1.0)
        s_0 = min(1.0, 0.1 + total_symbols / 1000.0)
        
        return s_0
    
    def _compute_initial_resonance_score(
        self,
        probe: ProbeState,
        address_phases: Dict[int, List[float]]
    ) -> float:
        """
        Compute initial resonance score RS_0 from fingerprint mismatch.
        
        According to copilot-instructions.md:
        Initialize RS_0 from fingerprint mismatch
        
        Args:
            probe: Probe state
            address_phases: Address phases
            
        Returns:
            Initial resonance score RS_0
        """
        # Compute initial overlap (before refinement)
        initial_overlap = self.synthesizer.compute_overlap(probe, address_phases)
        
        # Lower initial overlap → lower initial RS
        rs_0 = initial_overlap
        
        return rs_0
    
    def simulate_dynamics(
        self,
        s_0: float,
        rs_0: float,
        t_max: int = 100
    ) -> List[Tuple[float, float]]:
        """
        Simulate entropy and resonance score dynamics over time.
        
        According to copilot-instructions.md Section 3:
        - Evolve S(t) = S_0 e^{-λt}
        - Evolve RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt}
        
        Args:
            s_0: Initial entropy
            rs_0: Initial resonance score
            t_max: Maximum time steps to simulate
            
        Returns:
            List of (S(t), RS(t)) tuples
        """
        dynamics = []
        
        for t in range(t_max + 1):
            # S(t) = S_0 e^{-λt}
            s_t = s_0 * math.exp(-self.lambda_decay * t)
            
            # RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt}
            rs_t = self.rs_star - (self.rs_star - rs_0) * math.exp(-self.gamma_growth * t)
            
            dynamics.append((s_t, rs_t))
        
        return dynamics
    
    def check_convergence(
        self,
        overlap: float,
        entropy: float
    ) -> Tuple[bool, str]:
        """
        Check if convergence criteria are met.
        
        According to copilot-instructions.md:
        Converged when R > R_min AND S < S_min
        
        Args:
            overlap: Current overlap R
            entropy: Current entropy S
            
        Returns:
            Tuple of (converged, reason)
        """
        r_converged = overlap >= self.r_min
        s_converged = entropy <= self.s_min
        
        if r_converged and s_converged:
            return True, f"Both thresholds met: R={overlap:.4f} >= {self.r_min}, S={entropy:.6f} <= {self.s_min}"
        elif r_converged:
            return False, f"Overlap met but entropy too high: R={overlap:.4f} >= {self.r_min}, S={entropy:.6f} > {self.s_min}"
        elif s_converged:
            return False, f"Entropy met but overlap too low: R={overlap:.4f} < {self.r_min}, S={entropy:.6f} <= {self.s_min}"
        else:
            return False, f"Neither threshold met: R={overlap:.4f} < {self.r_min}, S={entropy:.6f} > {self.s_min}"
