"""
Tests for Kademlia DHT implementation.

Tests DHT node discovery, routing, and beacon storage
according to copilot-instructions.md Section 7 (Testing Strategies).
"""

import pytest
import hashlib
import time

from resonagraph.gossip.dht import (
    Node,
    KBucket,
    BloomFilter,
    KademliaDHT,
    compute_prime_hash,
    K_BUCKET_SIZE,
    ALPHA,
    ID_BITS
)


class TestNode:
    """Test Node class."""
    
    def test_node_creation(self):
        """Test basic node creation."""
        node_id = hashlib.sha1(b"test_node").digest()
        node = Node(node_id=node_id, address="192.168.1.1:8000")
        
        assert node.node_id == node_id
        assert node.address == "192.168.1.1:8000"
        assert node.last_seen > 0
    
    def test_node_distance_to(self):
        """Test XOR distance calculation."""
        node1_id = b'\x00' * 20
        node2_id = b'\x00' * 19 + b'\x01'  # Last byte is 1
        
        node1 = Node(node_id=node1_id, address="addr1")
        distance = node1.distance_to(node2_id)
        
        # Distance should be 1 (XOR of last byte: \x00 XOR \x01 = \x01)
        assert distance == 1
    
    def test_node_distance_symmetric(self):
        """Test that distance is symmetric (XOR property)."""
        node1_id = hashlib.sha1(b"node1").digest()
        node2_id = hashlib.sha1(b"node2").digest()
        
        node1 = Node(node_id=node1_id, address="addr1")
        node2 = Node(node_id=node2_id, address="addr2")
        
        dist1 = node1.distance_to(node2_id)
        dist2 = node2.distance_to(node1_id)
        
        assert dist1 == dist2
    
    def test_node_equality(self):
        """Test node equality based on ID."""
        node_id = hashlib.sha1(b"test").digest()
        node1 = Node(node_id=node_id, address="addr1")
        node2 = Node(node_id=node_id, address="addr2")
        
        assert node1 == node2  # Same ID
    
    def test_node_hash(self):
        """Test that nodes can be hashed (for use in sets)."""
        node_id = hashlib.sha1(b"test").digest()
        node = Node(node_id=node_id, address="addr1")
        
        node_set = {node}
        assert node in node_set


class TestKBucket:
    """Test K-bucket implementation."""
    
    def test_kbucket_creation(self):
        """Test basic k-bucket creation."""
        bucket = KBucket(min_distance=0, max_distance=100)
        
        assert bucket.min_distance == 0
        assert bucket.max_distance == 100
        assert len(bucket.nodes) == 0
    
    def test_kbucket_add_node(self):
        """Test adding nodes to bucket."""
        bucket = KBucket(min_distance=0, max_distance=100)
        node = Node(node_id=hashlib.sha1(b"node1").digest(), address="addr1")
        
        result = bucket.add_node(node)
        
        assert result is True
        assert len(bucket.nodes) == 1
        assert bucket.nodes[0] == node
    
    def test_kbucket_update_existing_node(self):
        """Test that adding existing node updates last_seen and moves to end."""
        bucket = KBucket(min_distance=0, max_distance=100)
        node_id = hashlib.sha1(b"node1").digest()
        
        node1 = Node(node_id=node_id, address="addr1")
        original_last_seen = node1.last_seen
        bucket.add_node(node1)
        
        time.sleep(0.01)
        node2 = Node(node_id=node_id, address="addr1", last_seen=time.time())
        bucket.add_node(node2)
        
        # Should still have only 1 node
        assert len(bucket.nodes) == 1
        # Last seen should be updated (more recent than original)
        assert bucket.nodes[0].last_seen >= node2.last_seen
    
    def test_kbucket_full(self):
        """Test that bucket rejects nodes when full."""
        bucket = KBucket(min_distance=0, max_distance=100, k=3)
        
        # Fill bucket
        for i in range(3):
            node = Node(node_id=hashlib.sha1(f"node{i}".encode()).digest(), 
                       address=f"addr{i}")
            assert bucket.add_node(node) is True
        
        # Try to add one more
        extra_node = Node(node_id=hashlib.sha1(b"extra").digest(), address="extra")
        assert bucket.add_node(extra_node) is False
        assert len(bucket.nodes) == 3
    
    def test_kbucket_remove_node(self):
        """Test removing node from bucket."""
        bucket = KBucket(min_distance=0, max_distance=100)
        node = Node(node_id=hashlib.sha1(b"node1").digest(), address="addr1")
        
        bucket.add_node(node)
        assert len(bucket.nodes) == 1
        
        result = bucket.remove_node(node.node_id)
        assert result is True
        assert len(bucket.nodes) == 0
    
    def test_kbucket_remove_nonexistent_node(self):
        """Test removing nonexistent node."""
        bucket = KBucket(min_distance=0, max_distance=100)
        node_id = hashlib.sha1(b"nonexistent").digest()
        
        result = bucket.remove_node(node_id)
        assert result is False


