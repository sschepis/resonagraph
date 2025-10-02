"""
Kademlia DHT implementation for ResonaGraph gossip plane discovery.

According to design.md Section 2.2.1 and copilot-instructions.md:
- Discovery: Kademlia DHT keyed on prime hashes
- Bloom filters prune duplicates
- Node discovery and routing

This is a simplified Kademlia implementation optimized for beacon discovery.
"""

import hashlib
import random
import time
from typing import List, Optional, Set, Dict, Tuple
from dataclasses import dataclass, field
import struct


# Kademlia parameters from design
K_BUCKET_SIZE = 20  # k parameter - nodes per bucket
ALPHA = 3  # α parameter - parallel lookups
ID_BITS = 160  # 160-bit node IDs (SHA-1 size)
BLOOM_FILTER_SIZE = 10000  # Bloom filter size for deduplication


@dataclass
class Node:
    """
    Represents a node in the DHT.
    
    According to design.md Section 2.2.1:
    - Each node has a unique ID derived from its address
    - Nodes store beacons keyed on prime hashes
    """
    node_id: bytes  # 160-bit ID
    address: str    # Network address (e.g., "ip:port")
    last_seen: float = field(default_factory=time.time)
    
    def distance_to(self, other_id: bytes) -> int:
        """
        Compute XOR distance to another node ID.
        
        Kademlia uses XOR metric for distance.
        
        Args:
            other_id: Target node ID
            
        Returns:
            XOR distance as integer
        """
        # XOR the two IDs byte by byte
        distance = int.from_bytes(self.node_id, byteorder='big') ^ \
                   int.from_bytes(other_id, byteorder='big')
        return distance
    
    def __hash__(self):
        return hash(self.node_id)
    
    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.node_id == other.node_id
    
    def __repr__(self):
        node_id_hex = self.node_id.hex()[:8]
        return f"Node(id={node_id_hex}..., addr={self.address})"


@dataclass
class KBucket:
    """
    K-bucket storing up to k nodes.
    
    According to Kademlia specification:
    - Each bucket stores up to k nodes
    - Nodes are sorted by last-seen time
    - Implements least-recently-seen eviction
    """
    min_distance: int  # Minimum XOR distance for this bucket
    max_distance: int  # Maximum XOR distance for this bucket
    nodes: List[Node] = field(default_factory=list)
    k: int = K_BUCKET_SIZE
    
    def add_node(self, node: Node) -> bool:
        """
        Add node to bucket.
        
        Args:
            node: Node to add
            
        Returns:
            True if node was added, False if bucket is full
        """
        # Check if node already exists
        existing = next((n for n in self.nodes if n.node_id == node.node_id), None)
        if existing:
            # Update last_seen and move to end
            existing.last_seen = node.last_seen
            self.nodes.remove(existing)
            self.nodes.append(existing)
            return True
        
        # Add new node if space available
        if len(self.nodes) < self.k:
            self.nodes.append(node)
            return True
        
        # Bucket is full - in real Kademlia, we'd ping the oldest node
        # For now, just reject
        return False
    
    def remove_node(self, node_id: bytes) -> bool:
        """
        Remove node from bucket.
        
        Args:
            node_id: ID of node to remove
            
        Returns:
            True if node was removed, False if not found
        """
        node = next((n for n in self.nodes if n.node_id == node_id), None)
        if node:
            self.nodes.remove(node)
            return True
        return False
    
    def get_nodes(self) -> List[Node]:
        """
        Get all nodes in bucket.
        
        Returns:
            List of nodes
        """
        return self.nodes.copy()


class BloomFilter:
    """
    Simple Bloom filter for beacon deduplication.
    
    According to design.md Section 2.2.1:
    - Bloom filters prune duplicate beacons during gossip
    """
    
    def __init__(self, size: int = BLOOM_FILTER_SIZE, hash_count: int = 3):
        """
        Initialize Bloom filter.
        
        Args:
            size: Size of bit array
            hash_count: Number of hash functions
        """
        self.size = size
        self.hash_count = hash_count
        self.bit_array = [False] * size
    
    def _hash(self, item: bytes, seed: int) -> int:
        """
        Hash item with seed.
        
        Args:
            item: Item to hash
            seed: Hash seed
            
        Returns:
            Hash value modulo size
        """
        h = hashlib.sha256(item + struct.pack('<I', seed)).digest()
        return int.from_bytes(h[:4], byteorder='big') % self.size
    
    def add(self, item: bytes) -> None:
        """
        Add item to filter.
        
        Args:
            item: Item to add
        """
        for i in range(self.hash_count):
            idx = self._hash(item, i)
            self.bit_array[idx] = True
    
    def contains(self, item: bytes) -> bool:
        """
        Check if item might be in filter.
        
        Args:
            item: Item to check
            
        Returns:
            True if item might be present (false positives possible)
            False if item is definitely not present
        """
        for i in range(self.hash_count):
            idx = self._hash(item, i)
            if not self.bit_array[idx]:
                return False
        return True


