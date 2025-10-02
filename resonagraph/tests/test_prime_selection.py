"""
Tests for prime selection module.

According to copilot-instructions.md Section 7:
- Mock Resonance: Use fixed primes for deterministic tests
- Unit Testing: Verify calculations match specifications
"""

import unittest
from resonagraph.core.prime_selection import PrimeSelector


class TestPrimeSelector(unittest.TestCase):
    """Test prime selection functionality."""
    
    def test_default_k_primes(self):
        """Test that default k_primes is 32."""
        selector = PrimeSelector()
        self.assertEqual(selector.k_primes, 32)
    
    def test_custom_k_primes(self):
        """Test custom k_primes value."""
        selector = PrimeSelector(k_primes=48)
        self.assertEqual(selector.k_primes, 48)
    
    def test_k_primes_validation(self):
        """Test that k_primes is validated."""
        # Too low
        with self.assertRaises(ValueError):
            PrimeSelector(k_primes=10)
        
        # Too high
        with self.assertRaises(ValueError):
            PrimeSelector(k_primes=100)
    
    def test_select_primes_deterministic(self):
        """Test that prime selection is deterministic for same key."""
        selector = PrimeSelector(k_primes=32)
        
        primes1 = selector.select_primes("test_key_123")
        primes2 = selector.select_primes("test_key_123")
        
        self.assertEqual(primes1, primes2)
    
    def test_select_primes_different_keys(self):
        """Test that different keys produce different prime sets."""
        selector = PrimeSelector(k_primes=32)
        
        primes1 = selector.select_primes("key_1")
        primes2 = selector.select_primes("key_2")
        
        # Should be different (though theoretically could collide)
        self.assertNotEqual(primes1, primes2)
    
    def test_select_primes_count(self):
        """Test that correct number of primes is selected."""
        for k in [32, 48, 64]:
            selector = PrimeSelector(k_primes=k)
            primes = selector.select_primes("test_key")
            self.assertEqual(len(primes), k)
    
    def test_all_selected_are_prime(self):
        """Test that all selected values are actually prime."""
        selector = PrimeSelector(k_primes=32)
        primes = selector.select_primes("test_key")
        
        for p in primes:
            self.assertTrue(selector._is_prime(p), f"{p} is not prime")
    
    def test_sieve_of_eratosthenes(self):
        """Test Eratosthenes sieve generates correct primes."""
        selector = PrimeSelector()
        
        # Test small range
        primes = selector._sieve_of_eratosthenes(20)
        expected = [2, 3, 5, 7, 11, 13, 17, 19]
        self.assertEqual(primes, expected)
        
        # Test edge cases
        self.assertEqual(selector._sieve_of_eratosthenes(1), [])
        self.assertEqual(selector._sieve_of_eratosthenes(2), [2])
    
    def test_is_prime(self):
        """Test prime checking function."""
        selector = PrimeSelector()
        
        # Known primes
        self.assertTrue(selector._is_prime(2))
        self.assertTrue(selector._is_prime(3))
        self.assertTrue(selector._is_prime(5))
        self.assertTrue(selector._is_prime(7))
        self.assertTrue(selector._is_prime(11))
        self.assertTrue(selector._is_prime(97))
        
        # Non-primes
        self.assertFalse(selector._is_prime(0))
        self.assertFalse(selector._is_prime(1))
        self.assertFalse(selector._is_prime(4))
        self.assertFalse(selector._is_prime(6))
        self.assertFalse(selector._is_prime(8))
        self.assertFalse(selector._is_prime(9))
        self.assertFalse(selector._is_prime(100))
    
    def test_verify_product_bound(self):
        """Test product bound verification for CRT."""
        selector = PrimeSelector()
        
        # Small primes should satisfy bound for small byte_size
        small_primes = [2, 3, 5, 7, 11, 13]
        self.assertTrue(selector.verify_product_bound(small_primes, 1))
        
        # Product of 2*3*5*7*11*13 = 30030 > 2^8 = 256
        self.assertTrue(selector.verify_product_bound(small_primes, 1))
        
        # But not for large byte_size
        self.assertFalse(selector.verify_product_bound(small_primes, 100))
    
    def test_deterministic_shuffle(self):
        """Test that shuffle is deterministic."""
        selector = PrimeSelector()
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        # Same seed should produce same result
        result1 = selector._deterministic_shuffle(items, seed=12345)
        result2 = selector._deterministic_shuffle(items, seed=12345)
        self.assertEqual(result1, result2)
        
        # Different seed should produce different result
        result3 = selector._deterministic_shuffle(items, seed=54321)
        self.assertNotEqual(result1, result3)
        
        # Should contain all original items
        self.assertEqual(sorted(result1), sorted(items))


if __name__ == '__main__':
    unittest.main()
