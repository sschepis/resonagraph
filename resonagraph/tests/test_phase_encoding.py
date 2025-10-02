"""
Tests for phase encoding module.

According to copilot-instructions.md Section 7:
- Phase Encoding: Verify θ_p calculations match specifications
- CRT Reconstruction: Test symbol recovery across various prime sets
"""

import unittest
import math
from resonagraph.core.phase_encoding import PhaseEncoder, PHI, TWO_PI


class TestPhaseEncoder(unittest.TestCase):
    """Test phase encoding functionality."""
    
    def test_default_taper_alpha(self):
        """Test that default taper_alpha is 0.1."""
        encoder = PhaseEncoder()
        self.assertEqual(encoder.taper_alpha, 0.1)
    
    def test_custom_taper_alpha(self):
        """Test custom taper_alpha value."""
        encoder = PhaseEncoder(taper_alpha=0.05)
        self.assertEqual(encoder.taper_alpha, 0.05)
    
    def test_taper_alpha_validation(self):
        """Test that taper_alpha is validated."""
        # Too low
        with self.assertRaises(ValueError):
            PhaseEncoder(taper_alpha=0.01)
        
        # Too high
        with self.assertRaises(ValueError):
            PhaseEncoder(taper_alpha=0.20)
    
    def test_payload_to_bytes(self):
        """Test payload serialization to bytes."""
        encoder = PhaseEncoder()
        
        payload = {"name": "Alice", "age": 30}
        result = encoder._payload_to_bytes(payload)
        
        # Should be bytes
        self.assertIsInstance(result, bytes)
        
        # Should be deterministic
        result2 = encoder._payload_to_bytes(payload)
        self.assertEqual(result, result2)
        
        # Should be consistent with sorted keys
        payload_reversed = {"age": 30, "name": "Alice"}
        result3 = encoder._payload_to_bytes(payload_reversed)
        self.assertEqual(result, result3)
    
    def test_chunk_into_symbols(self):
        """Test byte chunking into symbols."""
        encoder = PhaseEncoder()
        
        # Test even number of bytes
        data = b'\x01\x02\x03\x04'
        symbols = encoder._chunk_into_symbols(data, max_symbol_size=65536)
        self.assertEqual(len(symbols), 2)
        self.assertEqual(symbols[0], 0x0102)  # (1 << 8) | 2
        self.assertEqual(symbols[1], 0x0304)  # (3 << 8) | 4
        
        # Test odd number of bytes
        data = b'\x01\x02\x03'
        symbols = encoder._chunk_into_symbols(data, max_symbol_size=65536)
        self.assertEqual(len(symbols), 2)
        self.assertEqual(symbols[0], 0x0102)
        self.assertEqual(symbols[1], 0x0300)  # Last byte padded
    
    def test_compute_phase_angle_range(self):
        """Test that phase angles are in [0, 2π) range."""
        encoder = PhaseEncoder()
        phase_key = b'test_key_32_bytes_long_______'
        
        for symbol in [0, 100, 1000, 65535]:
            for prime in [2, 3, 5, 7, 11]:
                angle = encoder._compute_phase_angle(symbol, prime, 0, phase_key)
                self.assertGreaterEqual(angle, 0.0)
                self.assertLess(angle, TWO_PI)
    
    def test_compute_phase_angle_deterministic(self):
        """Test that phase angle computation is deterministic."""
        encoder = PhaseEncoder()
        phase_key = b'test_key_32_bytes_long_______'
        
        angle1 = encoder._compute_phase_angle(42, 7, 0, phase_key)
        angle2 = encoder._compute_phase_angle(42, 7, 0, phase_key)
        
        self.assertEqual(angle1, angle2)
    
    def test_compute_hmac_component(self):
        """Test HMAC component computation."""
        encoder = PhaseEncoder()
        phase_key = b'test_key_32_bytes_long_______'
        
        # Should return value in [0, 1)
        hmac_val = encoder._compute_hmac_component(7, 0, phase_key)
        self.assertGreaterEqual(hmac_val, 0.0)
        self.assertLess(hmac_val, 1.0)
        
        # Should be deterministic
        hmac_val2 = encoder._compute_hmac_component(7, 0, phase_key)
        self.assertEqual(hmac_val, hmac_val2)
        
        # Different inputs should give different values
        hmac_val3 = encoder._compute_hmac_component(11, 0, phase_key)
        self.assertNotEqual(hmac_val, hmac_val3)
    
    def test_encode_payload(self):
        """Test full payload encoding."""
        encoder = PhaseEncoder()
        phase_key = b'test_key_32_bytes_long_______'
        primes = [2, 3, 5, 7]
        
        payload = {"test": "data"}
        result = encoder.encode_payload(payload, primes, phase_key)
        
        # Should return dict with prime keys
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result.keys()), set(primes))
        
        # Each prime should have list of angles
        for prime in primes:
            self.assertIsInstance(result[prime], list)
            self.assertGreater(len(result[prime]), 0)
            
            # All angles should be in valid range
            for angle in result[prime]:
                self.assertGreaterEqual(angle, 0.0)
                self.assertLess(angle, TWO_PI)
    
    def test_chinese_remainder_theorem(self):
        """Test CRT implementation."""
        encoder = PhaseEncoder()
        
        # Simple test case: x ≡ 2 (mod 3), x ≡ 3 (mod 5), x ≡ 2 (mod 7)
        # Solution: x = 23 (mod 105)
        residues = [(2, 3), (3, 5), (2, 7)]
        result = encoder._chinese_remainder_theorem(residues)
        
        # Verify the result satisfies all congruences
        self.assertEqual(result % 3, 2)
        self.assertEqual(result % 5, 3)
        self.assertEqual(result % 7, 2)
    
    def test_mod_inverse(self):
        """Test modular inverse computation."""
        encoder = PhaseEncoder()
        
        # 3 * 5 ≡ 1 (mod 7)
        inv = encoder._mod_inverse(3, 7)
        self.assertEqual((3 * inv) % 7, 1)
        
        # 2 * 3 ≡ 1 (mod 5)
        inv = encoder._mod_inverse(2, 5)
        self.assertEqual((2 * inv) % 5, 1)
        
        # Test error case (no inverse exists)
        with self.assertRaises(ValueError):
            encoder._mod_inverse(2, 4)  # gcd(2, 4) = 2 != 1
    
    def test_symbols_to_bytes(self):
        """Test symbol to bytes conversion."""
        encoder = PhaseEncoder()
        
        # Test round-trip
        original = b'\x01\x02\x03\x04'
        symbols = encoder._chunk_into_symbols(original, 65536)
        recovered = encoder._symbols_to_bytes(symbols)
        
        # Should recover original bytes (or with minimal padding)
        self.assertTrue(recovered.startswith(original))
    
    def test_golden_ratio(self):
        """Test that PHI constant is correct."""
        expected_phi = (1 + math.sqrt(5)) / 2
        self.assertAlmostEqual(PHI, expected_phi, places=10)
    
    def test_two_pi(self):
        """Test that TWO_PI constant is correct."""
        expected_two_pi = 2 * math.pi
        self.assertAlmostEqual(TWO_PI, expected_two_pi, places=10)


if __name__ == '__main__':
    unittest.main()