class KademliaDHT:
    """
    Kademlia DHT for beacon discovery.
    
    According to design.md Section 2.2.1:
    - DHT keyed on prime hashes
    - Supports node discovery and routing
    - Bloom filters for deduplication
    """
    
    def __init__(self, node_id: Optional[bytes] = None, address: str = "localhost:0"):
        """
        Initialize DHT.
        
        Args:
            node_id: This node's ID (generated if None)
            address: This node's network address
        """
        if node_id is None:
            # Generate random node ID
            node_id = hashlib.sha1(address.encode() + 
                                  struct.pack('<d', time.time())).digest()
        
        self.self_node = Node(node_id=node_id, address=address)
        self.buckets: List[KBucket] = []
        self._initialize_buckets()
        
        # Bloom filter for beacon deduplication
        self.beacon_filter = BloomFilter()
        
        # Local beacon storage (prime_hash -> beacon_data)
        self.beacons: Dict[bytes, bytes] = {}
    
    def _initialize_buckets(self) -> None:
        """
        Initialize k-buckets for all possible distances.
        
        Creates ID_BITS buckets for the full ID space.
        """
        for i in range(ID_BITS):
            min_dist = 2 ** i
            max_dist = 2 ** (i + 1) - 1 if i < ID_BITS - 1 else 2 ** ID_BITS
            bucket = KBucket(min_distance=min_dist, max_distance=max_dist)
            self.buckets.append(bucket)
    
    def _get_bucket_index(self, distance: int) -> int:
        """
        Get bucket index for given distance.
        
        Args:
            distance: XOR distance
            
        Returns:
            Bucket index (0 to ID_BITS-1)
        """
        if distance == 0:
            return 0
        
        # Find the position of the highest bit
        bit_length = distance.bit_length()
        return min(bit_length - 1, ID_BITS - 1)
    
    def add_node(self, node: Node) -> bool:
        """
        Add node to routing table.
        
        Args:
            node: Node to add
            
        Returns:
            True if node was added
        """
        if node.node_id == self.self_node.node_id:
            return False
        
        distance = self.self_node.distance_to(node.node_id)
        bucket_idx = self._get_bucket_index(distance)
        
        return self.buckets[bucket_idx].add_node(node)
    
    def find_closest_nodes(self, target_id: bytes, count: int = K_BUCKET_SIZE) -> List[Node]:
        """
        Find closest nodes to target ID.
        
        Args:
            target_id: Target node ID
            count: Number of nodes to return
            
        Returns:
            List of closest nodes
        """
        # Collect all nodes from all buckets
        all_nodes: List[Node] = []
        for bucket in self.buckets:
            all_nodes.extend(bucket.get_nodes())
        
        # Sort by distance to target
        all_nodes.sort(key=lambda n: n.distance_to(target_id))
        
        return all_nodes[:count]
    
    def store_beacon(self, prime_hash: bytes, beacon_data: bytes) -> None:
        """
        Store beacon keyed by prime hash.
        
        According to design.md Section 2.2.1:
        - Beacons are stored keyed on prime hashes
        
        Args:
            prime_hash: Hash of prime set
            beacon_data: Serialized beacon
        """
        # Add to bloom filter for deduplication
        beacon_key = prime_hash + beacon_data[:32]  # Use first 32 bytes as key
        
        if not self.beacon_filter.contains(beacon_key):
            self.beacon_filter.add(beacon_key)
            self.beacons[prime_hash] = beacon_data
    
    def lookup_beacon(self, prime_hash: bytes) -> Optional[bytes]:
        """
        Lookup beacon by prime hash.
        
        Args:
            prime_hash: Hash of prime set
            
        Returns:
            Beacon data if found, None otherwise
        """
        return self.beacons.get(prime_hash)
    
    def has_beacon(self, prime_hash: bytes, beacon_data: bytes) -> bool:
        """
        Check if beacon has been seen (using Bloom filter).
        
        Args:
            prime_hash: Hash of prime set
            beacon_data: Serialized beacon
            
        Returns:
            True if beacon might have been seen (false positives possible)
        """
        beacon_key = prime_hash + beacon_data[:32]
        return self.beacon_filter.contains(beacon_key)
    
    def iterative_find_node(self, target_id: bytes) -> List[Node]:
        """
        Iteratively find closest nodes to target.
        
        This is the core Kademlia lookup algorithm.
        
        Args:
            target_id: Target node ID
            
        Returns:
            List of k closest nodes
        """
        # Start with closest known nodes
        closest = self.find_closest_nodes(target_id, ALPHA)
        queried: Set[bytes] = set()
        
        # Simplified iterative lookup (real implementation would be async)
        for _ in range(10):  # Max iterations
            # Find unqueried nodes
            to_query = [n for n in closest if n.node_id not in queried]
            
            if not to_query:
                break
            
            # Query up to ALPHA nodes
            for node in to_query[:ALPHA]:
                queried.add(node.node_id)
                # In real implementation, we'd send FIND_NODE RPC
                # For now, just mark as queried
            
            # Get new closest nodes (would be from RPC responses)
            closest = self.find_closest_nodes(target_id, K_BUCKET_SIZE)
        
        return closest[:K_BUCKET_SIZE]
    
    def get_node_count(self) -> int:
        """
        Get total number of nodes in routing table.
        
        Returns:
            Total node count
        """
        return sum(len(bucket.nodes) for bucket in self.buckets)
    
    def get_beacon_count(self) -> int:
        """
        Get total number of stored beacons.
        
        Returns:
            Beacon count
        """
        return len(self.beacons)
    
    def __repr__(self):
        node_count = self.get_node_count()
        beacon_count = self.get_beacon_count()
        return (f"KademliaDHT(id={self.self_node.node_id.hex()[:8]}..., "
                f"nodes={node_count}, beacons={beacon_count})")


def compute_prime_hash(primes: List[int]) -> bytes:
    """
    Compute hash of prime set for DHT keying.
    
    According to design.md Section 2.2.1:
    - DHT keyed on prime hashes
    
    Args:
        primes: List of primes
        
    Returns:
        SHA-1 hash of primes (160 bits for Kademlia)
    """
    prime_data = ','.join(str(p) for p in sorted(primes)).encode()
    return hashlib.sha1(prime_data).digest()
