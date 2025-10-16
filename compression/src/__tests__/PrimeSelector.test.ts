/**
 * Tests for PrimeSelector
 */

import { PrimeSelector } from '../PrimeSelector';

describe('PrimeSelector', () => {
  let selector: PrimeSelector;

  beforeEach(() => {
    selector = new PrimeSelector();
  });

  test('should generate primes', () => {
    const primeCount = selector.getPrimeCount();
    expect(primeCount).toBeGreaterThan(0);
    expect(primeCount).toBeGreaterThan(1000); // Should have many primes up to 10000
  });

  test('should select deterministic primes based on seed', () => {
    const seed = Buffer.from('test-seed');
    const primes1 = selector.selectPrimes(seed, 48);
    const primes2 = selector.selectPrimes(seed, 48);

    expect(primes1).toEqual(primes2);
    expect(primes1.length).toBe(48);
  });

  test('should select different primes for different seeds', () => {
    const seed1 = Buffer.from('seed-1');
    const seed2 = Buffer.from('seed-2');

    const primes1 = selector.selectPrimes(seed1, 48);
    const primes2 = selector.selectPrimes(seed2, 48);

    expect(primes1).not.toEqual(primes2);
  });

  test('should select unique primes', () => {
    const seed = Buffer.from('test-seed');
    const primes = selector.selectPrimes(seed, 48);

    const uniquePrimes = new Set(primes);
    expect(uniquePrimes.size).toBe(primes.length);
  });

  test('should return sorted primes', () => {
    const seed = Buffer.from('test-seed');
    const primes = selector.selectPrimes(seed, 48);

    const sorted = [...primes].sort((a, b) => a - b);
    expect(primes).toEqual(sorted);
  });

  test('should throw error if requesting too many primes', () => {
    const seed = Buffer.from('test-seed');
    const maxPrimes = selector.getPrimeCount();

    expect(() => {
      selector.selectPrimes(seed, maxPrimes + 1);
    }).toThrow();
  });
});
