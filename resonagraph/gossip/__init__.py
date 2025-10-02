"""
Gossip Plane implementation for ResonaGraph.

This module implements the Gossip Plane components according to 
copilot-instructions.md Section 1 (Gossip Plane) and design.md Section 2.2.1.

Components:
- Beacon: Compact metadata structure (128-512 bytes)
- DHT: Kademlia-based discovery
- Manager: Gossip coordination
"""

from resonagraph.gossip.beacon import Beacon, BeaconMetadata
from resonagraph.gossip.dht import (
    KademliaDHT,
    Node,
    BloomFilter,
    compute_prime_hash
)
from resonagraph.gossip.manager import GossipManager, GossipMessage

__all__ = [
    'Beacon',
    'BeaconMetadata',
    'KademliaDHT',
    'Node',
    'BloomFilter',
    'compute_prime_hash',
    'GossipManager',
    'GossipMessage',
]
