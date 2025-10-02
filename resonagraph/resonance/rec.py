"""
REC (Resonant Eventual Consistency) conflict resolution module.

Implements conflict detection and thermodynamic selection from design.md Section 2.3
and rec.md:
- Conflict detection via multiple epoch beacons
- Thermodynamic simulation of S(t) = S_0 e^{-λt} and RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt}
- Winner selection: min(S_stable) AND max(RS_stable)
- Tiebreak by epoch recency

According to copilot-instructions.md Phase 4:
- Detect Conflict: Multiple epochs indicate fork
- Simulate Dynamics: Evolve S(t) and RS(t) to steady state
- Compute Steady States: Extract S_stable and RS_stable
- Select Winner: Choose epoch with best thermodynamic profile
- Propagate: Gossip winning beacon
"""

import math
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


# Default simulation parameters from rec.md
DEFAULT_LAMBDA = 0.8  # Entropy decay rate
DEFAULT_GAMMA = 0.6   # Resonance score growth rate
DEFAULT_RS_STAR = 0.9976  # Target resonance score
DEFAULT_T_MAX = 10.0  # Maximum simulation time (in multiples of τ)
DEFAULT_DT = 0.1  # Time step for simulation


@dataclass
class ConflictCandidate:
    """
    Represents a candidate epoch in a conflict scenario.
    
    According to rec.md:
    - epoch: Timestamp of the write
    - s_0: Initial entropy (from payload complexity)
    - rs_0: Initial resonance score (from fingerprint mismatch)
    - lambda_decay: Entropy decay rate (depends on prime count k)
    - gamma_growth: Resonance score growth rate (depends on phase alignment)
    - rs_star: Maximum achievable resonance score
    """
    epoch: float
    s_0: float
    rs_0: float
    lambda_decay: float = DEFAULT_LAMBDA
    gamma_growth: float = DEFAULT_GAMMA
    rs_star: float = DEFAULT_RS_STAR
    
    # Computed steady states (filled by simulation)
    s_stable: Optional[float] = None
    rs_stable: Optional[float] = None
    
    # Additional metadata
    beacon_data: Optional[Dict[str, Any]] = None
    
    def __repr__(self) -> str:
        s_stable_str = f"{self.s_stable:.4f}" if self.s_stable is not None else "None"
        rs_stable_str = f"{self.rs_stable:.4f}" if self.rs_stable is not None else "None"
        return (f"ConflictCandidate(epoch={self.epoch}, "
                f"s_0={self.s_0:.4f}, rs_0={self.rs_0:.4f}, "
                f"s_stable={s_stable_str}, "
                f"rs_stable={rs_stable_str})")


