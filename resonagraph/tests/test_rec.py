"""
Tests for REC (Resonant Eventual Consistency) conflict resolution.

Tests Phase 4 implementation according to copilot-instructions.md:
- Conflict detection
- Thermodynamic simulation (S(t), RS(t) evolution)
- Winner selection with various scenarios
- Integration with resonance plane
"""

import pytest
import math
from resonagraph.resonance.rec import (
    RECSimulator,
    ConflictCandidate,
    DEFAULT_LAMBDA,
    DEFAULT_GAMMA,
    DEFAULT_RS_STAR
)


class TestConflictCandidate:
    """Test ConflictCandidate dataclass."""
    
    def test_candidate_initialization(self):
        """Test basic candidate creation."""
        candidate = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1
        )
        
        assert candidate.epoch == 1000.0
        assert candidate.s_0 == 1.0
        assert candidate.rs_0 == 0.1
        assert candidate.lambda_decay == DEFAULT_LAMBDA
        assert candidate.gamma_growth == DEFAULT_GAMMA
        assert candidate.rs_star == DEFAULT_RS_STAR
        assert candidate.s_stable is None
        assert candidate.rs_stable is None
    
    def test_candidate_custom_parameters(self):
        """Test candidate with custom parameters."""
        candidate = ConflictCandidate(
            epoch=2000.0,
            s_0=1.2,
            rs_0=0.05,
            lambda_decay=0.5,
            gamma_growth=0.4,
            rs_star=0.98
        )
        
        assert candidate.lambda_decay == 0.5
        assert candidate.gamma_growth == 0.4
        assert candidate.rs_star == 0.98
    
    def test_candidate_repr(self):
        """Test string representation."""
        candidate = ConflictCandidate(epoch=1000.0, s_0=1.0, rs_0=0.1)
        repr_str = repr(candidate)
        
        assert "ConflictCandidate" in repr_str
        assert "epoch=1000.0" in repr_str
        assert "s_0=1.0000" in repr_str


class TestRECSimulator:
    """Test REC simulator core functionality."""
    
    def test_simulator_initialization(self):
        """Test simulator initialization with defaults."""
        simulator = RECSimulator()
        
        assert simulator.t_max == 10.0
        assert simulator.dt == 0.1
        assert simulator.convergence_threshold == 1e-6
    
    def test_simulator_custom_parameters(self):
        """Test simulator with custom parameters."""
        simulator = RECSimulator(t_max=20.0, dt=0.05, convergence_threshold=1e-8)
        
        assert simulator.t_max == 20.0
        assert simulator.dt == 0.05
        assert simulator.convergence_threshold == 1e-8
    
    def test_simulate_entropy_decay(self):
        """Test entropy decay: S(t) = S_0 e^{-λt}"""
        simulator = RECSimulator()
        s_0 = 1.0
        lambda_decay = 0.8
        
        # At t=0, entropy should be s_0
        s_0_result = simulator.simulate_entropy(s_0, lambda_decay, 0.0)
        assert abs(s_0_result - s_0) < 1e-10
        
        # Entropy should decay exponentially
        s_2 = simulator.simulate_entropy(s_0, lambda_decay, 2.0)
        expected_s_2 = s_0 * math.exp(-lambda_decay * 2.0)
        assert abs(s_2 - expected_s_2) < 1e-10
        
        # At large t, entropy approaches 0
        s_100 = simulator.simulate_entropy(s_0, lambda_decay, 100.0)
        assert s_100 < 1e-30
    
    def test_simulate_entropy_different_lambda(self):
        """Test entropy decay with different λ values."""
        simulator = RECSimulator()
        s_0 = 1.0
        t = 5.0
        
        # Higher λ → faster decay
        s_fast = simulator.simulate_entropy(s_0, 0.8, t)
        s_slow = simulator.simulate_entropy(s_0, 0.5, t)
        
        assert s_fast < s_slow
    
    def test_simulate_resonance_score_growth(self):
        """Test resonance score growth: RS(t) = RS_★ - (RS_★ - RS_0)e^{-γt}"""
        simulator = RECSimulator()
        rs_0 = 0.1
        rs_star = 0.9976
        gamma_growth = 0.6
        
        # At t=0, resonance score should be rs_0
        rs_0_result = simulator.simulate_resonance_score(rs_0, rs_star, gamma_growth, 0.0)
        assert abs(rs_0_result - rs_0) < 1e-10
        
        # Resonance score should grow toward rs_star
        rs_2 = simulator.simulate_resonance_score(rs_0, rs_star, gamma_growth, 2.0)
        expected_rs_2 = rs_star - (rs_star - rs_0) * math.exp(-gamma_growth * 2.0)
        assert abs(rs_2 - expected_rs_2) < 1e-10
        
        # Should be between rs_0 and rs_star
        assert rs_0 < rs_2 < rs_star
        
        # At large t, approaches rs_star
        rs_100 = simulator.simulate_resonance_score(rs_0, rs_star, gamma_growth, 100.0)
        assert abs(rs_100 - rs_star) < 1e-10
    
    def test_simulate_resonance_score_different_gamma(self):
        """Test resonance score growth with different γ values."""
        simulator = RECSimulator()
        rs_0 = 0.1
        rs_star = 0.9976
        t = 5.0
        
        # Higher γ → faster growth
        rs_fast = simulator.simulate_resonance_score(rs_0, rs_star, 0.6, t)
        rs_slow = simulator.simulate_resonance_score(rs_0, rs_star, 0.4, t)
        
        # Both should be between rs_0 and rs_star
        assert rs_0 < rs_slow < rs_star
        assert rs_0 < rs_fast < rs_star
        
        # Faster growth should be closer to rs_star
        assert rs_fast > rs_slow


