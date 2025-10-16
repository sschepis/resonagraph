/**
 * Tests for PrimeSelector
 */

import { PrimeSelector } from '../core/PrimeSelector';

describe('PrimeSelector', () => {
  let selector: PrimeSelector;

  beforeEach(() => {
    selector = new PrimeSelector();
  });

  test('should select default number of primes', () => {
    const primes = selector.selectPrimes('test-key');
    expect(primes.length).toBe(48); // Default k_primes
  });

  test('should select specified number of primes', () => {
    const primes = selector.selectPrimes('test-key', 32);
    expect(primes.length).toBe(32);
  });

  test('should select primes deterministically', () => {
    const primes1 = selector.selectPrimes('test-key', 32);
    const primes2 = selector.selectPrimes('test-key', 32);
    
    expect(primes1).toEqual(primes2);
  });

  test('should select different primes for different keys', () => {
    const primes1 = selector.selectPrimes('key-1', 32);
    const primes2 = selector.selectPrimes('key-2', 32);
    
    expect(primes1).not.toEqual(primes2);
  });

  test('should return sorted primes', () => {
    const primes = selector.selectPrimes('test-key', 32);
    const sorted = [...primes].sort((a, b) => a - b);
    
    expect(primes).toEqual(sorted);
  });

  test('should validate k_primes range', () => {
    expect(() => selector.selectPrimes('key', 20)).toThrow(); // Too low
    expect(() => selector.selectPrimes('key', 70)).toThrow(); // Too high
  });

  test('should have prime cache', () => {
    const cacheSize = selector.getCacheSize();
    expect(cacheSize).toBeGreaterThan(1000);
  });

  test('should compute product of primes', () => {
    const primes = [2, 3, 5];
    const product = PrimeSelector.getProduct(primes);
    expect(product).toBe(BigInt(30));
  });

  test('should check product sufficiency', () => {
    const primes = [2, 3, 5, 7, 11]; // Product = 2310
    const isSufficient = PrimeSelector.checkProductSufficiency(primes, 1);
    expect(isSufficient).toBe(true); // 2310 > 2^8 = 256
  });
});
