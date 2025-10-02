"""
Tests for gossip manager.

Tests gossip coordination, beacon propagation, and heartbeats
according to copilot-instructions.md Section 7 (Testing Strategies).
"""

import pytest
import time
import hashlib

from resonagraph.gossip.manager import (
    GossipManager,
    GossipMessage,
    GOSSIP_INTERVAL,
    TTL_HOPS
)
from resonagraph.gossip.beacon import Beacon
from resonagraph.gossip.dht import KademliaDHT, Node


class TestGossipMessage:
    """Test GossipMessage class."""
    
    def test_gossip_message_creation(self):
        """Test basic gossip message creation."""
        sender_id = hashlib.sha1(b"sender").digest()
        payload = b"test payload"
        
        msg = GossipMessage(
            message_type='beacon',
            sender_id=sender_id,
            payload=payload
        )
        
        assert msg.message_type == 'beacon'
        assert msg.sender_id == sender_id
        assert msg.payload == payload
        assert msg.ttl == TTL_HOPS
        assert msg.timestamp > 0
    
    def test_gossip_message_decrement_ttl(self):
        """Test TTL decrement."""
        msg = GossipMessage(
            message_type='beacon',
            sender_id=b'sender',
            payload=b'payload',
            ttl=3
        )
        
        assert msg.decrement_ttl() is True  # TTL=2
        assert msg.ttl == 2
        
        assert msg.decrement_ttl() is True  # TTL=1
        assert msg.ttl == 1
        
        assert msg.decrement_ttl() is False  # TTL=0
        assert msg.ttl == 0
    
    def test_gossip_message_ttl_zero(self):
        """Test message with TTL=0 doesn't propagate."""
        msg = GossipMessage(
            message_type='beacon',
            sender_id=b'sender',
            payload=b'payload',
            ttl=1
        )
        
        assert msg.decrement_ttl() is False