class TestRECDynamicsSimulation:
    """Test full dynamics simulation."""
    
    def test_simulate_dynamics_basic(self):
        """Test basic dynamics simulation."""
        simulator = RECSimulator()
        candidate = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1,
            lambda_decay=0.8,
            gamma_growth=0.6
        )
        
        result = simulator.simulate_dynamics(candidate)
        
        # Should fill in stable states
        assert result.s_stable is not None
        assert result.rs_stable is not None
        
        # S_stable should be very low (entropy decays)
        assert result.s_stable < 0.1
        
        # RS_stable should be high (resonance score grows)
        assert result.rs_stable > 0.9
    
    def test_simulate_dynamics_fast_convergence(self):
        """Test dynamics with fast convergence parameters."""
        simulator = RECSimulator(t_max=10.0, dt=0.1)
        candidate = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1,
            lambda_decay=0.8,  # Fast decay
            gamma_growth=0.6,  # Fast growth
            rs_star=0.9976
        )
        
        result = simulator.simulate_dynamics(candidate)
        
        # Should converge quickly
        assert result.s_stable < 0.05
        assert result.rs_stable > 0.95
    
    def test_simulate_dynamics_slow_convergence(self):
        """Test dynamics with slow convergence parameters."""
        simulator = RECSimulator(t_max=10.0, dt=0.1)
        candidate = ConflictCandidate(
            epoch=1000.0,
            s_0=1.2,
            rs_0=0.05,
            lambda_decay=0.5,  # Slow decay
            gamma_growth=0.4,  # Slow growth
            rs_star=0.9819
        )
        
        result = simulator.simulate_dynamics(candidate)
        
        # Should converge slower, but exponential decay is still quite fast
        # At t=10 with lambda=0.5: S = 1.2 * e^(-0.5*10) = 1.2 * e^-5 ≈ 0.0081
        assert result.s_stable > 0.001  # Still quite low due to exponential
        assert result.rs_stable < 0.98  # Won't reach as high as fast params
    
    def test_simulate_dynamics_trajectory(self):
        """Test trajectory recording."""
        simulator = RECSimulator()
        candidate = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1
        )
        
        result = simulator.simulate_dynamics(candidate, return_trajectory=True)
        
        # Should have trajectory data
        assert result.beacon_data is not None
        assert 'trajectory' in result.beacon_data
        trajectory = result.beacon_data['trajectory']
        
        # Should have multiple time steps
        assert len(trajectory) > 1
        
        # Each step should have t, s, rs
        for step in trajectory:
            assert 't' in step
            assert 's' in step
            assert 'rs' in step
        
        # Entropy should decrease over time
        assert trajectory[-1]['s'] < trajectory[0]['s']
        
        # Resonance score should increase over time
        assert trajectory[-1]['rs'] > trajectory[0]['rs']


