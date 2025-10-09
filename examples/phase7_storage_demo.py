#!/usr/bin/env python3
"""
Phase 7.5 Storage Layer Demo

Demonstrates the RocksDB storage backend with primary and secondary indexes.
"""

import tempfile
import shutil
import pickle
from resonagraph.storage import (
    StorageManager,
    ROCKSDB_AVAILABLE,
    ROCKSDB_LIBRARY
)
from resonagraph.core.phase_key import PhaseKey
import numpy as np


def demo_in_memory_storage():
    """Demonstrate in-memory storage."""
    print("=" * 60)
    print("IN-MEMORY STORAGE DEMO")
    print("=" * 60)
    
    # Create manager with in-memory backend
    manager = StorageManager(backend_type='memory')
    
    # Create primary index for beacons
    beacons = manager.create_primary_index('beacons')
    
    # Store some beacons
    print("\nStoring beacons...")
    for i in range(5):
        beacon_id = f"beacon_{i}".encode()
        beacon_data = {
            'id': i,
            'phase': float(i * 0.1),
            'residues': [2, 3, 5, 7, 11]
        }
        beacons.put(beacon_id, beacon_data)
    
    # Retrieve and display
    print("\nRetrieving beacons:")
    for i in range(5):
        beacon_id = f"beacon_{i}".encode()
        data = beacons.get(beacon_id)
        print(f"  {beacon_id.decode()}: phase={data['phase']:.2f}")
    
    # Scan all beacons
    print("\nScanning all beacons:")
    for key, value in beacons.scan():
        print(f"  {key.decode()}: {value}")
    
    # Display stats
    print("\nStorage statistics:")
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    manager.close()


def demo_rocksdb_storage():
    """Demonstrate RocksDB persistent storage."""
    if not ROCKSDB_AVAILABLE:
        print("\nRocksDB not available - skipping persistent storage demo")
        return
    
    print("\n" + "=" * 60)
    print(f"ROCKSDB STORAGE DEMO (using {ROCKSDB_LIBRARY})")
    print("=" * 60)
    
    # Create temporary directory for database
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create manager with RocksDB backend
        manager = StorageManager(
            backend_type='rocksdb',
            path=temp_dir,
            compression='lz4'
        )
        
        # Create primary index for data
        phase_keys = manager.create_primary_index('phase_keys')
        
        # Create secondary index for looking up by prime
        prime_index = manager.create_secondary_index('by_prime')
        
        print("\nStoring data with secondary index...")
        
        # Store some sample data
        for i in range(10):
            primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29][:i+3]
            
            key_id = f"key_{i}".encode()
            key_data = {
                'primes': primes,
                'count': len(primes),
                'sum': sum(primes)
            }
            
            # Store in primary index
            phase_keys.put(key_id, key_data)
            
            # Add secondary index entries for each prime
            # Use composite key: "prime:key_id" so each mapping is unique
            for prime in primes:
                secondary_key = f"{prime}:{i}".encode()
                prime_index.put(secondary_key, key_id)
        
        # Query by secondary index using scan with prefix
        print("\nQuerying data containing prime 7 (using secondary index scan):")
        found_keys = set()
        for sec_key, prim_key in prime_index.scan(prefix=b'7:'):
            if prim_key not in found_keys:
                found_keys.add(prim_key)
                data = phase_keys.get(prim_key)
                print(f"  {prim_key.decode()}: primes={data['primes']}")
        
        # Batch write example (using raw backend batch)
        print("\nDemonstrating batch write (raw backend):")
        namespace = b'primary:phase_keys:'
        with manager.batch_write() as batch:
            for i in range(5):
                key_id = f"batch_key_{i}".encode()
                full_key = namespace + key_id
                value = pickle.dumps({'batch': True, 'index': i})
                batch.put(full_key, value)
        
        print("  Batch write completed - 5 keys added")
        
        # Verify batch write worked
        batch_count = sum(1 for k, v in phase_keys.scan(prefix=b'batch_key_'))
        print(f"  Verified: found {batch_count} batch keys")
        
        # Display storage stats
        print("\nRocksDB statistics:")
        stats = manager.get_stats()
        for key, value in stats.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")
        
        # Close and reopen to demonstrate persistence
        print("\nTesting persistence...")
        manager.close()
        
        manager = StorageManager(
            backend_type='rocksdb',
            path=temp_dir
        )
        
        # Recreate the primary index (indexes are in-memory, data persists)
        phase_keys = manager.create_primary_index('phase_keys')
        
        print("  Reopened database successfully")
        print(f"  Found {sum(1 for _ in phase_keys.scan())} keys in persisted data")
        
        manager.close()
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def demo_performance_comparison():
    """Compare in-memory vs RocksDB performance."""
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)
    
    import time
    
    num_operations = 1000
    
    # Test in-memory
    print(f"\nIn-memory backend ({num_operations} operations):")
    manager = StorageManager(backend_type='memory')
    index = manager.create_primary_index('test')
    
    start = time.time()
    for i in range(num_operations):
        index.put(f"key_{i}".encode(), {'value': i})
    write_time = time.time() - start
    
    start = time.time()
    for i in range(num_operations):
        _ = index.get(f"key_{i}".encode())
    read_time = time.time() - start
    
    print(f"  Write: {write_time*1000:.2f}ms ({num_operations/write_time:.0f} ops/sec)")
    print(f"  Read:  {read_time*1000:.2f}ms ({num_operations/read_time:.0f} ops/sec)")
    
    manager.close()
    
    # Test RocksDB if available
    if ROCKSDB_AVAILABLE:
        temp_dir = tempfile.mkdtemp()
        try:
            print(f"\nRocksDB backend ({num_operations} operations):")
            manager = StorageManager(backend_type='rocksdb', path=temp_dir)
            index = manager.create_primary_index('test')
            
            start = time.time()
            for i in range(num_operations):
                index.put(f"key_{i}".encode(), {'value': i})
            write_time = time.time() - start
            
            start = time.time()
            for i in range(num_operations):
                _ = index.get(f"key_{i}".encode())
            read_time = time.time() - start
            
            print(f"  Write: {write_time*1000:.2f}ms ({num_operations/write_time:.0f} ops/sec)")
            print(f"  Read:  {read_time*1000:.2f}ms ({num_operations/read_time:.0f} ops/sec)")
            
            manager.close()
        finally:
            shutil.rmtree(temp_dir)


def main():
    """Run all storage demos."""
    print("\nResonaGraph Phase 7.5 Storage Layer Demo")
    print("=" * 60)
    
    # Demo 1: In-memory storage
    demo_in_memory_storage()
    
    # Demo 2: RocksDB storage
    demo_rocksdb_storage()
    
    # Demo 3: Performance comparison
    demo_performance_comparison()
    
    print("\n" + "=" * 60)
    print("Storage demo completed successfully!")
    print("=" * 60)


if __name__ == '__main__':
    main()