class RECSimulator:
    """
    Implements REC thermodynamic simulation and winner selection.
    
    According to rec.md and copilot-instructions.md Section 3:
    - Simulate entropy decay: S(t) = S_0 e^{-λt}
    - Simulate resonance score growth: RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt}
    - Run until t_max or steady state reached
    - Select winner based on thermodynamic profile
    """
    
    def __init__(
        self,
        t_max: float = DEFAULT_T_MAX,
        dt: float = DEFAULT_DT,
        convergence_threshold: float = 1e-6
    ):
        """
        Initialize REC simulator.
        
        Args:
            t_max: Maximum simulation time (seconds or multiples of τ)
            dt: Time step for numerical integration
            convergence_threshold: Threshold for detecting steady state
        """
        self.t_max = t_max
        self.dt = dt
        self.convergence_threshold = convergence_threshold
    
    def simulate_entropy(
        self,
        s_0: float,
        lambda_decay: float,
        t: float
    ) -> float:
        """
        Compute entropy at time t: S(t) = S_0 e^{-λt}
        
        According to rec.md Section "How to Arrive at the Resolution":
        Solve dS/dt = -λS → S(t) = S_0 e^{-λt}
        
        Args:
            s_0: Initial entropy
            lambda_decay: Decay rate λ (depends on prime count k)
            t: Time
            
        Returns:
            Entropy S(t)
        """
        return s_0 * math.exp(-lambda_decay * t)
    
    def simulate_resonance_score(
        self,
        rs_0: float,
        rs_star: float,
        gamma_growth: float,
        t: float
    ) -> float:
        """
        Compute resonance score at time t: RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt}
        
        According to rec.md Section "How to Arrive at the Resolution":
        Approximate as RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt}
        
        Args:
            rs_0: Initial resonance score
            rs_star: Maximum achievable resonance score RS_★
            gamma_growth: Growth rate γ (depends on phase alignment)
            t: Time
            
        Returns:
            Resonance score RS(t)
        """
        return rs_star - (rs_star - rs_0) * math.exp(-gamma_growth * t)
    
    def simulate_dynamics(
        self,
        candidate: ConflictCandidate,
        return_trajectory: bool = False
    ) -> ConflictCandidate:
        """
        Simulate thermodynamic dynamics for a conflict candidate.
        
        According to rec.md:
        - Evolve S(t) and RS(t) until t_max or steady state
        - Extract S_stable and RS_stable at convergence
        
        Args:
            candidate: ConflictCandidate to simulate
            return_trajectory: If True, store full S(t), RS(t) trajectory
            
        Returns:
            Updated candidate with s_stable and rs_stable filled
        """
        t = 0.0
        trajectory = []
        
        prev_s = None
        prev_rs = None
        
        # Numerical integration using exponential formulas
        while t <= self.t_max:
            # Compute current values
            s_t = self.simulate_entropy(candidate.s_0, candidate.lambda_decay, t)
            rs_t = self.simulate_resonance_score(
                candidate.rs_0, candidate.rs_star, candidate.gamma_growth, t
            )
            
            if return_trajectory:
                trajectory.append({'t': t, 's': s_t, 'rs': rs_t})
            
            # Check for steady state (both S and RS converged)
            if prev_s is not None and prev_rs is not None:
                s_change = abs(s_t - prev_s)
                rs_change = abs(rs_t - prev_rs)
                
                if s_change < self.convergence_threshold and rs_change < self.convergence_threshold:
                    # Steady state reached
                    candidate.s_stable = s_t
                    candidate.rs_stable = rs_t
                    break
            
            prev_s = s_t
            prev_rs = rs_t
            t += self.dt
        
        # If we reached t_max without converging, use final values
        if candidate.s_stable is None:
            candidate.s_stable = self.simulate_entropy(
                candidate.s_0, candidate.lambda_decay, self.t_max
            )
            candidate.rs_stable = self.simulate_resonance_score(
                candidate.rs_0, candidate.rs_star, candidate.gamma_growth, self.t_max
            )
        
        if return_trajectory:
            candidate.beacon_data = candidate.beacon_data or {}
            candidate.beacon_data['trajectory'] = trajectory
        
        return candidate
    
    def select_winner(
        self,
        candidates: List[ConflictCandidate]
    ) -> Tuple[ConflictCandidate, str]:
        """
        Select winner from conflict candidates using thermodynamic selection.
        
        According to rec.md Section "How to Arrive at the Resolution":
        - e wins if S_stable^e < S_stable^e' AND RS_stable^e > RS_stable^e'
        - Tiebreak by epoch recency
        
        Args:
            candidates: List of conflict candidates (must be simulated)
            
        Returns:
            (winner, reason) tuple
        """
        if not candidates:
            raise ValueError("No candidates provided")
        
        if len(candidates) == 1:
            return candidates[0], "single_candidate"
        
        # Ensure all candidates have been simulated
        for candidate in candidates:
            if candidate.s_stable is None or candidate.rs_stable is None:
                raise ValueError(f"Candidate {candidate} has not been simulated")
        
        # Find candidate with minimum entropy
        min_entropy_candidate = min(candidates, key=lambda c: c.s_stable)
        
        # Among candidates with similar minimum entropy, find max resonance score
        # Use small epsilon for entropy comparison
        entropy_epsilon = 0.001
        low_entropy_candidates = [
            c for c in candidates
            if abs(c.s_stable - min_entropy_candidate.s_stable) < entropy_epsilon
        ]
        
        if len(low_entropy_candidates) == 1:
            return low_entropy_candidates[0], "min_entropy_winner"
        
        # Multiple candidates with similar low entropy, select by max resonance
        max_resonance_candidate = max(low_entropy_candidates, key=lambda c: c.rs_stable)
        
        # Check if there's a clear resonance winner
        resonance_epsilon = 0.01
        similar_resonance = [
            c for c in low_entropy_candidates
            if abs(c.rs_stable - max_resonance_candidate.rs_stable) < resonance_epsilon
        ]
        
        if len(similar_resonance) == 1:
            return max_resonance_candidate, "max_resonance_winner"
        
        # Tiebreak by epoch recency (highest epoch wins)
        winner = max(similar_resonance, key=lambda c: c.epoch)
        return winner, "epoch_recency_tiebreak"
    
    def resolve_conflict(
        self,
        candidates: List[ConflictCandidate]
    ) -> Tuple[ConflictCandidate, Dict[str, Any]]:
        """
        Full REC conflict resolution pipeline.
        
        According to copilot-instructions.md Section 3:
        1. Detect Conflict (done by caller)
        2. Simulate Dynamics
        3. Compute Steady States
        4. Select Winner
        5. Propagate (done by caller)
        
        Args:
            candidates: List of conflict candidates
            
        Returns:
            (winner, resolution_info) tuple
        """
        start_time = time.time()
        
        # Simulate dynamics for all candidates
        simulated_candidates = []
        for candidate in candidates:
            simulated = self.simulate_dynamics(candidate)
            simulated_candidates.append(simulated)
        
        # Select winner
        winner, reason = self.select_winner(simulated_candidates)
        
        resolution_time = time.time() - start_time
        
        resolution_info = {
            'num_candidates': len(candidates),
            'winner_epoch': winner.epoch,
            'winner_s_stable': winner.s_stable,
            'winner_rs_stable': winner.rs_stable,
            'resolution_reason': reason,
            'resolution_time': resolution_time,
            'all_candidates': [
                {
                    'epoch': c.epoch,
                    's_0': c.s_0,
                    'rs_0': c.rs_0,
                    's_stable': c.s_stable,
                    'rs_stable': c.rs_stable
                }
                for c in simulated_candidates
            ]
        }
        
        return winner, resolution_info