class TestRECWinnerSelection:
    """Test winner selection logic."""
    
    def test_select_winner_single_candidate(self):
        """Test with single candidate."""
        simulator = RECSimulator()
        candidate = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1
        )
        candidate = simulator.simulate_dynamics(candidate)
        
        winner, reason = simulator.select_winner([candidate])
        
        assert winner == candidate
        assert reason == "single_candidate"
    
    def test_select_winner_clear_entropy_winner(self):
        """Test selection with clear entropy winner."""
        simulator = RECSimulator()
        
        # Candidate with low entropy (fast convergence)
        candidate1 = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1,
            lambda_decay=0.8,
            gamma_growth=0.6,
            rs_star=0.9976
        )
        
        # Candidate with high entropy (slow convergence)
        candidate2 = ConflictCandidate(
            epoch=1001.0,
            s_0=1.2,
            rs_0=0.05,
            lambda_decay=0.5,
            gamma_growth=0.4,
            rs_star=0.9819
        )
        
        candidate1 = simulator.simulate_dynamics(candidate1)
        candidate2 = simulator.simulate_dynamics(candidate2)
        
        winner, reason = simulator.select_winner([candidate1, candidate2])
        
        # Candidate1 should win (lower entropy)
        assert winner == candidate1
        assert reason == "min_entropy_winner"
        assert winner.s_stable < candidate2.s_stable
    
    def test_select_winner_resonance_tiebreak(self):
        """Test selection with resonance score tiebreak."""
        simulator = RECSimulator()
        
        # Two candidates with similar entropy but different resonance
        candidate1 = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1,
            lambda_decay=0.8,
            gamma_growth=0.6,
            rs_star=0.9976
        )
        
        candidate2 = ConflictCandidate(
            epoch=1001.0,
            s_0=1.0001,  # Very similar initial entropy
            rs_0=0.05,
            lambda_decay=0.8,
            gamma_growth=0.4,  # Slower resonance growth
            rs_star=0.9819
        )
        
        candidate1 = simulator.simulate_dynamics(candidate1)
        candidate2 = simulator.simulate_dynamics(candidate2)
        
        winner, reason = simulator.select_winner([candidate1, candidate2])
        
        # Candidate1 should win (higher resonance score)
        assert winner == candidate1
        assert winner.rs_stable > candidate2.rs_stable
    
    def test_select_winner_epoch_tiebreak(self):
        """Test selection with epoch recency tiebreak."""
        simulator = RECSimulator()
        
        # Two candidates with identical dynamics but different epochs
        candidate1 = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1,
            lambda_decay=0.8,
            gamma_growth=0.6
        )
        
        candidate2 = ConflictCandidate(
            epoch=1002.0,  # More recent
            s_0=1.0,
            rs_0=0.1,
            lambda_decay=0.8,
            gamma_growth=0.6
        )
        
        candidate1 = simulator.simulate_dynamics(candidate1)
        candidate2 = simulator.simulate_dynamics(candidate2)
        
        winner, reason = simulator.select_winner([candidate1, candidate2])
        
        # Candidate2 should win (more recent epoch)
        assert winner == candidate2
        assert reason == "epoch_recency_tiebreak"
        assert winner.epoch > candidate1.epoch
    
    def test_select_winner_no_candidates_error(self):
        """Test error handling with no candidates."""
        simulator = RECSimulator()
        
        with pytest.raises(ValueError, match="No candidates provided"):
            simulator.select_winner([])
    
    def test_select_winner_unsimulated_candidate_error(self):
        """Test error handling with unsimulated candidate."""
        simulator = RECSimulator()
        candidate1 = ConflictCandidate(epoch=1000.0, s_0=1.0, rs_0=0.1)
        candidate2 = ConflictCandidate(epoch=1001.0, s_0=1.2, rs_0=0.05)
        
        # Simulate only one
        candidate1 = simulator.simulate_dynamics(candidate1)
        
        # Should fail because candidate2 is not simulated
        with pytest.raises(ValueError, match="has not been simulated"):
            simulator.select_winner([candidate1, candidate2])


