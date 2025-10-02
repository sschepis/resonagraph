"""
Tests for locking dynamics module.

According to copilot-instructions.md Section 7:
- Test locking convergence
- Verify entropy tracking S(t) = S_0 e^{-λt}
- Verify resonance score RS(t) = RS_★(1 - e^{-γt})
- Test convergence thresholds
"""

import unittest
import math
from resonagraph.resonance.probe import ProbeState, ProbeSynthesizer
from resonagraph.resonance.locking import ResonanceLock, LockMetrics, R_MIN, S_MIN


class TestLockMetrics(unittest.TestCase):
    """Test LockMetrics dataclass."""
    
    def test_lock_metrics_creation(self):
        """Test lock metrics initialization."""
        metrics = LockMetrics(
            converged=True,
            iterations=10,
            final_overlap=0.96,
            final_entropy=0.005,
            final_resonance_score=0.85,
            lock_time=0.05,
            convergence_reason="Converged"
        )
        
        self.assertTrue(metrics.converged)
        self.assertEqual(metrics.iterations, 10)
        self.assertAlmostEqual(metrics.final_overlap, 0.96)
    
    def test_lock_metrics_to_dict(self):
        """Test conversion to dictionary."""
        metrics = LockMetrics(
            converged=True,
            iterations=5,
            final_overlap=0.97,
            final_entropy=0.008,
            final_resonance_score=0.9,
            lock_time=0.03,
            convergence_reason="Success"
        )
        
        d = metrics.to_dict()
        
        self.assertIn('converged', d)
        self.assertIn('iterations', d)
        self.assertIn('lock_time', d)
        self.assertTrue(d['converged'])