class TestGossipManager:
    """Test GossipManager class."""
    
    def test_gossip_manager_creation(self):
        """Test basic gossip manager creation."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht, address="localhost:8000")
        
        assert manager.dht is dht
        assert manager.address == "localhost:8000"
        assert manager.node_id == dht.self_node.node_id
        assert manager.is_running is False
    
    def test_gossip_manager_start_stop(self):
        """Test starting and stopping gossip manager."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Start manager
        manager.start()
        assert manager.is_running is True
        
        # Give threads time to start
        time.sleep(0.1)
        
        # Stop manager
        manager.stop()
        assert manager.is_running is False
    
    def test_gossip_manager_publish_beacon(self):
        """Test publishing beacon."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Create beacon
        beacon = Beacon(
            key="vertex:test",
            primes=[2, 3, 5, 7],
            phase_angles=[1.0, 2.0, 3.0, 4.0]
        )
        
        # Publish beacon
        manager.publish_beacon("vertex:test", beacon)
        
        # Check it's stored locally
        assert "vertex:test" in manager.local_beacons
        assert manager.local_beacons["vertex:test"] == beacon
        
        # Check it's in DHT
        stats = manager.get_stats()
        assert stats['dht_beacons'] > 0
    
    def test_gossip_manager_query_beacon(self):
        """Test querying beacon by primes."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Create and publish beacon
        primes = [2, 3, 5, 7]
        beacon = Beacon(
            key="vertex:test",
            primes=primes,
            phase_angles=[1.0, 2.0, 3.0, 4.0]
        )
        manager.publish_beacon("vertex:test", beacon)
        
        # Query beacon
        result = manager.query_beacon(primes)
        
        assert result is not None
        assert result.primes == []  # Deserialized beacon has empty primes (not stored)
        assert result.epoch == beacon.epoch
    
    def test_gossip_manager_receive_beacon_message(self):
        """Test receiving beacon message."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Create beacon
        beacon = Beacon(
            key="vertex:test",
            primes=[2, 3, 5, 7],
            phase_angles=[1.0, 2.0, 3.0, 4.0]
        )
        
        # Create message
        message = GossipMessage(
            message_type='beacon',
            sender_id=hashlib.sha1(b"sender").digest(),
            payload=beacon.serialize()
        )
        
        # Receive message
        initial_received = manager.stats['beacons_received']
        manager.receive_message(message.sender_id, message)
        
        # Check stats updated
        assert manager.stats['beacons_received'] == initial_received + 1
        
        # Check beacon stored in DHT
        assert manager.dht.get_beacon_count() > 0
    
    def test_gossip_manager_receive_heartbeat_message(self):
        """Test receiving heartbeat message."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Create heartbeat message
        sender_id = hashlib.sha1(b"sender").digest()
        timestamp_int = int(time.time() * 1000)  # Convert to milliseconds int
        heartbeat_payload = sender_id + timestamp_int.to_bytes(8, byteorder='big')
        
        message = GossipMessage(
            message_type='heartbeat',
            sender_id=sender_id,
            payload=heartbeat_payload,
            ttl=1
        )
        
        # Receive message
        initial_received = manager.stats['heartbeats_received']
        manager.receive_message(sender_id, message)
        
        # Check stats updated
        assert manager.stats['heartbeats_received'] == initial_received + 1
    
    def test_gossip_manager_get_stats(self):
        """Test getting gossip statistics."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        stats = manager.get_stats()
        
        assert 'beacons_sent' in stats
        assert 'beacons_received' in stats
        assert 'heartbeats_sent' in stats
        assert 'heartbeats_received' in stats
        assert 'local_beacons' in stats
        assert 'dht_nodes' in stats
        assert 'dht_beacons' in stats
        
        assert stats['beacons_sent'] == 0
        assert stats['local_beacons'] == 0
    
    def test_gossip_manager_send_callback(self):
        """Test send callback mechanism."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Track sent messages
        sent_messages = []
        
        def send_callback(node, message):
            sent_messages.append((node, message))
        
        manager.send_callback = send_callback
        
        # Add a neighbor node
        neighbor = Node(
            node_id=hashlib.sha1(b"neighbor").digest(),
            address="192.168.1.1:8000"
        )
        dht.add_node(neighbor)
        
        # Publish beacon
        beacon = Beacon(
            key="vertex:test",
            primes=[2, 3, 5, 7],
            phase_angles=[1.0, 2.0, 3.0, 4.0]
        )
        manager.publish_beacon("vertex:test", beacon)
        
        # Perform gossip round
        manager._perform_gossip_round()
        
        # Check messages were sent
        assert len(sent_messages) > 0
    
    def test_gossip_manager_beacon_deduplication(self):
        """Test that duplicate beacons are not processed twice."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Create beacon
        beacon = Beacon(
            key="vertex:test",
            primes=[2, 3, 5, 7],
            phase_angles=[1.0, 2.0, 3.0, 4.0]
        )
        
        # Create message
        message = GossipMessage(
            message_type='beacon',
            sender_id=hashlib.sha1(b"sender").digest(),
            payload=beacon.serialize()
        )
        
        # Receive message twice
        manager.receive_message(message.sender_id, message)
        initial_beacon_count = manager.dht.get_beacon_count()
        
        manager.receive_message(message.sender_id, message)
        
        # Beacon count should not increase (Bloom filter catches duplicate)
        # Note: Bloom filters may have false positives, but no false negatives
        assert manager.dht.get_beacon_count() == initial_beacon_count
    
    def test_gossip_manager_repr(self):
        """Test gossip manager string representation."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        repr_str = repr(manager)
        
        assert "GossipManager" in repr_str
        assert "node=" in repr_str
        assert "beacons=" in repr_str
        assert "running=" in repr_str
    
    def test_gossip_manager_multiple_beacons(self):
        """Test managing multiple beacons."""
        dht = KademliaDHT(address="localhost:8000")
        manager = GossipManager(dht)
        
        # Publish multiple beacons with different prime sets
        prime_sets = [
            [2, 3, 5, 7],
            [11, 13, 17, 19],
            [23, 29, 31, 37],
            [41, 43, 47, 53],
            [59, 61, 67, 71]
        ]
        
        for i, primes in enumerate(prime_sets):
            beacon = Beacon(
                key=f"vertex:test{i}",
                primes=primes,
                phase_angles=[float(j) for j in range(len(primes))]
            )
            manager.publish_beacon(f"vertex:test{i}", beacon)
        
        # Check all stored locally
        stats = manager.get_stats()
        assert stats['local_beacons'] == 5
        # DHT stores by prime hash, so should have 5 different beacons
        assert stats['dht_beacons'] == 5
