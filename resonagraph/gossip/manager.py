"""
Gossip manager for coordinating beacon exchange in ResonaGraph.

According to design.md Section 2.2.1 and copilot-instructions.md:
- Coordinate beacon exchange
- Manage gossip mechanics (periodic floods, TTL, heartbeats)
- Integration point for Client SDK

This provides a simplified gossip protocol without full QUIC support.
For production, this would use QUIC via quiche library.
"""

import time
import threading
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass

from resonagraph.gossip.beacon import Beacon, TAU_EPOCH
from resonagraph.gossip.dht import KademliaDHT, Node, compute_prime_hash


# Gossip parameters from design.md Section 2.2.1
GOSSIP_INTERVAL = TAU_EPOCH // 2  # Periodic floods every τ/2
TTL_HOPS = 3  # TTL=3 hops for gossip propagation
HEARTBEAT_INTERVAL = TAU_EPOCH  # Heartbeat every τ


@dataclass
class GossipMessage:
    """
    Represents a gossip message.
    
    Messages are used for beacon propagation and heartbeats.
    """
    message_type: str  # 'beacon', 'heartbeat', 'query'
    sender_id: bytes
    payload: bytes
    ttl: int = TTL_HOPS
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def decrement_ttl(self) -> bool:
        """
        Decrement TTL and check if message should continue propagating.
        
        Returns:
            True if message should continue, False if TTL expired
        """
        self.ttl -= 1
        return self.ttl > 0


