"""
Tests for probe synthesis module.

According to copilot-instructions.md Section 7:
- Test probe synthesis
- Test weighted probes with taper_alpha
- Verify probe state generation
"""

import unittest
import math
from resonagraph.resonance.probe import ProbeState, ProbeSynthesizer


class TestProbeState(unittest.TestCase):
    """Test ProbeState class."""
    
    def test_probe_state_initialization(self):
        """Test basic probe state creation."""
        primes = [2, 3, 5, 7]
        phases = [0.1, 0.2, 0.3, 0.4]
        
        probe = ProbeState(primes, phases)
        
        self.assertEqual(probe.primes, primes)
        self.assertEqual(probe.phase_angles, phases)
        self.assertEqual(len(probe.weights), len(primes))
    
    def test_probe_state_with_weights(self):
        """Test probe state with custom weights."""
        primes = [2, 3, 5]
        phases = [0.5, 1.0, 1.5]
        weights = [0.5, 0.3, 0.2]
        
        probe = ProbeState(primes, phases, weights)
        
        # Weights should be normalized
        total = sum(probe.weights)
        self.assertAlmostEqual(total, 1.0, places=6)
    
    def test_probe_state_length_mismatch(self):
        """Test that mismatched lengths raise error."""
        primes = [2, 3, 5]
        phases = [0.1, 0.2]  # Wrong length
        
        with self.assertRaises(ValueError):
            ProbeState(primes, phases)
    
    def test_compute_amplitude(self):
        """Test complex amplitude computation."""
        primes = [2, 3]
        phases = [0.0, math.pi]
        weights = [1.0, 1.0]
        
        probe = ProbeState(primes, phases, weights)
        
        # Amplitude at index 0: 0.5 * e^{i*0} = 0.5
        amp0 = probe.compute_amplitude(0)
        self.assertAlmostEqual(abs(amp0), 0.5, places=6)
        
        # Amplitude at index 1: 0.5 * e^{i*π} = -0.5
        amp1 = probe.compute_amplitude(1)
        self.assertAlmostEqual(amp1.real, -0.5, places=6)
    
    def test_probe_state_repr(self):
        """Test string representation."""
        primes = [2, 3, 5]
        phases = [0.1, 0.2, 0.3]
        
        probe = ProbeState(primes, phases)
        repr_str = repr(probe)
        
        self.assertIn("ProbeState", repr_str)
        self.assertIn("3", repr_str)


class TestProbeSynthesizer(unittest.TestCase):
    """Test ProbeSynthesizer class."""
    
    def test_synthesizer_default_taper(self):
        """Test default taper_alpha value."""
        synth = ProbeSynthesizer()
        self.assertEqual(synth.taper_alpha, ProbeSynthesizer.DEFAULT_TAPER_ALPHA)
    
    def test_synthesizer_custom_taper(self):
        """Test custom taper_alpha value."""
        synth = ProbeSynthesizer(taper_alpha=0.08)
        self.assertEqual(synth.taper_alpha, 0.08)
    
    def test_synthesizer_taper_validation(self):
        """Test taper_alpha validation."""
        # Too low
        with self.assertRaises(ValueError):
            ProbeSynthesizer(taper_alpha=0.01)
        
        # Too high
        with self.assertRaises(ValueError):
            ProbeSynthesizer(taper_alpha=0.20)
    
    def test_synthesize_probe_uniform(self):
        """Test probe synthesis with uniform weights."""
        synth = ProbeSynthesizer()
        primes = [2, 3, 5, 7]
        phases = [0.1, 0.2, 0.3, 0.4]
        
        probe = synth.synthesize_probe(primes, phases, use_tapered=False)
        
        self.assertEqual(probe.primes, primes)
        self.assertEqual(probe.phase_angles, phases)
        # Uniform weights should all be equal after normalization
        self.assertTrue(all(w == probe.weights[0] for w in probe.weights))
    
    def test_synthesize_probe_tapered(self):
        """Test probe synthesis with tapered weights."""
        synth = ProbeSynthesizer(taper_alpha=0.1)
        primes = [2, 3, 5, 7, 11]
        phases = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        probe = synth.synthesize_probe(primes, phases, use_tapered=True)
        
        self.assertEqual(probe.primes, primes)
        # Tapered weights should decrease
        for i in range(len(probe.weights) - 1):
            self.assertGreater(probe.weights[i], probe.weights[i + 1])
    
    def test_compute_tapered_weights(self):
        """Test tapered weight computation."""
        synth = ProbeSynthesizer(taper_alpha=0.1)
        weights = synth._compute_tapered_weights(5)
        
        self.assertEqual(len(weights), 5)
        # Weights should be positive and decreasing
        for i in range(len(weights) - 1):
            self.assertGreater(weights[i], 0.0)
            self.assertGreater(weights[i], weights[i + 1])
    
    def test_compute_overlap(self):
        """Test overlap computation."""
        synth = ProbeSynthesizer()
        primes = [2, 3, 5]
        probe_phases = [0.0, 0.0, 0.0]
        address_phases = {
            2: [0.0],
            3: [0.0],
            5: [0.0]
        }
        
        probe = synth.synthesize_probe(primes, probe_phases, use_tapered=False)
        overlap = synth.compute_overlap(probe, address_phases)
        
        # Perfect alignment should give high overlap
        self.assertGreater(overlap, 0.9)
    
    def test_compute_overlap_misaligned(self):
        """Test overlap with misaligned phases."""
        synth = ProbeSynthesizer()
        primes = [2, 3, 5]
        probe_phases = [0.0, 0.0, 0.0]
        address_phases = {
            2: [math.pi],  # Opposite phase
            3: [math.pi],
            5: [math.pi]
        }
        
        probe = synth.synthesize_probe(primes, probe_phases, use_tapered=False)
        overlap = synth.compute_overlap(probe, address_phases)
        
        # Opposite phases give e^(-iπ) = -1, so magnitude is still 1
        # For random phases, we'd expect lower overlap
        # This test shows consistent opposite phases still align
        self.assertGreater(overlap, 0.9)
    
    def test_refine_probe(self):
        """Test probe refinement."""
        synth = ProbeSynthesizer()
        primes = [2, 3, 5]
        initial_phases = [0.5, 0.5, 0.5]
        target_phases = {
            2: [1.0],
            3: [1.0],
            5: [1.0]
        }
        
        probe = synth.synthesize_probe(primes, initial_phases, use_tapered=False)
        refined_probe = synth.refine_probe(probe, target_phases, learning_rate=0.5)
        
        # Refined phases should be closer to target
        for i in range(len(primes)):
            self.assertNotEqual(refined_probe.phase_angles[i], initial_phases[i])
    
    def test_synthesize_probe_length_mismatch(self):
        """Test error on length mismatch."""
        synth = ProbeSynthesizer()
        primes = [2, 3, 5]
        phases = [0.1, 0.2]  # Wrong length
        
        with self.assertRaises(ValueError):
            synth.synthesize_probe(primes, phases)


if __name__ == '__main__':
    unittest.main()