class TestResonanceLock(unittest.TestCase):
    """Test ResonanceLock class."""
    
    def test_resonance_lock_initialization(self):
        """Test default initialization."""
        lock = ResonanceLock()
        
        self.assertEqual(lock.r_min, R_MIN)
        self.assertEqual(lock.s_min, S_MIN)
        self.assertGreater(lock.max_iterations, 0)
    
    def test_resonance_lock_custom_params(self):
        """Test custom parameters."""
        lock = ResonanceLock(
            r_min=0.90,
            s_min=0.02,
            max_iterations=50,
            lambda_decay=0.6,
            gamma_growth=0.4
        )
        
        self.assertEqual(lock.r_min, 0.90)
        self.assertEqual(lock.s_min, 0.02)
        self.assertEqual(lock.max_iterations, 50)
        self.assertEqual(lock.lambda_decay, 0.6)
        self.assertEqual(lock.gamma_growth, 0.4)
    
    def test_lock_converges(self):
        """Test successful locking convergence."""
        lock = ResonanceLock(max_iterations=100)
        synth = ProbeSynthesizer()
        
        # Create probe and address with similar phases
        primes = [2, 3, 5]
        probe_phases = [0.1, 0.2, 0.3]
        address_phases = {
            2: [0.15],
            3: [0.25],
            5: [0.35]
        }
        
        probe = synth.synthesize_probe(primes, probe_phases, use_tapered=False)
        locked_probe, metrics = lock.lock(probe, address_phases, learning_rate=0.2)
        
        # Should converge
        self.assertIsNotNone(locked_probe)
        self.assertIsInstance(metrics, LockMetrics)
        self.assertGreater(metrics.iterations, 0)
    
    def test_lock_max_iterations(self):
        """Test that locking respects max iterations."""
        lock = ResonanceLock(max_iterations=10, r_min=0.99, s_min=0.001)
        synth = ProbeSynthesizer()
        
        # Create probe and address with very different phases
        primes = [2, 3, 5]
        probe_phases = [0.0, 0.0, 0.0]
        address_phases = {
            2: [math.pi],
            3: [math.pi],
            5: [math.pi]
        }
        
        probe = synth.synthesize_probe(primes, probe_phases, use_tapered=False)
        locked_probe, metrics = lock.lock(probe, address_phases, learning_rate=0.1)
        
        # Should reach max iterations
        self.assertEqual(metrics.iterations, 10)
    
    def test_entropy_decay(self):
        """Test entropy decay S(t) = S_0 e^{-λt}."""
        lock = ResonanceLock(lambda_decay=0.5)
        s_0 = 1.0
        
        # Check entropy at different times
        dynamics = lock.simulate_dynamics(s_0, 0.5, t_max=10)
        
        # Entropy should decrease over time
        for i in range(len(dynamics) - 1):
            s_t, _ = dynamics[i]
            s_t_plus_1, _ = dynamics[i + 1]
            self.assertGreater(s_t, s_t_plus_1)
    
    def test_resonance_score_growth(self):
        """Test resonance score growth RS(t) = RS_★(1 - e^{-γt})."""
        lock = ResonanceLock(gamma_growth=0.3, rs_star=1.0)
        rs_0 = 0.2
        
        # Check resonance score at different times
        dynamics = lock.simulate_dynamics(1.0, rs_0, t_max=10)
        
        # Resonance score should increase over time
        for i in range(len(dynamics) - 1):
            _, rs_t = dynamics[i]
            _, rs_t_plus_1 = dynamics[i + 1]
            self.assertLess(rs_t, rs_t_plus_1)
    
    def test_simulate_dynamics(self):
        """Test full dynamics simulation."""
        lock = ResonanceLock()
        s_0 = 0.8
        rs_0 = 0.3
        
        dynamics = lock.simulate_dynamics(s_0, rs_0, t_max=20)
        
        self.assertEqual(len(dynamics), 21)  # t=0 to t=20
        
        # Initial values
        s_init, rs_init = dynamics[0]
        self.assertAlmostEqual(s_init, s_0)
        self.assertAlmostEqual(rs_init, rs_0)
    
    def test_check_convergence_both_met(self):
        """Test convergence when both thresholds met."""
        lock = ResonanceLock()
        
        converged, reason = lock.check_convergence(overlap=0.96, entropy=0.005)
        
        self.assertTrue(converged)
        self.assertIn("Both thresholds met", reason)
    
    def test_check_convergence_overlap_only(self):
        """Test convergence when only overlap threshold met."""
        lock = ResonanceLock()
        
        converged, reason = lock.check_convergence(overlap=0.96, entropy=0.05)
        
        self.assertFalse(converged)
        self.assertIn("entropy too high", reason)
    
    def test_check_convergence_entropy_only(self):
        """Test convergence when only entropy threshold met."""
        lock = ResonanceLock()
        
        converged, reason = lock.check_convergence(overlap=0.80, entropy=0.005)
        
        self.assertFalse(converged)
        self.assertIn("overlap too low", reason)
    
    def test_check_convergence_neither(self):
        """Test convergence when neither threshold met."""
        lock = ResonanceLock()
        
        converged, reason = lock.check_convergence(overlap=0.80, entropy=0.05)
        
        self.assertFalse(converged)
        self.assertIn("Neither threshold met", reason)
    
    def test_compute_initial_entropy(self):
        """Test initial entropy computation."""
        lock = ResonanceLock()
        synth = ProbeSynthesizer()
        
        primes = [2, 3, 5]
        phases = [0.1, 0.2, 0.3]
        address_phases = {
            2: [0.1, 0.2],
            3: [0.3, 0.4, 0.5],
            5: [0.6]
        }
        
        probe = synth.synthesize_probe(primes, phases, use_tapered=False)
        s_0 = lock._compute_initial_entropy(probe, address_phases)
        
        # Should be positive
        self.assertGreater(s_0, 0.0)
        self.assertLessEqual(s_0, 1.0)
    
    def test_compute_initial_resonance_score(self):
        """Test initial resonance score computation."""
        lock = ResonanceLock()
        synth = ProbeSynthesizer()
        
        primes = [2, 3, 5]
        phases = [0.1, 0.2, 0.3]
        address_phases = {
            2: [0.1],
            3: [0.2],
            5: [0.3]
        }
        
        probe = synth.synthesize_probe(primes, phases, use_tapered=False)
        rs_0 = lock._compute_initial_resonance_score(probe, address_phases)
        
        # Should be in [0, 1] range
        self.assertGreaterEqual(rs_0, 0.0)
        self.assertLessEqual(rs_0, 1.0)
    
    def test_lock_metrics_timing(self):
        """Test that lock_time is measured."""
        lock = ResonanceLock(max_iterations=20)
        synth = ProbeSynthesizer()
        
        primes = [2, 3, 5]
        phases = [0.1, 0.2, 0.3]
        address_phases = {
            2: [0.2],
            3: [0.3],
            5: [0.4]
        }
        
        probe = synth.synthesize_probe(primes, phases, use_tapered=False)
        _, metrics = lock.lock(probe, address_phases)
        
        # Lock time should be positive
        self.assertGreater(metrics.lock_time, 0.0)


if __name__ == '__main__':
    unittest.main()