class TestBloomFilter:
    """Test Bloom filter implementation."""
    
    def test_bloom_filter_creation(self):
        """Test basic Bloom filter creation."""
        bf = BloomFilter(size=100, hash_count=3)
        
        assert bf.size == 100
        assert bf.hash_count == 3
        assert len(bf.bit_array) == 100
    
    def test_bloom_filter_add_and_contains(self):
        """Test adding items and checking membership."""
        bf = BloomFilter()
        item = b"test_item"
        
        # Item should not be in filter initially
        assert bf.contains(item) is False
        
        # Add item
        bf.add(item)
        
        # Item should now be in filter
        assert bf.contains(item) is True
    
    def test_bloom_filter_false_negatives_impossible(self):
        """Test that false negatives are impossible."""
        bf = BloomFilter()
        
        items = [f"item{i}".encode() for i in range(10)]
        
        for item in items:
            bf.add(item)
        
        # All items should be found
        for item in items:
            assert bf.contains(item) is True
    
    def test_bloom_filter_different_items(self):
        """Test with different items."""
        bf = BloomFilter()
        
        bf.add(b"item1")
        bf.add(b"item2")
        
        assert bf.contains(b"item1") is True
        assert bf.contains(b"item2") is True
        # Note: item3 might return True (false positive) but unlikely


