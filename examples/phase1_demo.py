#!/usr/bin/env python3
"""
Example demonstrating ResonaGraph Phase 1 implementation.

This example shows:
1. Prime selection using hash-seeded Eratosthenes sieve
2. Phase encoding with golden ratio and HMAC
3. Phase key management with HKDF
4. Basic client SDK operations
"""

from resonagraph import Client, PhaseKey, Query

def main():
    print("=" * 70)
    print("ResonaGraph Phase 1 Example")
    print("=" * 70)
    print()
    
    # Step 1: Generate a phase key
    print("1. Phase Key Management")
    print("-" * 40)
    pk = PhaseKey.from_secret(b"my-secret-32-bytes-long______")
    print(f"✓ Phase key created: {pk}")
    
    # Derive topic-specific keys
    topic_key = PhaseKey.derive_topic_key(pk, "users")
    print(f"✓ Topic key derived for 'users': {topic_key}")
    print()
    
    # Step 2: Initialize client
    print("2. Client Initialization")
    print("-" * 40)
    client = Client("https://api.resonagraph.com/v1")
    print(f"✓ Client initialized with endpoint: {client.endpoint}")
    print()
    
    # Step 3: Encode and store data
    print("3. Data Encoding (put operation)")
    print("-" * 40)
    payload = {
        "name": "Alice",
        "email": "alice@example.com",
        "props": {
            "age": 30,
            "role": "engineer"
        }
    }
    
    beacon = client.put(
        key="vertex:user_123",
        payload=payload,
        phase_key=pk,
        options={"k_primes": 48, "taper_alpha": 0.05}
    )
    
    print(f"✓ Data encoded with {len(beacon['primes'])} primes")
    print(f"✓ Phase angles computed for each prime")
    print(f"✓ Sample primes: {beacon['primes'][:5]}...")
    print(f"✓ Options: k_primes={beacon['options']['k_primes']}, "
          f"taper_alpha={beacon['options']['taper_alpha']}")
    print()
    
    # Step 4: Demonstrate prime selection
    print("4. Prime Selection Details")
    print("-" * 40)
    from resonagraph.core.prime_selection import PrimeSelector
    
    selector = PrimeSelector(k_primes=32)
    primes = selector.select_primes("vertex:user_123")
    print(f"✓ Selected {len(primes)} primes for key 'vertex:user_123'")
    print(f"✓ First 10 primes: {primes[:10]}")
    print(f"✓ Prime selection is deterministic (same key → same primes)")
    
    # Verify product bound for CRT
    is_sufficient = selector.verify_product_bound(primes, byte_size=8)
    print(f"✓ Product bound check (8 bytes): {is_sufficient}")
    print()
    
    # Step 5: Demonstrate phase encoding
    print("5. Phase Encoding Details")
    print("-" * 40)
    from resonagraph.core.phase_encoding import PhaseEncoder, PHI, TWO_PI
    
    encoder = PhaseEncoder(taper_alpha=0.05)
    phase_angles = encoder.encode_payload(payload, primes[:5], pk.get_bytes())
    
    print(f"✓ Golden ratio φ = {PHI:.10f}")
    print(f"✓ Formula: θ_p = 2π(m_j mod p + α/φ + β/δ + HMAC(p||j, K))")
    print(f"✓ Encoded payload into phase angles for 5 primes:")
    for prime, angles in list(phase_angles.items())[:3]:
        print(f"  Prime {prime}: {len(angles)} angles, first: {angles[0]:.6f} rad")
    print()
    
    # Step 6: Query parsing
    print("6. Query Language")
    print("-" * 40)
    query = Query(
        "MATCH (u:User {id: 'user_123'})-[:FOLLOWS*1..2]->(f) "
        "COHERE ON u,f RETURN f.name"
    )
    parsed = query.parse()
    print(f"✓ Query: {query}")
    print(f"✓ Has COHERE extension: {parsed['has_cohere']}")
    print(f"✓ Has EPOCH WINDOW extension: {parsed['has_epoch_window']}")
    print()
    
    # Step 7: Summary
    print("7. Summary")
    print("-" * 40)
    print("✓ Phase 1 Foundation Complete!")
    print()
    print("Implemented:")
    print("  • Prime selection (Eratosthenes sieve)")
    print("  • Phase encoding (θ_p with golden ratio)")
    print("  • Phase key management (HKDF)")
    print("  • Client SDK (put/get/query operations)")
    print("  • Chinese Remainder Theorem (CRT)")
    print()
    print("Next phases:")
    print("  • Phase 2: Gossip Plane (QUIC, beacons, DHT)")
    print("  • Phase 3: Resonance Plane (locking, entropy)")
    print("  • Phase 4: REC (conflict resolution)")
    print("=" * 70)

if __name__ == "__main__":
    main()
