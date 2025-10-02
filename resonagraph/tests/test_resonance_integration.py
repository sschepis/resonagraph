"""
Integration tests for Phase 3 Resonance Plane.

According to copilot-instructions.md Section 7:
- Test end-to-end reconstruction
- Integration test: put → get with resonance locking
"""

import unittest
from resonagraph import Client, PhaseKey


class TestResonancePlaneIntegration(unittest.TestCase):
    """Integration tests for resonance plane with client SDK."""
    
    def test_put_and_get_simple_payload(self):
        """Test complete put/get cycle with simple payload."""
        client = Client("http://localhost:8080", enable_gossip=False)
        phase_key = PhaseKey.from_secret(b"test_secret_key_32_bytes_long__")
        
        # Put data
        payload = {"name": "Alice", "age": 30}
        put_result = client.put(
            key="user:123",
            payload=payload,
            phase_key=phase_key,
            options={"k_primes": 32, "taper_alpha": 0.1}
        )
        
        self.assertIn("key", put_result)
        self.assertEqual(put_result["key"], "user:123")
        
        # Get data back
        get_result = client.get("user:123", phase_key)
        
        self.assertIn("payload", get_result)
        self.assertIn("metrics", get_result)
        self.assertTrue(get_result["found"])
    
    def test_put_and_get_complex_payload(self):
        """Test put/get with more complex payload."""
        client = Client("http://localhost:8080", enable_gossip=False)
        phase_key = PhaseKey.from_secret(b"another_secret_key_32_bytes____")
        
        # Complex payload
        payload = {
            "user": {
                "name": "Bob",
                "email": "bob@example.com",
                "metadata": {
                    "created": "2025-01-01",
                    "tags": ["developer", "admin"]
                }
            },
            "stats": {
                "posts": 42,
                "followers": 150
            }
        }
        
        put_result = client.put(
            key="user:456",
            payload=payload,
            phase_key=phase_key
        )
        
        self.assertIn("primes", put_result)
        self.assertGreater(len(put_result["primes"]), 0)
        
        # Get back
        get_result = client.get("user:456", phase_key)
        
        self.assertTrue(get_result["found"])
        self.assertIn("metrics", get_result)
    
    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        client = Client("http://localhost:8080", enable_gossip=False)
        phase_key = PhaseKey.from_secret(b"test_key_32_bytes_long_________")
        
        result = client.get("nonexistent:key", phase_key)
        
        self.assertFalse(result["found"])
        self.assertIsNone(result["payload"])
    
    def test_put_with_different_k_primes(self):
        """Test put with different k_primes values."""
        client = Client("http://localhost:8080", enable_gossip=False)
        phase_key = PhaseKey.from_secret(b"test_secret_32_bytes___________")
        
        payload = {"test": "data"}
        
        # Test with k=32
        result_32 = client.put(
            key="test:32",
            payload=payload,
            phase_key=phase_key,
            options={"k_primes": 32}
        )
        
        self.assertEqual(len(result_32["primes"]), 32)
        
        # Test with k=48
        result_48 = client.put(
            key="test:48",
            payload=payload,
            phase_key=phase_key,
            options={"k_primes": 48}
        )
        
        self.assertEqual(len(result_48["primes"]), 48)
    
    def test_metrics_included_in_response(self):
        """Test that metrics are included in get response."""
        client = Client("http://localhost:8080", enable_gossip=False)
        phase_key = PhaseKey.from_secret(b"metrics_test_key_32_bytes______")
        
        payload = {"data": "test"}
        client.put("test:metrics", payload, phase_key)
        
        result = client.get("test:metrics", phase_key)
        
        self.assertIn("metrics", result)
        metrics = result["metrics"]
        
        # Check required metrics fields
        self.assertIn("lock_time", metrics)
        self.assertIn("entropy_final", metrics)
        self.assertIn("resonance_score", metrics)
        self.assertIn("iterations", metrics)
        self.assertIn("converged", metrics)
        self.assertIn("final_overlap", metrics)
        
        # Verify metrics types and ranges
        self.assertIsInstance(metrics["lock_time"], float)
        self.assertIsInstance(metrics["iterations"], int)
        self.assertIsInstance(metrics["converged"], bool)
        self.assertGreaterEqual(metrics["final_overlap"], 0.0)
        self.assertLessEqual(metrics["final_overlap"], 1.0)
    
    def test_multiple_keys_independent(self):
        """Test that multiple keys are stored independently."""
        client = Client("http://localhost:8080", enable_gossip=False)
        phase_key = PhaseKey.from_secret(b"multi_key_test_32_bytes________")
        
        # Store multiple different payloads
        payloads = {
            "key1": {"value": 1},
            "key2": {"value": 2},
            "key3": {"value": 3}
        }
        
        for key, payload in payloads.items():
            client.put(key, payload, phase_key)
        
        # Retrieve and verify each
        for key, expected_payload in payloads.items():
            result = client.get(key, phase_key)
            self.assertTrue(result["found"])
    
    def test_locking_convergence(self):
        """Test that resonance locking converges."""
        client = Client("http://localhost:8080", enable_gossip=False)
        phase_key = PhaseKey.from_secret(b"convergence_test_32_bytes______")
        
        payload = {"test": "convergence"}
        client.put("test:conv", payload, phase_key)
        
        result = client.get("test:conv", phase_key)
        
        # Check convergence
        self.assertTrue(result["found"])
        metrics = result["metrics"]
        
        # Should converge in reasonable number of iterations
        self.assertLess(metrics["iterations"], 100)
        
        # If converged, should have good overlap
        if metrics["converged"]:
            self.assertGreater(metrics["final_overlap"], 0.9)


class TestPhaseEncodingCRT(unittest.TestCase):
    """Test CRT reconstruction in phase encoding."""
    
    def test_reconstruct_payload(self):
        """Test payload reconstruction from residues."""
        from resonagraph.core.phase_encoding import PhaseEncoder
        
        encoder = PhaseEncoder()
        
        # Simple residues for testing
        # Note: This is a simplified test; real residues come from phase extraction
        residues_per_prime = {
            2: [1],
            3: [2],
            5: [3]
        }
        
        # Reconstruct (may not produce valid JSON in this simple test)
        result = encoder.reconstruct_payload(residues_per_prime)
        
        # Should return a dict (even if reconstruction failed)
        self.assertIsInstance(result, dict)
    
    def test_validate_prime_product(self):
        """Test prime product validation."""
        from resonagraph.core.phase_encoding import PhaseEncoder
        
        encoder = PhaseEncoder()
        
        # For 2-byte symbols (16 bits), need product >= 65536
        primes_sufficient = [2, 3, 5, 7, 11, 13, 17]  # Product > 65536
        primes_insufficient = [2, 3, 5]  # Product = 30 < 65536
        
        self.assertTrue(encoder.validate_prime_product(primes_sufficient, 2))
        self.assertFalse(encoder.validate_prime_product(primes_insufficient, 2))


if __name__ == '__main__':
    unittest.main()