class GossipManager:
    """
    Manages gossip coordination for beacon exchange.
    
    According to design.md Section 2.2.1:
    - Periodic floods (every τ/2)
    - TTL=3 hops
    - Heartbeat beacons for liveness
    - Integration with DHT for discovery
    """
    
    def __init__(
        self,
        dht: KademliaDHT,
        address: str = "localhost:0"
    ):
        """
        Initialize gossip manager.
        
        Args:
            dht: Kademlia DHT instance
            address: Network address for this node
        """
        self.dht = dht
        self.address = address
        self.node_id = dht.self_node.node_id
        
        # Local beacon storage
        self.local_beacons: Dict[str, Beacon] = {}  # key -> Beacon
        
        # Gossip state
        self.is_running = False
        self._gossip_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        
        # Callbacks for network operations (would be implemented with QUIC)
        self.send_callback: Optional[Callable[[Node, GossipMessage], None]] = None
        
        # Statistics
        self.stats = {
            'beacons_sent': 0,
            'beacons_received': 0,
            'heartbeats_sent': 0,
            'heartbeats_received': 0
        }
    
    def start(self):
        """
        Start gossip manager threads.
        
        Starts periodic beacon gossip and heartbeat threads.
        """
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start gossip thread
        self._gossip_thread = threading.Thread(target=self._gossip_loop, daemon=True)
        self._gossip_thread.start()
        
        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
    
    def stop(self):
        """Stop gossip manager threads."""
        self.is_running = False
        
        if self._gossip_thread:
            self._gossip_thread.join(timeout=1.0)
        
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1.0)
    
    def _gossip_loop(self):
        """
        Periodic gossip loop.
        
        According to design.md Section 2.2.1:
        - Floods beacons every τ/2
        """
        while self.is_running:
            try:
                self._perform_gossip_round()
            except Exception as e:
                # Log error in production
                pass
            
            # Sleep until next gossip interval
            time.sleep(GOSSIP_INTERVAL)
    
    def _heartbeat_loop(self):
        """
        Periodic heartbeat loop.
        
        Sends heartbeat beacons for liveness detection.
        """
        while self.is_running:
            try:
                self._send_heartbeat()
            except Exception as e:
                # Log error in production
                pass
            
            # Sleep until next heartbeat
            time.sleep(HEARTBEAT_INTERVAL)
    
    def _perform_gossip_round(self):
        """
        Perform one round of gossip propagation.
        
        Sends recent beacons to known peers with TTL=3.
        """
        # Get neighbors from DHT
        neighbors = self.dht.find_closest_nodes(self.node_id, count=10)
        
        if not neighbors:
            return
        
        # Send recent beacons to neighbors
        for key, beacon in self.local_beacons.items():
            message = GossipMessage(
                message_type='beacon',
                sender_id=self.node_id,
                payload=beacon.serialize(),
                ttl=TTL_HOPS
            )
            
            for neighbor in neighbors:
                self._send_message(neighbor, message)
                self.stats['beacons_sent'] += 1
    
    def _send_heartbeat(self):
        """
        Send heartbeat to neighbors.
        
        Heartbeat contains node ID and timestamp for liveness detection.
        """
        neighbors = self.dht.find_closest_nodes(self.node_id, count=10)
        
        if not neighbors:
            return
        
        # Create heartbeat payload
        timestamp_int = int(time.time() * 1000)  # Convert to milliseconds int
        heartbeat_payload = self.node_id + timestamp_int.to_bytes(8, byteorder='big')
        
        message = GossipMessage(
            message_type='heartbeat',
            sender_id=self.node_id,
            payload=heartbeat_payload,
            ttl=1  # Heartbeats don't propagate
        )
        
        for neighbor in neighbors:
            self._send_message(neighbor, message)
            self.stats['heartbeats_sent'] += 1
    
    def _send_message(self, node: Node, message: GossipMessage):
        """
        Send message to node.
        
        In production, this would use QUIC protocol.
        For now, uses callback if provided.
        
        Args:
            node: Target node
            message: Message to send
        """
        if self.send_callback:
            self.send_callback(node, message)
    
    def publish_beacon(self, key: str, beacon: Beacon):
        """
        Publish beacon for gossip propagation.
        
        Args:
            key: Key for this beacon
            beacon: Beacon to publish
        """
        # Store locally
        self.local_beacons[key] = beacon
        
        # Store in DHT
        prime_hash = compute_prime_hash(beacon.primes)
        self.dht.store_beacon(prime_hash, beacon.serialize())
    
    def receive_message(self, sender_id: bytes, message: GossipMessage):
        """
        Receive and process gossip message.
        
        Args:
            sender_id: Sender node ID
            message: Received message
        """
        if message.message_type == 'beacon':
            self._handle_beacon_message(sender_id, message)
        elif message.message_type == 'heartbeat':
            self._handle_heartbeat_message(sender_id, message)
        elif message.message_type == 'query':
            self._handle_query_message(sender_id, message)
    
    def _handle_beacon_message(self, sender_id: bytes, message: GossipMessage):
        """
        Handle received beacon message.
        
        Args:
            sender_id: Sender node ID
            message: Beacon message
        """
        self.stats['beacons_received'] += 1
        
        try:
            # Deserialize beacon
            beacon = Beacon.deserialize(message.payload)
            
            # Store in DHT
            prime_hash = compute_prime_hash(beacon.primes)
            
            # Check if we've seen this beacon (using Bloom filter)
            if not self.dht.has_beacon(prime_hash, message.payload):
                self.dht.store_beacon(prime_hash, message.payload)
                
                # Propagate if TTL allows
                if message.decrement_ttl():
                    self._propagate_message(message)
        
        except Exception as e:
            # Log error in production
            pass
    
    def _handle_heartbeat_message(self, sender_id: bytes, message: GossipMessage):
        """
        Handle received heartbeat message.
        
        Updates last_seen time for sender node.
        
        Args:
            sender_id: Sender node ID
            message: Heartbeat message
        """
        self.stats['heartbeats_received'] += 1
        
        # Update node last_seen in DHT (if node exists)
        # In production, this would update routing table
    
    def _handle_query_message(self, sender_id: bytes, message: GossipMessage):
        """
        Handle received query message.
        
        Responds with matching beacons from DHT.
        
        Args:
            sender_id: Sender node ID
            message: Query message
        """
        # Parse query (prime_hash)
        prime_hash = message.payload
        
        # Lookup beacon
        beacon_data = self.dht.lookup_beacon(prime_hash)
        
        if beacon_data:
            # Send response (would use QUIC in production)
            response = GossipMessage(
                message_type='beacon',
                sender_id=self.node_id,
                payload=beacon_data,
                ttl=1
            )
            # Would send to sender
    
    def _propagate_message(self, message: GossipMessage):
        """
        Propagate message to neighbors.
        
        Args:
            message: Message to propagate
        """
        neighbors = self.dht.find_closest_nodes(self.node_id, count=5)
        
        for neighbor in neighbors:
            if neighbor.node_id != message.sender_id:  # Don't send back to sender
                self._send_message(neighbor, message)
    
    def query_beacon(self, primes: List[int]) -> Optional[Beacon]:
        """
        Query for beacon by prime set.
        
        Args:
            primes: List of primes to query
            
        Returns:
            Beacon if found, None otherwise
        """
        prime_hash = compute_prime_hash(primes)
        beacon_data = self.dht.lookup_beacon(prime_hash)
        
        if beacon_data:
            try:
                return Beacon.deserialize(beacon_data)
            except Exception:
                return None
        
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get gossip statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            **self.stats,
            'local_beacons': len(self.local_beacons),
            'dht_nodes': self.dht.get_node_count(),
            'dht_beacons': self.dht.get_beacon_count()
        }
    
    def __repr__(self):
        stats = self.get_stats()
        return (f"GossipManager(node={self.node_id.hex()[:8]}..., "
                f"beacons={stats['local_beacons']}, "
                f"running={self.is_running})")