class TestKademliaDHT:
    """Test Kademlia DHT implementation."""
    
    def test_dht_creation(self):
        """Test basic DHT creation."""
        dht = KademliaDHT(address="localhost:8000")
        
        assert dht.self_node.address == "localhost:8000"
        assert len(dht.self_node.node_id) == 20  # SHA-1 is 160 bits = 20 bytes
        assert len(dht.buckets) == ID_BITS
    
    def test_dht_creation_with_node_id(self):
        """Test DHT creation with specific node ID."""
        node_id = hashlib.sha1(b"test_node").digest()
        dht = KademliaDHT(node_id=node_id, address="localhost:8000")
        
        assert dht.self_node.node_id == node_id
    
    def test_dht_add_node(self):
        """Test adding nodes to DHT."""
        dht = KademliaDHT(address="localhost:8000")
        
        node = Node(
            node_id=hashlib.sha1(b"remote_node").digest(),
            address="192.168.1.1:8000"
        )
        
        result = dht.add_node(node)
        
        assert result is True
        assert dht.get_node_count() == 1
    
    def test_dht_reject_self_node(self):
        """Test that DHT rejects adding itself."""
        dht = KademliaDHT(address="localhost:8000")
        
        result = dht.add_node(dht.self_node)
        
        assert result is False
        assert dht.get_node_count() == 0
    
    def test_dht_find_closest_nodes(self):
        """Test finding closest nodes."""
        dht = KademliaDHT(address="localhost:8000")
        
        # Add some nodes
        for i in range(10):
            node = Node(
                node_id=hashlib.sha1(f"node{i}".encode()).digest(),
                address=f"192.168.1.{i}:8000"
            )
            dht.add_node(node)
        
        # Find closest nodes to a target
        target_id = hashlib.sha1(b"target").digest()
        closest = dht.find_closest_nodes(target_id, count=5)
        
        assert len(closest) <= 5
        
        # Verify they are sorted by distance
        if len(closest) > 1:
            distances = [node.distance_to(target_id) for node in closest]
            assert distances == sorted(distances)
    
    def test_dht_store_and_lookup_beacon(self):
        """Test storing and looking up beacons."""
        dht = KademliaDHT(address="localhost:8000")
        
        prime_hash = hashlib.sha1(b"2,3,5,7").digest()
        beacon_data = b"beacon_payload"
        
        # Store beacon
        dht.store_beacon(prime_hash, beacon_data)
        
        # Lookup beacon
        result = dht.lookup_beacon(prime_hash)
        
        assert result == beacon_data
        assert dht.get_beacon_count() == 1
    
    def test_dht_has_beacon_bloom_filter(self):
        """Test beacon deduplication with Bloom filter."""
        dht = KademliaDHT(address="localhost:8000")
        
        prime_hash = hashlib.sha1(b"2,3,5,7").digest()
        beacon_data = b"beacon_payload_with_enough_data"
        
        # Should not have beacon initially
        assert dht.has_beacon(prime_hash, beacon_data) is False
        
        # Store beacon
        dht.store_beacon(prime_hash, beacon_data)
        
        # Should now have beacon
        assert dht.has_beacon(prime_hash, beacon_data) is True
    
    def test_dht_iterative_find_node(self):
        """Test iterative node lookup."""
        dht = KademliaDHT(address="localhost:8000")
        
        # Add nodes
        for i in range(15):
            node = Node(
                node_id=hashlib.sha1(f"node{i}".encode()).digest(),
                address=f"192.168.1.{i}:8000"
            )
            dht.add_node(node)
        
        # Perform iterative lookup
        target_id = hashlib.sha1(b"target").digest()
        closest = dht.iterative_find_node(target_id)
        
        assert len(closest) <= K_BUCKET_SIZE
    
    def test_dht_get_bucket_index(self):
        """Test bucket index calculation."""
        dht = KademliaDHT(address="localhost:8000")
        
        # Distance 0 should go to bucket 0
        assert dht._get_bucket_index(0) == 0
        
        # Distance 1 should go to bucket 0
        assert dht._get_bucket_index(1) == 0
        
        # Distance 2-3 should go to bucket 1
        assert dht._get_bucket_index(2) == 1
        assert dht._get_bucket_index(3) == 1
        
        # Distance 4-7 should go to bucket 2
        assert dht._get_bucket_index(4) == 2
        assert dht._get_bucket_index(7) == 2
    
    def test_dht_repr(self):
        """Test DHT string representation."""
        dht = KademliaDHT(address="localhost:8000")
        repr_str = repr(dht)
        
        assert "KademliaDHT" in repr_str
        assert "nodes=" in repr_str
        assert "beacons=" in repr_str


class TestPrimeHash:
    """Test prime hash computation."""
    
    def test_compute_prime_hash(self):
        """Test computing prime hash."""
        primes = [2, 3, 5, 7, 11]
        prime_hash = compute_prime_hash(primes)
        
        assert len(prime_hash) == 20  # SHA-1 is 20 bytes
    
    def test_compute_prime_hash_deterministic(self):
        """Test that prime hash is deterministic."""
        primes = [2, 3, 5, 7, 11]
        
        hash1 = compute_prime_hash(primes)
        hash2 = compute_prime_hash(primes)
        
        assert hash1 == hash2
    
    def test_compute_prime_hash_order_independent(self):
        """Test that prime hash is order-independent (sorts primes)."""
        primes1 = [2, 3, 5, 7]
        primes2 = [7, 5, 3, 2]
        
        hash1 = compute_prime_hash(primes1)
        hash2 = compute_prime_hash(primes2)
        
        assert hash1 == hash2
    
    def test_compute_prime_hash_different_primes(self):
        """Test that different primes produce different hashes."""
        primes1 = [2, 3, 5, 7]
        primes2 = [11, 13, 17, 19]
        
        hash1 = compute_prime_hash(primes1)
        hash2 = compute_prime_hash(primes2)
        
        assert hash1 != hash2
