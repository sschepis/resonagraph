"""
Prime selection module implementing Eratosthenes sieve for ResonaGraph.

This module handles prime selection for encoding graph elements. According to 
design.md Section 3.2, we select k=32-64 primes in the range 2 to 10^12.
"""

import hashlib
import math
from typing import List, Optional


class PrimeSelector:
    """
    Selects primes for encoding using Eratosthenes sieve.
    
    According to design.md Section 3.2:
    - Hash key seeds the sieve
    - Select k=32-64 primes 
    - Range: 2 to 10^12 for collision resistance
    """
    
    # Default parameters from copilot-instructions.md
    DEFAULT_K_PRIMES = 32
    MIN_K_PRIMES = 32
    MAX_K_PRIMES = 64
    MIN_PRIME = 2
    MAX_PRIME = 10**12
    
    def __init__(self, k_primes: int = DEFAULT_K_PRIMES):
        """
        Initialize the prime selector.
        
        Args:
            k_primes: Number of primes to select (32-64)
        """
        if not (self.MIN_K_PRIMES <= k_primes <= self.MAX_K_PRIMES):
            raise ValueError(
                f"k_primes must be between {self.MIN_K_PRIMES} and {self.MAX_K_PRIMES}"
            )
        self.k_primes = k_primes
        # Cache for commonly used small primes
        self._small_primes_cache: Optional[List[int]] = None
    
    def select_primes(self, key: str) -> List[int]:
        """
        Select k primes for a given key using seeded Eratosthenes sieve.
        
        Process (design.md Section 3.2):
        1. H(key) seeds the sieve
        2. Use Eratosthenes algorithm to generate primes
        3. Select k primes from the range
        
        Args:
            key: The key string to hash and seed prime selection
            
        Returns:
            List of k prime numbers
        """
        # Hash the key to get a deterministic seed
        key_hash = hashlib.sha256(key.encode()).digest()
        seed = int.from_bytes(key_hash[:8], byteorder='big')
        
        # For practical purposes, we'll use a strategic selection:
        # - Mix of small primes for efficiency
        # - Larger primes for collision resistance
        # - Deterministic based on seed
        
        primes = self._generate_primes_with_seed(seed)
        return primes[:self.k_primes]
    
    def _generate_primes_with_seed(self, seed: int) -> List[int]:
        """
        Generate primes using Eratosthenes sieve with deterministic seed-based selection.
        
        Strategy:
        - Generate small primes efficiently (2 to 10000)
        - Use larger strategic primes for collision resistance
        - Deterministically select based on seed
        """
        # Start with small primes using classic Eratosthenes
        small_limit = 10000
        small_primes = self._sieve_of_eratosthenes(small_limit)
        
        # For larger primes, we'll use a deterministic selection
        # based on the seed to pick from known ranges
        large_prime_ranges = [
            (10007, 20000),
            (100003, 110000),
            (1000003, 1010000),
            (10000019, 10010000),
        ]
        
        all_primes = list(small_primes)
        
        # Add larger primes deterministically based on seed
        for start, end in large_prime_ranges:
            range_primes = self._primes_in_range(start, end)
            # Use seed to deterministically pick primes from this range
            step = max(1, (seed % len(range_primes)) + 1)
            selected = [range_primes[i] for i in range(0, len(range_primes), step)]
            all_primes.extend(selected[:5])  # Take a few from each range
        
        # Shuffle deterministically based on seed
        return self._deterministic_shuffle(all_primes, seed)
    
    def _sieve_of_eratosthenes(self, limit: int) -> List[int]:
        """
        Classic Eratosthenes sieve for generating primes up to limit.
        
        Args:
            limit: Upper bound for prime generation
            
        Returns:
            List of all primes up to limit
        """
        if limit < 2:
            return []
        
        # Create a boolean array and initialize all entries as true
        is_prime = [True] * (limit + 1)
        is_prime[0] = is_prime[1] = False
        
        # Start with 2
        p = 2
        while p * p <= limit:
            # If is_prime[p] is not changed, then it's a prime
            if is_prime[p]:
                # Mark all multiples of p as not prime
                for i in range(p * p, limit + 1, p):
                    is_prime[i] = False
            p += 1
        
        # Collect all prime numbers
        primes = [i for i in range(2, limit + 1) if is_prime[i]]
        return primes
    
    def _primes_in_range(self, start: int, end: int) -> List[int]:
        """
        Find primes in a given range using trial division.
        
        For large ranges, this is more efficient than full sieve.
        """
        primes = []
        for n in range(start, end):
            if self._is_prime(n):
                primes.append(n)
                if len(primes) >= 20:  # Limit per range for efficiency
                    break
        return primes
    
    def _is_prime(self, n: int) -> bool:
        """Check if a number is prime using trial division."""
        if n < 2:
            return False
        if n == 2:
            return True
        if n % 2 == 0:
            return False
        
        # Check odd divisors up to sqrt(n)
        sqrt_n = int(math.sqrt(n))
        for i in range(3, sqrt_n + 1, 2):
            if n % i == 0:
                return False
        return True
    
    def _deterministic_shuffle(self, items: List[int], seed: int) -> List[int]:
        """
        Deterministically shuffle items based on seed.
        
        Uses a simple linear congruential generator for reproducibility.
        """
        result = items.copy()
        n = len(result)
        
        # LCG parameters
        a = 1664525
        c = 1013904223
        m = 2**32
        
        state = seed % m
        
        # Fisher-Yates shuffle with deterministic RNG
        for i in range(n - 1, 0, -1):
            state = (a * state + c) % m
            j = state % (i + 1)
            result[i], result[j] = result[j], result[i]
        
        return result
    
    def verify_product_bound(self, primes: List[int], byte_size: int) -> bool:
        """
        Verify that product of primes satisfies ∏ p_i ≥ 2^{8b} for CRT.
        
        According to copilot-instructions.md Section 2.2.2:
        - Product must be large enough for b-byte symbols
        
        Args:
            primes: List of prime numbers
            byte_size: Size in bytes of symbols to encode
            
        Returns:
            True if product is large enough
        """
        product = 1
        for p in primes:
            product *= p
            # Early exit if we've already satisfied the bound
            if product >= 2 ** (8 * byte_size):
                return True
        
        return product >= 2 ** (8 * byte_size)
