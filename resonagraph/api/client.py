"""
Client SDK for ResonaGraph.

Implements the core operations from design.md Section 4.1:
- put(key, payload, phase_key, options)
- get(key, phase_key) with Phase 4 REC conflict resolution
- traverse(start_key, pattern, phase_key)
- query(cypher_query, phase_key, params)
"""

from typing import Dict, Any, Optional, List, Tuple
import time
from cryptography.hazmat.primitives.asymmetric import ed25519

from resonagraph.core.phase_key import PhaseKey
from resonagraph.core.prime_selection import PrimeSelector
from resonagraph.core.phase_encoding import PhaseEncoder
from resonagraph.gossip import Beacon, GossipManager, KademliaDHT
from resonagraph.resonance import (
    ProbeSynthesizer, ResonanceLock, ResidueExtractor,
    RECSimulator, ConflictCandidate
)
from resonagraph.api.query import Query


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
        phase_key: PhaseKey,
        max_depth: int = 3,
        use_coherence: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Graph traversal with coherence bias.
        
        According to copilot-instructions.md Section 4:
        Uses Hamiltonian H_G bias for efficient locks
        
        Phase 5 implementation:
        - Start from start_key vertex
        - Apply coherence bias using H_G for subgraph traversal
        - Traverse edges according to pattern (e.g., "FOLLOWS", "KNOWS")
        - Use resonance locking for each hop
        
        Args:
            start_key: Starting vertex key
            pattern: Traversal pattern (relationship type)
            phase_key: Cryptographic phase key
            max_depth: Maximum traversal depth (default 3)
            use_coherence: Apply coherence bias (default True)
            
        Returns:
            List of matching vertices/edges with metadata
        """
        start_time = time.time()
        results = []
        visited = set()
        
        # Step 1: Get starting vertex
        start_node = self.get(start_key, phase_key)
        if not start_node['found']:
            return []
        
        # Step 2: Initialize traversal queue
        # Each item: (key, payload, depth, path)
        queue = [(start_key, start_node['payload'], 0, [start_key])]
        visited.add(start_key)
        
        # Step 3: Breadth-first traversal with coherence bias
        while queue:
            current_key, current_payload, depth, path = queue.pop(0)
            
            # Add current node to results
            results.append({
                'key': current_key,
                'payload': current_payload,
                'depth': depth,
                'path': path,
                'type': 'vertex'
            })
            
            # Stop if max depth reached
            if depth >= max_depth:
                continue
            
            # Step 4: Find edges from current vertex
            # In storage, edges are stored as "edge:src:dst:type"
            # For simulation, we'll check storage for edge keys
            edges = self._find_edges_from_vertex(current_key, pattern)
            
            # Step 5: Apply coherence bias if enabled
            if use_coherence and edges:
                edges = self._apply_coherence_bias(
                    edges, current_key, phase_key
                )
            
            # Step 6: Traverse to neighbor vertices
            for edge in edges:
                dst_key = edge['dst_key']
                
                if dst_key not in visited:
                    visited.add(dst_key)
                    
                    # Retrieve destination vertex
                    dst_node = self.get(dst_key, phase_key)
                    if dst_node['found']:
                        new_path = path + [dst_key]
                        queue.append((
                            dst_key,
                            dst_node['payload'],
                            depth + 1,
                            new_path
                        ))
                        
                        # Add edge to results
                        results.append({
                            'key': edge['key'],
                            'src_key': edge['src_key'],
                            'dst_key': edge['dst_key'],
                            'type': 'edge',
                            'edge_type': edge['edge_type'],
                            'payload': edge.get('payload', {}),
                            'depth': depth
                        })
        
        traversal_time = time.time() - start_time
        
        return results
    
    def _find_edges_from_vertex(
        self,
        src_key: str,
        pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find edges originating from a vertex.
        
        Args:
            src_key: Source vertex key
            pattern: Optional edge type filter
            
        Returns:
            List of edge metadata
        """
        edges = []
        
        # Search storage for edge keys matching pattern
        # Edge key format: "edge:src_key:dst_key:edge_type"
        # Example: "edge:vertex:a:vertex:b:NEXT"
        for key in self._storage.keys():
            if not key.startswith("edge:"):
                continue
            
            # Remove "edge:" prefix
            edge_info = key[5:]  # Skip "edge:"
            
            # Try to parse the edge structure
            # Format: src_key:dst_key:edge_type
            # src_key and dst_key may contain colons
            
            # Look for the src_key
            if not edge_info.startswith(src_key + ":"):
                continue
            
            # Remove src_key and leading colon
            rest = edge_info[len(src_key) + 1:]
            
            # Now we have "dst_key:edge_type"
            # Find the last colon to separate dst_key and edge_type
            if ':' in rest:
                last_colon_idx = rest.rfind(':')
                dst_key = rest[:last_colon_idx]
                edge_type = rest[last_colon_idx + 1:]
            else:
                # No edge type specified
                dst_key = rest
                edge_type = None
            
            # Filter by pattern if provided
            if pattern and edge_type != pattern:
                continue
            
            edges.append({
                'key': key,
                'src_key': src_key,
                'dst_key': dst_key,
                'edge_type': edge_type
            })
        
        return edges
    
    def _apply_coherence_bias(
        self,
        edges: List[Dict[str, Any]],
        current_key: str,
        phase_key: PhaseKey
    ) -> List[Dict[str, Any]]:
        """
        Apply Hamiltonian coherence bias to edge selection.
        
        According to copilot-instructions.md:
        Bias queries toward minimum Hamiltonian H_G for efficient locks
        
        Args:
            edges: List of candidate edges
            current_key: Current vertex key
            phase_key: Phase key for resonance computation
            
        Returns:
            Sorted edges with coherence bias applied
        """
        # Compute coherence score for each edge
        # H_G bias favors edges with high phase alignment
        scored_edges = []
        
        for edge in edges:
            # Get phases for current vertex and destination
            # Coherence ~ phase alignment between vertices
            coherence_score = self._compute_coherence_score(
                current_key, edge['dst_key'], phase_key
            )
            
            scored_edges.append((coherence_score, edge))
        
        # Sort by coherence score (descending)
        scored_edges.sort(key=lambda x: x[0], reverse=True)
        
        return [edge for _, edge in scored_edges]
    
    def _compute_coherence_score(
        self,
        key1: str,
        key2: str,
        phase_key: PhaseKey
    ) -> float:
        """
        Compute coherence score between two vertices.
        
        Coherence is based on phase alignment:
        Higher alignment = more coherent subgraph = faster locking
        
        Args:
            key1: First vertex key
            key2: Second vertex key
            phase_key: Phase key
            
        Returns:
            Coherence score (0.0 to 1.0)
        """
        # Get primes for both keys
        prime_selector = PrimeSelector()
        primes1 = prime_selector.select_primes(key1)
        primes2 = prime_selector.select_primes(key2)
        
        # Find common primes
        common_primes = set(primes1) & set(primes2)
        if not common_primes:
            return 0.0
        
        # Get phases for common primes
        phases1_map = self._fetch_all_epochs(key1, primes1)
        phases2_map = self._fetch_all_epochs(key2, primes2)
        
        if not phases1_map or not phases2_map:
            return 0.0
        
        # Use latest epochs
        epoch1 = max(phases1_map.keys())
        epoch2 = max(phases2_map.keys())
        
        phases1 = phases1_map[epoch1]
        phases2 = phases2_map[epoch2]
        
        # Compute phase alignment for common primes
        import math
        alignment_sum = 0.0
        count = 0
        
        for prime in common_primes:
            if prime in phases1 and prime in phases2:
                # Get first phase for each prime
                if phases1[prime] and phases2[prime]:
                    phase1 = phases1[prime][0]
                    phase2 = phases2[prime][0]
                    
                    # Compute phase difference
                    diff = abs(phase1 - phase2)
                    # Normalize to [0, π]
                    diff = min(diff, 2 * math.pi - diff)
                    
                    # Convert to alignment score [0, 1]
                    alignment = 1.0 - (diff / math.pi)
                    alignment_sum += alignment
                    count += 1
        
        if count == 0:
            return 0.0
        
        return alignment_sum / count
    
    def query(
        self,
        query_obj: Query,
        phase_key: PhaseKey,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Cypher-like query with resonance extensions.
        
        According to design.md Section 4.1 and 4.2:
        - Supports Cypher subset + resonance extensions
        - COHERE ON: Apply H_G bias for coherent subgraph traversal
        - EPOCH WINDOW: Filter beacons by epoch drift tolerance
        - Lazy evaluation for partial locks
        
        Phase 5 implementation:
        1. Parse Cypher query
        2. Plan execution with coherence hints
        3. Execute traversal using traverse()
        4. Apply WHERE filters
        5. Return results with metrics
        
        Args:
            query_obj: Query object with Cypher string
            phase_key: Cryptographic phase key
            params: Query parameters for substitution
            
        Returns:
            Dict with nodes, edges, and metrics (lock_time, entropy_final)
        """
        start_time = time.time()
        params = params or {}
        
        # Step 1: Parse query
        parsed = query_obj.parse()
        
        # Step 2: Execute MATCH clause
        nodes = []
        edges = []
        
        if parsed['match_clause']:
            match_result = self._execute_match(
                parsed['match_clause'],
                phase_key,
                params,
                cohere_on=parsed.get('cohere_on'),
                epoch_window=parsed.get('epoch_window')
            )
            nodes.extend(match_result['nodes'])
            edges.extend(match_result['edges'])
        
        # Step 3: Apply WHERE filters
        if parsed['where_clause']:
            nodes, edges = self._apply_where_filter(
                nodes, edges, parsed['where_clause'], params
            )
        
        # Step 4: Apply RETURN projection
        if parsed['return_clause']:
            nodes, edges = self._apply_return_projection(
                nodes, edges, parsed['return_clause']
            )
        
        query_time = time.time() - start_time
        
        # Step 5: Return results with metrics
        return {
            'nodes': nodes,
            'edges': edges,
            'metrics': {
                'query_time': query_time,
                'nodes_matched': len(nodes),
                'edges_matched': len(edges),
                'used_cohere': parsed.get('cohere_on') is not None,
                'epoch_window': parsed.get('epoch_window')
            }
        }
    
    def _execute_match(
        self,
        match_clause: Dict[str, Any],
        phase_key: PhaseKey,
        params: Dict[str, Any],
        cohere_on: Optional[List[str]] = None,
        epoch_window: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute MATCH clause to find matching patterns.
        
        Args:
            match_clause: Parsed MATCH clause
            phase_key: Phase key
            params: Query parameters
            cohere_on: Variables to apply coherence bias
            epoch_window: Epoch drift tolerance
            
        Returns:
            Dict with matched nodes and edges
        """
        nodes_list = match_clause.get('nodes', [])
        relationships = match_clause.get('relationships', [])
        
        matched_nodes = []
        matched_edges = []
        
        # Simple implementation: match first node, then traverse
        if nodes_list:
            first_node = nodes_list[0]
            
            # Find starting vertices
            start_keys = self._find_matching_vertices(
                first_node, params, epoch_window
            )
            
            # For each starting vertex, traverse relationships
            for start_key in start_keys:
                if relationships:
                    # Use traverse with relationship pattern
                    rel = relationships[0]
                    rel_type = rel.get('type')
                    max_hops = rel.get('max_hops', 1)
                    
                    # Apply coherence if specified
                    use_coherence = cohere_on is not None
                    
                    traversal_results = self.traverse(
                        start_key,
                        rel_type,
                        phase_key,
                        max_depth=max_hops if max_hops != float('inf') else 3,
                        use_coherence=use_coherence
                    )
                    
                    # Separate nodes and edges
                    for result in traversal_results:
                        if result['type'] == 'vertex':
                            matched_nodes.append(result)
                        elif result['type'] == 'edge':
                            matched_edges.append(result)
                else:
                    # No relationships, just return the node
                    node_data = self.get(start_key, phase_key)
                    if node_data['found']:
                        matched_nodes.append({
                            'key': start_key,
                            'payload': node_data['payload'],
                            'type': 'vertex',
                            'depth': 0,
                            'path': [start_key]
                        })
        
        return {
            'nodes': matched_nodes,
            'edges': matched_edges
        }
    
    def _find_matching_vertices(
        self,
        node_pattern: Dict[str, Any],
        params: Dict[str, Any],
        epoch_window: Optional[int] = None
    ) -> List[str]:
        """
        Find vertices matching node pattern.
        
        Args:
            node_pattern: Node pattern from MATCH clause
            params: Query parameters
            epoch_window: Epoch drift tolerance
            
        Returns:
            List of matching vertex keys
        """
        matching_keys = []
        
        # Get properties to match
        properties = node_pattern.get('properties', {})
        
        # If 'id' property specified, use it directly
        if 'id' in properties:
            key = properties['id']
            # Check if key exists in storage
            if key in self._storage:
                # Apply epoch window filter if specified
                if epoch_window is not None:
                    epochs = list(self._storage[key].keys())
                    latest_epoch = max(epochs)
                    # Filter epochs within window
                    valid_epochs = [
                        e for e in epochs
                        if abs(e - latest_epoch) <= epoch_window
                    ]
                    if valid_epochs:
                        matching_keys.append(key)
                else:
                    matching_keys.append(key)
        else:
            # Search all keys (in production, would use index)
            for key in self._storage.keys():
                # Skip edge keys
                if key.startswith('edge:'):
                    continue
                
                # Apply epoch window if specified
                if epoch_window is not None:
                    epochs = list(self._storage[key].keys())
                    if epochs:
                        latest_epoch = max(epochs)
                        valid_epochs = [
                            e for e in epochs
                            if abs(e - latest_epoch) <= epoch_window
                        ]
                        if not valid_epochs:
                            continue
                
                matching_keys.append(key)
        
        return matching_keys
    
    def _apply_where_filter(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        where_clause: str,
        params: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Apply WHERE clause filters.
        
        Args:
            nodes: Matched nodes
            edges: Matched edges
            where_clause: WHERE clause condition
            params: Query parameters
            
        Returns:
            Filtered nodes and edges
        """
        # Simple implementation: parse basic conditions
        # In production, would use expression evaluator
        
        filtered_nodes = []
        filtered_edges = []
        
        # For now, keep all nodes/edges (placeholder)
        # Full implementation would evaluate WHERE conditions
        filtered_nodes = nodes
        filtered_edges = edges
        
        return filtered_nodes, filtered_edges
    
    def _apply_return_projection(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        return_clause: List[str]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Apply RETURN clause projection.
        
        Args:
            nodes: Matched nodes
            edges: Matched edges
            return_clause: List of return expressions
            
        Returns:
            Projected nodes and edges
        """
        # Simple implementation: return all fields
        # In production, would project specific fields
        
        projected_nodes = []
        projected_edges = []
        
        for node in nodes:
            # Extract requested fields
            projected = {}
            for expr in return_clause:
                # Handle simple property access: var.prop
                if '.' in expr:
                    var, prop = expr.split('.', 1)
                    if 'payload' in node and prop in node['payload']:
                        projected[expr] = node['payload'][prop]
                else:
                    # Return entire node
                    projected[expr] = node
            
            if projected:
                projected_nodes.append(projected)
            else:
                # If no projection, return original
                projected_nodes.append(node)
        
        # Similar for edges
        projected_edges = edges
        
        return projected_nodes, projected_edges
