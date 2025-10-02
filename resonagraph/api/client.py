"""
Client SDK for ResonaGraph.

Implements the core operations from design.md Section 4.1:
- put(key, payload, phase_key, options)
- get(key, phase_key)
- traverse(start_key, pattern, phase_key)
- query(cypher_query, phase_key, params)
"""

from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives.asymmetric import ed25519

from resonagraph.core.phase_key import PhaseKey
from resonagraph.core.prime_selection import PrimeSelector
from resonagraph.core.phase_encoding import PhaseEncoder
from resonagraph.gossip import Beacon, GossipManager, KademliaDHT


class Client:
    """
    ResonaGraph client SDK.
    
    According to design.md Section 4.1:
    Core operations: put, get, traverse, query
    """
    
    def __init__(self, endpoint: str, enable_gossip: bool = False):
        """
        Initialize ResonaGraph client.
        
        Args:
            endpoint: API endpoint URL (e.g., "https://api.resonagraph.com/v1")
            enable_gossip: Enable local gossip manager (for testing/development)
        """
        self.endpoint = endpoint
        self._prime_selector = PrimeSelector()
        self._phase_encoder = PhaseEncoder()
        
        # Gossip plane (optional, for testing)
        self._gossip_manager: Optional[GossipManager] = None
        if enable_gossip:
            dht = KademliaDHT(address=endpoint)
            self._gossip_manager = GossipManager(dht, address=endpoint)
        
        # Signing key for beacons (would be configured in production)
        self._signing_key: Optional[ed25519.Ed25519PrivateKey] = None
    
    def put(
        self,
        key: str,
        payload: Dict[str, Any],
        phase_key: PhaseKey,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Write vertex/edge with encoding.
        
        According to design.md Section 4.1:
        - Options: k_primes (32-64), taper_alpha (0.05-0.15)
        - Returns beacon metadata
        
        Args:
            key: Vertex or edge key
            payload: Data to store
            phase_key: Cryptographic phase key
            options: Optional parameters (k_primes, taper_alpha)
            
        Returns:
            Beacon metadata dict
        """
        options = options or {}
        
        # Extract options
        k_primes = options.get('k_primes', PrimeSelector.DEFAULT_K_PRIMES)
        taper_alpha = options.get('taper_alpha', 0.1)  # DEFAULT_TAPER_ALPHA
        
        # Select primes for this key
        prime_selector = PrimeSelector(k_primes=k_primes)
        primes = prime_selector.select_primes(key)
        
        # Encode payload
        encoder = PhaseEncoder(taper_alpha=taper_alpha)
        phase_angles_dict = encoder.encode_payload(
            payload, primes, phase_key.get_bytes()
        )
        
        # Convert dict to flat list of phase angles for beacon
        phase_angles = []
        for prime in primes:
            if prime in phase_angles_dict:
                phase_angles.extend(phase_angles_dict[prime])
        
        # Create beacon (with signature if gossip enabled)
        beacon = Beacon(
            key=key,
            primes=primes,
            phase_angles=phase_angles,
            signing_key=self._signing_key,
            mac_key=phase_key.get_bytes()
        )
        
        # Publish beacon via gossip if enabled
        if self._gossip_manager:
            self._gossip_manager.publish_beacon(key, beacon)
        
        # Return beacon metadata
        return {
            'key': key,
            'primes': primes,
            'phase_angles': phase_angles_dict,  # Return original dict format
            'epoch': beacon.epoch,
            'phase_fingerprint': beacon.phase_fingerprint,
            'beacon_size': beacon.size(),
            'options': {
                'k_primes': k_primes,
                'taper_alpha': taper_alpha
            }
        }
    
    def get(
        self,
        key: str,
        phase_key: PhaseKey
    ) -> Dict[str, Any]:
        """
        Retrieve by resonance locking.
        
        According to design.md Section 4.1:
        Returns payload + metrics (lock_time, entropy_final)
        
        Args:
            key: Key to retrieve
            phase_key: Cryptographic phase key
            
        Returns:
            Dict with payload and metrics
        """
        # If gossip enabled, try to fetch beacon
        if self._gossip_manager:
            # Select primes for this key (same as in put)
            primes = self._prime_selector.select_primes(key)
            
            # Query beacon from gossip manager
            beacon = self._gossip_manager.query_beacon(primes)
            
            if beacon:
                return {
                    'payload': {},  # Would reconstruct via CRT in Phase 3
                    'beacon_found': True,
                    'epoch': beacon.epoch,
                    'phase_fingerprint': beacon.phase_fingerprint,
                    'metrics': {
                        'lock_time': 0.0,
                        'entropy_final': 0.0
                    }
                }
        
        # In a full implementation, this would:
        # 1. Fetch beacons for key's primes
        # 2. Synthesize probe |Q⟩
        # 3. Perform resonance locking
        # 4. Extract residues
        # 5. Reconstruct via CRT
        
        # Placeholder implementation
        return {
            'payload': {},
            'beacon_found': False,
            'metrics': {
                'lock_time': 0.0,
                'entropy_final': 0.0
            }
        }
    
    def traverse(
        self,
        start_key: str,
        pattern: str,
        phase_key: PhaseKey
    ) -> List[Dict[str, Any]]:
        """
        Graph traversal with coherence bias.
        
        According to copilot-instructions.md Section 4:
        Uses Hamiltonian H_G bias for efficient locks
        
        Args:
            start_key: Starting vertex key
            pattern: Traversal pattern
            phase_key: Cryptographic phase key
            
        Returns:
            List of matching vertices/edges
        """
        # In a full implementation, this would:
        # 1. Start from start_key
        # 2. Apply coherence bias using H_G
        # 3. Traverse edges according to pattern
        
        # Placeholder implementation
        return []
    
    def query(
        self,
        query_obj: Any,  # Will be Query object
        phase_key: PhaseKey,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Cypher-like query.
        
        According to design.md Section 4.1:
        Supports Cypher subset + resonance extensions
        
        Args:
            query_obj: Query object with Cypher string
            phase_key: Cryptographic phase key
            params: Query parameters
            
        Returns:
            Dict with nodes, edges, and metrics
        """
        params = params or {}
        
        # In a full implementation, this would:
        # 1. Parse Cypher query
        # 2. Plan execution with coherence hints
        # 3. Execute traversal
        # 4. Return results with metrics
        
        # Placeholder implementation
        return {
            'nodes': [],
            'edges': [],
            'metrics': {
                'lock_time': 0.0,
                'entropy_final': 0.0
            }
        }
