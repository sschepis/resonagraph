/**
 * Tests for Client integration
 */

import { Client, PhaseKey } from '../index';

describe('Client', () => {
  let client: Client;
  let phaseKey: PhaseKey;

  beforeEach(() => {
    client = new Client('http://localhost:8443');
    phaseKey = PhaseKey.fromPassphrase('test-key');
  });

  test('should create client instance', () => {
    expect(client).toBeInstanceOf(Client);
  });

  test('should store and retrieve data', () => {
    const key = 'test:data';
    const payload = { name: 'Test', value: 42 };

    // Store data
    const beacon = client.put(key, payload, phaseKey);
    expect(beacon.key).toBe(key);
    expect(beacon.primes.length).toBe(48);

    // Retrieve data
    const result = client.get(key, phaseKey);
    expect(result.metrics.converged).toBe(true);
  });

  test('should use custom options', () => {
    const key = 'test:custom';
    const payload = { data: 'test' };

    const beacon = client.put(key, payload, phaseKey, {
      kPrimes: 32,
      taperAlpha: 0.05,
    });

    expect(beacon.primes.length).toBe(32);
  });

  test('should throw on missing key', () => {
    expect(() => client.get('nonexistent', phaseKey)).toThrow();
  });

  test('should return statistics', () => {
    const stats = client.getStats();
    expect(stats.endpoint).toBe('http://localhost:8443');
    expect(stats.primeCacheSize).toBeGreaterThan(0);
  });

  test('should handle multiple keys', () => {
    const key1 = 'user:alice';
    const key2 = 'user:bob';
    const payload1 = { name: 'Alice' };
    const payload2 = { name: 'Bob' };

    client.put(key1, payload1, phaseKey);
    client.put(key2, payload2, phaseKey);

    const stats = client.getStats();
    expect(stats.storedKeys).toBe(2);
  });
});
