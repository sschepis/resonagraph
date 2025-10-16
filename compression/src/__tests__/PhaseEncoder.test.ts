/**
 * Tests for PhaseEncoder
 */

import { PhaseEncoder } from '../PhaseEncoder';
import * as crypto from 'crypto';

describe('PhaseEncoder', () => {
  let encoder: PhaseEncoder;

  beforeEach(() => {
    encoder = new PhaseEncoder();
  });

  test('should encode and decode simple data', () => {
    const data = Buffer.from('Hello');
    const primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47];

    const encoded = encoder.encode(data, primes);
    const decoded = encoder.decode(encoded);

    expect(decoded.toString()).toBe('Hello');
  });

  test('should encode with correct structure', () => {
    const data = Buffer.from('Test');
    const primes = [2, 3, 5, 7, 11];

    const encoded = encoder.encode(data, primes);

    expect(encoded.phases.length).toBe(data.length * primes.length);
    expect(encoded.primes).toEqual(primes);
    expect(encoded.metadata.originalSize).toBe(data.length);
    expect(encoded.metadata.symbolCount).toBe(data.length);
    expect(encoded.metadata.checksum).toBeTruthy();
  });

  test('should produce consistent checksums', () => {
    const data = Buffer.from('Test data');
    const primes = [2, 3, 5, 7, 11];

    const encoded1 = encoder.encode(data, primes);
    const encoded2 = encoder.encode(data, primes);

    expect(encoded1.metadata.checksum).toBe(encoded2.metadata.checksum);
  });

  test('should encode and decode with secret', () => {
    const data = Buffer.from('Secret message');
    const primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37];
    const secret = crypto.randomBytes(32);

    const encoded = encoder.encode(data, primes, secret);
    const decoded = encoder.decode(encoded, secret);

    expect(decoded.toString()).toBe('Secret message');
  });

  test('should handle empty data', () => {
    const data = Buffer.from('');
    const primes = [2, 3, 5];

    const encoded = encoder.encode(data, primes);
    const decoded = encoder.decode(encoded);

    expect(decoded.length).toBe(0);
  });

  test('should handle single byte', () => {
    const data = Buffer.from([42]);
    const primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29];

    const encoded = encoder.encode(data, primes);
    const decoded = encoder.decode(encoded);

    expect(decoded[0]).toBe(42);
  });

  test('should handle all byte values', () => {
    // Test a range of byte values
    const data = Buffer.from([0, 1, 127, 128, 255]);
    const primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47];

    const encoded = encoder.encode(data, primes);
    const decoded = encoder.decode(encoded);

    expect(Array.from(decoded)).toEqual([0, 1, 127, 128, 255]);
  });
});
