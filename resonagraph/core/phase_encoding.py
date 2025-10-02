"""
Phase encoding module implementing the phase coding formalism.

According to design.md Section 3.2 and copilot-instructions.md:
- Phase Coding: θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
- Golden ratio φ = (1+√5)/2
- Taper alpha for weighted probes (default α=0.1)
"""

import hashlib
import hmac
import math
from typing import List, Dict, Any, Optional
import json


# Mathematical constants
PHI = (1 + math.sqrt(5)) / 2  # Golden ratio
TWO_PI = 2 * math.pi

# Default parameters from copilot-instructions.md
DEFAULT_TAPER_ALPHA = 0.1
MIN_TAPER_ALPHA = 0.05
MAX_TAPER_ALPHA = 0.15


class PhaseEncoder:
    """
    Encodes graph data into phase angles for resonance-based storage.
    
    Implements the phase coding formalism from design.md Section 3.2:
    θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
    
    Where:
    - m_j: Symbol (byte chunk) from payload
    - p: Prime from selected set
    - α: Taper parameter for weighted probes
    - φ: Golden ratio (1+√5)/2
    - β, δ: Additional distribution parameters
    - HMAC: Cryptographic MAC for access control
    - K: Phase key
    """
    
    def __init__(self, taper_alpha: float = DEFAULT_TAPER_ALPHA):
        """
        Initialize the phase encoder.
        
        Args:
            taper_alpha: Taper parameter for weighted probes (0.05-0.15)
        """
        if not (MIN_TAPER_ALPHA <= taper_alpha <= MAX_TAPER_ALPHA):
            raise ValueError(
                f"taper_alpha must be between {MIN_TAPER_ALPHA} and {MAX_TAPER_ALPHA}"
            )
        self.taper_alpha = taper_alpha
    
    def encode_payload(
        self,
        payload: Dict[str, Any],
        primes: List[int],
        phase_key: bytes,
        max_symbol_size: int = 65536  # M = 2^16
    ) -> Dict[int, List[float]]:
        """
        Encode a payload into phase angles for each prime.
        
        Args:
            payload: Dictionary payload to encode
            primes: List of prime numbers to use
            phase_key: Cryptographic key for HMAC
            max_symbol_size: Maximum symbol value (M=2^16 default)
            
        Returns:
            Dictionary mapping each prime to list of phase angles
        """
        # Convert payload to bytes
        payload_bytes = self._payload_to_bytes(payload)
        
        # Chunk into symbols m_j ≤ M
        symbols = self._chunk_into_symbols(payload_bytes, max_symbol_size)
        
        # Encode each symbol for each prime
        phase_angles = {}
        for prime in primes:
            angles = []
            for j, symbol in enumerate(symbols):
                theta_p = self._compute_phase_angle(
                    symbol, prime, j, phase_key
                )
                angles.append(theta_p)
            phase_angles[prime] = angles
        
        return phase_angles
    
    def _payload_to_bytes(self, payload: Dict[str, Any]) -> bytes:
        """
        Convert a payload dictionary to bytes.
        
        Uses JSON serialization for consistent byte representation.
        """
        # Serialize to JSON with sorted keys for determinism
        json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return json_str.encode('utf-8')
    
    def _chunk_into_symbols(self, data: bytes, max_symbol_size: int) -> List[int]:
        """
        Chunk byte data into symbols m_j ≤ M.
        
        According to design.md Section 3.1:
        - Properties chunked into symbols m_j ≤ M=2^16
        
        We'll use 2-byte chunks for M=2^16.
        """
        symbols = []
        
        # Process as 2-byte chunks
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                # Full 2-byte symbol
                symbol = (data[i] << 8) | data[i + 1]
            else:
                # Last byte, pad with zero
                symbol = data[i] << 8
            
            symbols.append(symbol)
        
        return symbols
    
    def _compute_phase_angle(
        self,
        symbol: int,
        prime: int,
        symbol_index: int,
        phase_key: bytes
    ) -> float:
        """
        Compute phase angle θ_p for a symbol.
        
        Formula from design.md Section 3.2:
        θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))
        
        Where:
        - m_j: symbol value
        - p: prime
        - α: taper_alpha
        - φ: golden ratio
        - β, δ: additional distribution parameters (using simple defaults)
        - HMAC: cryptographic MAC
        """
        # Base modular component
        mod_component = symbol % prime
        
        # Taper component: α/φ
        taper_component = self.taper_alpha / PHI
        
        # Distribution components β/δ (using simple values)
        # β represents phase offset, δ represents scale
        # We'll use symbol_index for β and prime for δ for distribution
        beta = symbol_index
        delta = prime
        distribution_component = beta / delta if delta != 0 else 0
        
        # HMAC component for cryptographic binding
        hmac_component = self._compute_hmac_component(
            prime, symbol_index, phase_key
        )
        
        # Combine all components and wrap to [0, 2π)
        phase = TWO_PI * (
            mod_component + 
            taper_component + 
            distribution_component + 
            hmac_component
        )
        
        # Normalize to [0, 2π)
        phase = phase % TWO_PI
        
        return phase
    
    def _compute_hmac_component(
        self,
        prime: int,
        symbol_index: int,
        phase_key: bytes
    ) -> float:
        """
        Compute HMAC component for phase angle.
        
        According to design.md Section 3.2:
        HMAC(p||j, K) where || is concatenation
        
        Returns a normalized value in [0, 1) for phase computation.
        """
        # Concatenate prime and index
        message = f"{prime}||{symbol_index}".encode('utf-8')
        
        # Compute HMAC-SHA256
        mac = hmac.new(phase_key, message, hashlib.sha256).digest()
        
        # Convert first 8 bytes to float in [0, 1)
        mac_int = int.from_bytes(mac[:8], byteorder='big')
        mac_float = mac_int / (2**64)
        
        return mac_float
    
    def decode_from_residues(
        self,
        residues: Dict[int, int],
        num_symbols: int
    ) -> bytes:
        """
        Decode symbols from residues using Chinese Remainder Theorem.
        
        According to copilot-instructions.md Section 2.2.2:
        - Extract residues r_j ≡ m_j mod p_i
        - Use CRT to reconstruct m_j
        
        Args:
            residues: Dict mapping primes to residue values
            num_symbols: Number of symbols to reconstruct
            
        Returns:
            Decoded byte data
        """
        # For each symbol position, apply CRT
        symbols = []
        
        for j in range(num_symbols):
            # Get residues for this symbol from all primes
            symbol_residues = []
            primes = list(residues.keys())
            
            for prime in primes:
                # In practice, we'd extract the residue for symbol j
                # For now, using the residue value directly
                symbol_residues.append((residues[prime], prime))
            
            # Apply CRT to get original symbol
            symbol = self._chinese_remainder_theorem(symbol_residues)
            symbols.append(symbol)
        
        # Convert symbols back to bytes
        return self._symbols_to_bytes(symbols)
    
    def _chinese_remainder_theorem(
        self,
        residues: List[tuple[int, int]]
    ) -> int:
        """
        Solve system of congruences using CRT.
        
        Given: x ≡ a_i (mod n_i) for i = 1, 2, ..., k
        Find: x
        
        Args:
            residues: List of (remainder, modulus) tuples
            
        Returns:
            Solution x
        """
        if not residues:
            return 0
        
        # Calculate product of all moduli
        N = 1
        for _, n_i in residues:
            N *= n_i
        
        # Apply CRT formula
        x = 0
        for a_i, n_i in residues:
            N_i = N // n_i
            # Find modular inverse of N_i mod n_i
            M_i = self._mod_inverse(N_i, n_i)
            x += a_i * N_i * M_i
        
        return x % N
    
    def _mod_inverse(self, a: int, m: int) -> int:
        """
        Compute modular multiplicative inverse of a modulo m.
        
        Uses extended Euclidean algorithm.
        """
        def extended_gcd(a: int, b: int) -> tuple[int, int, int]:
            if a == 0:
                return b, 0, 1
            gcd, x1, y1 = extended_gcd(b % a, a)
            x = y1 - (b // a) * x1
            y = x1
            return gcd, x, y
        
        gcd, x, _ = extended_gcd(a % m, m)
        if gcd != 1:
            raise ValueError("Modular inverse does not exist")
        return (x % m + m) % m
    
    def _symbols_to_bytes(self, symbols: List[int]) -> bytes:
        """
        Convert symbols back to bytes.
        
        Reverses the chunking process.
        """
        byte_array = bytearray()
        
        for symbol in symbols:
            # Extract 2 bytes from symbol
            high_byte = (symbol >> 8) & 0xFF
            low_byte = symbol & 0xFF
            byte_array.append(high_byte)
            if low_byte != 0 or symbol > 255:  # Don't add trailing zero padding
                byte_array.append(low_byte)
        
        return bytes(byte_array)
