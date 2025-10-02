"""
Client SDK for ResonaGraph.

Implements the core operations from design.md Section 4.1:
- put(key, payload, phase_key, options)
- get(key, phase_key) with Phase 4 REC conflict resolution
- traverse(start_key, pattern, phase_key)
- query(cypher_query, phase_key, params)
"""

from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives.asymmetric import ed25519

from resonagraph.core.phase_key import PhaseKey
from resonagraph.core.prime_selection import PrimeSelector
from resonagraph.core.phase_encoding import PhaseEncoder
from resonagraph.gossip import Beacon, GossipManager, KademliaDHT
from resonagraph.resonance import (
    ProbeSynthesizer, ResonanceLock, ResidueExtractor,
    RECSimulator, ConflictCandidate
)


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
        
        # Resonance plane components (Phase 3)
        self._probe_synthesizer = ProbeSynthesizer()
        self._resonance_lock = ResonanceLock()
        self._residue_extractor = ResidueExtractor()
        
        # REC conflict resolution (Phase 4)
        self._rec_simulator = RECSimulator()
        
        # Gossip plane (optional, for testing)
        self._gossip_manager: Optional[GossipManager] = None
        if enable_gossip:
            dht = KademliaDHT(address=endpoint)
            self._gossip_manager = GossipManager(dht, address=endpoint)
        
        # Signing key for beacons (would be configured in production)
        self._signing_key: Optional[ed25519.Ed25519PrivateKey] = None
        
        # Local storage for encoded data (simulated)
        # In production, this would be RocksDB
        # Format: {key: {epoch: {prime: [phases]}}}
        self._storage: Dict[str, Dict[float, Dict[int, List[float]]]] = {}
    
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
        
        # Store phases locally for later retrieval (simulated storage)
        # Store with epoch timestamp for REC conflict detection
        if key not in self._storage:
            self._storage[key] = {}
        self._storage[key][beacon.epoch] = phase_angles_dict
        
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
        phase_key: PhaseKey,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve by resonance locking with REC conflict resolution.
        
        According to design.md Section 4.1 and Section 2.3 (Algo 2):
        1. Hash key → Select P(a)
        2. Fetch beacons (or use local storage)
        3. Detect conflicts (multiple epochs)
        4. If conflict, use REC to resolve
        5. Synthesize probe |Q⟩
        6. Perform resonance locking
        7. Extract residues
        8. Reconstruct via CRT
        
        Phase 4 REC integration according to copilot-instructions.md:
        - Detect Conflict: Multiple epochs indicate fork
        - Simulate Dynamics: For each candidate epoch
        - Select Winner: min(S_stable) AND max(RS_stable)
        
        Returns payload + metrics (lock_time, entropy_final)
        
        Args:
            key: Key to retrieve
            phase_key: Cryptographic phase key
            options: Optional parameters (k_primes, taper_alpha)
            
        Returns:
            Dict with payload and metrics (including REC info if conflict)
        """
        options = options or {}
        k_primes = options.get('k_primes', PrimeSelector.DEFAULT_K_PRIMES)
        taper_alpha = options.get('taper_alpha', 0.1)
        
        # Step 1: Select primes for this key
        prime_selector = PrimeSelector(k_primes=k_primes)
        primes = prime_selector.select_primes(key)
        
        # Step 2: Fetch address phases (from local storage or beacon)
        # Returns dict: {epoch: {prime: [phases]}}
        epoch_phases_map = self._fetch_all_epochs(key, primes)
        
        if not epoch_phases_map:
            return {
                'payload': None,
                'found': False,
                'conflict_resolved': False,
                'metrics': {
                    'lock_time': 0.0,
                    'entropy_final': 0.0
                }
            }
        
        # Step 3: Detect conflicts (multiple epochs)
        epochs = list(epoch_phases_map.keys())
        address_phases = None
        rec_info = None
        
        if len(epochs) > 1:
            # Conflict detected! Use REC to resolve
            rec_info, address_phases = self._resolve_conflict(
                key, epoch_phases_map, primes, phase_key
            )
        else:
            # No conflict, use the single epoch
            address_phases = epoch_phases_map[epochs[0]]
        
        # Step 4: Synthesize probe |Q⟩
        # Initial probe phases are arbitrary (could be random or zero)
        import random
        import math
        initial_phases = [random.random() * 2 * math.pi for _ in primes]
        
        probe_synthesizer = ProbeSynthesizer(taper_alpha=taper_alpha)
        probe = probe_synthesizer.synthesize_probe(
            primes, initial_phases, use_tapered=True
        )
        
        # Step 5: Perform resonance locking
        locked_probe, lock_metrics = self._resonance_lock.lock(
            probe, address_phases, learning_rate=0.1
        )
        
        # Step 6: Extract residues
        residues = self._residue_extractor.extract_all_residues(
            locked_probe, address_phases
        )
        
        # Step 7: Reconstruct payload via CRT
        payload = self._phase_encoder.reconstruct_payload(residues)
        
        # Return with metrics (including REC info if conflict was resolved)
        result = {
            'payload': payload,
            'found': True,
            'metrics': {
                'lock_time': lock_metrics.lock_time,
                'entropy_final': lock_metrics.final_entropy,
                'resonance_score': lock_metrics.final_resonance_score,
                'iterations': lock_metrics.iterations,
                'converged': lock_metrics.converged,
                'final_overlap': lock_metrics.final_overlap
            }
        }
        
        # Add REC info if conflict was resolved
        if rec_info:
            result['conflict_resolved'] = True
            result['rec_info'] = rec_info
        else:
            result['conflict_resolved'] = False
        
        return result
    
    def _fetch_all_epochs(
        self,
        key: str,
        primes: List[int]
    ) -> Dict[float, Dict[int, List[float]]]:
        """
        Fetch all epochs for a key (for conflict detection).
        
        Returns dict mapping epoch -> prime phases.
        In production, this would query RocksDB or fetch from beacons.
        
        Args:
            key: Key to fetch
            primes: Primes to fetch phases for
            
        Returns:
            Dict mapping epochs to phase dicts {epoch: {prime: [phases]}}
        """
        # Try local storage first
        if key in self._storage:
            return self._storage[key]
        
        # Try gossip plane if enabled
        if self._gossip_manager:
            # Would fetch all beacons for this key from gossip plane
            # For now, return empty
            return {}
        
        return {}
    
    def _resolve_conflict(
        self,
        key: str,
        epoch_phases_map: Dict[float, Dict[int, List[float]]],
        primes: List[int],
        phase_key: PhaseKey
    ) -> tuple[Dict[str, Any], Dict[int, List[float]]]:
        """
        Resolve conflict using REC thermodynamic selection.
        
        According to copilot-instructions.md Phase 4:
        1. Create ConflictCandidate for each epoch
        2. Simulate thermodynamic dynamics
        3. Select winner based on min(S_stable) AND max(RS_stable)
        4. Return winner's phases
        
        Args:
            key: Key being retrieved
            epoch_phases_map: Map of epochs to phase dicts
            primes: Prime list for this key
            phase_key: Phase key for access
            
        Returns:
            (rec_info, winning_phases) tuple
        """
        # Create conflict candidates
        candidates = []
        for epoch, phase_dict in epoch_phases_map.items():
            # Estimate initial entropy from payload complexity
            # More primes or phases → potentially higher initial entropy
            total_phases = sum(len(phases) for phases in phase_dict.values())
            s_0 = 1.0 + (total_phases / 1000.0)  # Heuristic based on size
            
            # Estimate initial resonance score from phase distribution
            # More varied phases → lower initial overlap
            rs_0 = 0.05 + (0.05 * (len(primes) / 32))  # Normalized by typical k_primes
            
            # Lambda and gamma depend on prime count (more primes → faster dynamics)
            lambda_decay = 0.5 + (len(primes) / 64) * 0.5  # Scale from 0.5 to 1.0
            gamma_growth = 0.4 + (len(primes) / 64) * 0.4  # Scale from 0.4 to 0.8
            
            candidate = ConflictCandidate(
                epoch=epoch,
                s_0=s_0,
                rs_0=rs_0,
                lambda_decay=lambda_decay,
                gamma_growth=gamma_growth,
                rs_star=0.98,  # Conservative target
                beacon_data={'phase_dict': phase_dict}
            )
            candidates.append(candidate)
        
        # Resolve conflict using REC
        winner, rec_info = self._rec_simulator.resolve_conflict(candidates)
        
        # Extract winning phases
        winning_phases = winner.beacon_data['phase_dict']
        
        # Prune losing epochs from storage (in production, gossip would handle this)
        if key in self._storage:
            # Keep only the winning epoch
            self._storage[key] = {winner.epoch: winning_phases}
        
        return rec_info, winning_phases
    
    def _fetch_address_phases(
        self,
        key: str,
        primes: List[int]
    ) -> Dict[int, List[float]]:
        """
        Fetch address phases from local storage or gossip plane.
        
        Legacy method for single-epoch fetches.
        Use _fetch_all_epochs() for conflict-aware retrieval.
        
        Args:
            key: Key to fetch
            primes: Primes to fetch phases for
            
        Returns:
            Dict mapping primes to phase lists
        """
        epoch_map = self._fetch_all_epochs(key, primes)
        if not epoch_map:
            return {}
        
        # Return the most recent epoch
        latest_epoch = max(epoch_map.keys())
        return epoch_map[latest_epoch]
    
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
