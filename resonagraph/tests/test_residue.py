"""
Tests for residue extraction module.

According to copilot-instructions.md Section 7:
- Test residue extraction
- Verify phase difference computation
- Test quantization to residues
"""

import unittest
import math
from resonagraph.resonance.probe import ProbeState, ProbeSynthesizer
from resonagraph.resonance.residue import ResidueExtractor


class TestResidueExtractor(unittest.TestCase):
    """Test ResidueExtractor class."""
    
    def test_extractor_initialization(self):
        """Test basic initialization."""
        extractor = ResidueExtractor()
        self.assertIsNotNone(extractor)
    
    def test_compute_phase_difference(self):
        """Test phase difference computation."""
        extractor = ResidueExtractor()
        
        # Test basic difference
        delta = extractor._compute_phase_difference(1.0, 0.5)
        self.assertAlmostEqual(delta, 0.5, places=6)
        
        # Test wrap-around
        delta = extractor._compute_phase_difference(0.5, 6.0)
        self.assertGreaterEqual(delta, 0.0)
        self.assertLess(delta, 2 * math.pi)
    
    def test_quantize_to_residue(self):
        """Test quantization of phase to residue."""
        extractor = ResidueExtractor()
        
        # Test with prime 7
        # Phase 0 should give residue 0
        residue = extractor._quantize_to_residue(0.0, 7)
        self.assertEqual(residue, 0)
        
        # Test with different phases
        residue = extractor._quantize_to_residue(math.pi, 5)
        self.assertGreaterEqual(residue, 0)
        self.assertLess(residue, 5)
    
    def test_extract_residues_single_prime(self):
        """Test residue extraction for single prime."""
        extractor = ResidueExtractor()
        
        probe_phases = [1.0, 2.0, 3.0]
        address_phases = [1.1, 2.1, 3.1]
        prime = 7
        
        residues = extractor.extract_residues(probe_phases, address_phases, prime)
        
        self.assertEqual(len(residues), 3)
        # All residues should be in valid range [0, prime)
        for r in residues:
            self.assertGreaterEqual(r, 0)
            self.assertLess(r, prime)
    
    def test_extract_residues_length_mismatch(self):
        """Test handling of length mismatch."""
        extractor = ResidueExtractor()
        
        probe_phases = [1.0, 2.0]
        address_phases = [1.1, 2.1, 3.1]
        prime = 5
        
        # Should use shorter length
        residues = extractor.extract_residues(probe_phases, address_phases, prime)
        self.assertEqual(len(residues), 2)
    
    def test_extract_all_residues(self):
        """Test extraction for all primes in probe."""
        extractor = ResidueExtractor()
        synth = ProbeSynthesizer()
        
        primes = [2, 3, 5]
        phases = [0.5, 1.0, 1.5]
        address_phases = {
            2: [0.6],
            3: [1.1],
            5: [1.6]
        }
        
        probe = synth.synthesize_probe(primes, phases, use_tapered=False)
        all_residues = extractor.extract_all_residues(probe, address_phases)
        
        # Should have residues for each prime
        self.assertEqual(len(all_residues), 3)
        self.assertIn(2, all_residues)
        self.assertIn(3, all_residues)
        self.assertIn(5, all_residues)
    
    def test_extract_all_residues_missing_prime(self):
        """Test extraction when address is missing a prime."""
        extractor = ResidueExtractor()
        synth = ProbeSynthesizer()
        
        primes = [2, 3, 5]
        phases = [0.5, 1.0, 1.5]
        address_phases = {
            2: [0.6],
            3: [1.1]
            # 5 is missing
        }
        
        probe = synth.synthesize_probe(primes, phases, use_tapered=False)
        all_residues = extractor.extract_all_residues(probe, address_phases)
        
        # Should only have residues for available primes
        self.assertEqual(len(all_residues), 2)
        self.assertIn(2, all_residues)
        self.assertIn(3, all_residues)
        self.assertNotIn(5, all_residues)
    
    def test_validate_residues_valid(self):
        """Test validation of valid residues."""
        extractor = ResidueExtractor()
        
        residues = [(0, 2), (2, 5), (6, 7)]
        self.assertTrue(extractor.validate_residues(residues))
    
    def test_validate_residues_invalid_negative(self):
        """Test validation rejects negative residues."""
        extractor = ResidueExtractor()
        
        residues = [(-1, 5), (2, 7)]
        self.assertFalse(extractor.validate_residues(residues))
    
    def test_validate_residues_invalid_too_large(self):
        """Test validation rejects residues >= prime."""
        extractor = ResidueExtractor()
        
        residues = [(5, 5), (2, 7)]  # 5 >= 5
        self.assertFalse(extractor.validate_residues(residues))
    
    def test_compute_confidence_high(self):
        """Test confidence computation with high overlap and low entropy."""
        extractor = ResidueExtractor()
        
        residues = {2: [1], 3: [2], 5: [3]}
        confidence = extractor.compute_confidence(residues, overlap=0.95, entropy=0.01)
        
        # Should have high confidence
        self.assertGreater(confidence, 0.8)
    
    def test_compute_confidence_low(self):
        """Test confidence computation with low overlap and high entropy."""
        extractor = ResidueExtractor()
        
        residues = {2: [1], 3: [2]}
        confidence = extractor.compute_confidence(residues, overlap=0.70, entropy=0.5)
        
        # Should have lower confidence
        self.assertLess(confidence, 0.8)
    
    def test_compute_confidence_range(self):
        """Test confidence is in valid range."""
        extractor = ResidueExtractor()
        
        residues = {2: [1]}
        confidence = extractor.compute_confidence(residues, overlap=0.85, entropy=0.1)
        
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
    
    def test_residue_extraction_deterministic(self):
        """Test that residue extraction is deterministic."""
        extractor = ResidueExtractor()
        
        probe_phases = [1.234, 2.345, 3.456]
        address_phases = [1.240, 2.350, 3.460]
        prime = 11
        
        residues1 = extractor.extract_residues(probe_phases, address_phases, prime)
        residues2 = extractor.extract_residues(probe_phases, address_phases, prime)
        
        self.assertEqual(residues1, residues2)
    
    def test_residue_extraction_different_primes(self):
        """Test residue extraction with different primes."""
        extractor = ResidueExtractor()
        
        probe_phases = [1.0]
        address_phases = [1.1]
        
        residue_p2 = extractor.extract_residues(probe_phases, address_phases, 2)
        residue_p5 = extractor.extract_residues(probe_phases, address_phases, 5)
        residue_p11 = extractor.extract_residues(probe_phases, address_phases, 11)
        
        # All should be valid for their respective primes
        self.assertLess(residue_p2[0], 2)
        self.assertLess(residue_p5[0], 5)
        self.assertLess(residue_p11[0], 11)


if __name__ == '__main__':
    unittest.main()