class TestRECConflictResolution:
    """Test full REC conflict resolution pipeline."""
    
    def test_resolve_conflict_basic(self):
        """Test basic conflict resolution."""
        simulator = RECSimulator()
        
        candidates = [
            ConflictCandidate(epoch=1000.0, s_0=1.0, rs_0=0.1,
                            lambda_decay=0.8, gamma_growth=0.6, rs_star=0.9976),
            ConflictCandidate(epoch=1001.0, s_0=1.2, rs_0=0.05,
                            lambda_decay=0.5, gamma_growth=0.4, rs_star=0.9819)
        ]
        
        winner, info = simulator.resolve_conflict(candidates)
        
        # Should return winner and resolution info
        assert winner is not None
        assert isinstance(info, dict)
        
        # Info should contain expected fields
        assert info['num_candidates'] == 2
        assert 'winner_epoch' in info
        assert 'winner_s_stable' in info
        assert 'winner_rs_stable' in info
        assert 'resolution_reason' in info
        assert 'resolution_time' in info
        assert 'all_candidates' in info
        
        # All candidates should be in info
        assert len(info['all_candidates']) == 2
    
    def test_resolve_conflict_matches_rec_example(self):
        """Test that simulation matches rec.md example."""
        # From rec.md simulation example
        simulator = RECSimulator(t_max=10.0, dt=0.1)
        
        # Write e (from Node A)
        candidate_e = ConflictCandidate(
            epoch=1000.0,
            s_0=1.0,
            rs_0=0.1,
            lambda_decay=0.8,
            gamma_growth=0.6,
            rs_star=0.9976
        )
        
        # Write e' (from Node B)
        candidate_e_prime = ConflictCandidate(
            epoch=1001.0,
            s_0=1.2,
            rs_0=0.05,
            lambda_decay=0.5,
            gamma_growth=0.4,
            rs_star=0.9819
        )
        
        winner, info = simulator.resolve_conflict([candidate_e, candidate_e_prime])
        
        # According to rec.md, e should win (lower entropy and higher resonance)
        assert winner.epoch == candidate_e.epoch
        
        # Check that values follow expected trends from rec.md
        # Candidate e should have much lower entropy due to higher lambda
        # At t=10: S^e = 1.0*e^(-0.8*10) = e^-8 ≈ 0.00034
        #          S^e' = 1.2*e^(-0.5*10) = 1.2*e^-5 ≈ 0.0081
        assert winner.s_stable < 0.001  # Very low entropy
        assert winner.rs_stable > 0.99  # Very high resonance
        
        # Loser should have higher entropy and lower resonance
        loser = candidate_e_prime
        loser = simulator.simulate_dynamics(loser)
        assert loser.s_stable > winner.s_stable  # Higher entropy
        assert loser.rs_stable < winner.rs_stable  # Lower resonance
    
    def test_resolve_conflict_three_candidates(self):
        """Test conflict resolution with three candidates."""
        simulator = RECSimulator()
        
        candidates = [
            ConflictCandidate(epoch=1000.0, s_0=1.0, rs_0=0.1,
                            lambda_decay=0.8, gamma_growth=0.6),
            ConflictCandidate(epoch=1001.0, s_0=1.2, rs_0=0.05,
                            lambda_decay=0.5, gamma_growth=0.4),
            ConflictCandidate(epoch=1002.0, s_0=0.9, rs_0=0.15,
                            lambda_decay=0.9, gamma_growth=0.7)
        ]
        
        winner, info = simulator.resolve_conflict(candidates)
        
        assert info['num_candidates'] == 3
        assert len(info['all_candidates']) == 3
        
        # Winner should have best thermodynamic profile
        # Candidate with highest lambda_decay and gamma_growth should win
        assert winner.epoch == 1002.0
    
    def test_resolve_conflict_timing(self):
        """Test that resolution completes in reasonable time."""
        simulator = RECSimulator()
        
        candidates = [
            ConflictCandidate(epoch=1000.0 + i, s_0=1.0 + i*0.1, rs_0=0.1 - i*0.01)
            for i in range(5)
        ]
        
        winner, info = simulator.resolve_conflict(candidates)
        
        # Should complete in less than 1 second
        assert info['resolution_time'] < 1.0
        
        # Should resolve to one winner
        assert winner is not None
