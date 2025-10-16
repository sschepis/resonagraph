/**
 * Tests for PhaseKey
 */

import { PhaseKey } from '../core/PhaseKey';

describe('PhaseKey', () => {
  test('should create from passphrase', () => {
    const key = PhaseKey.fromPassphrase('test-passphrase');
    expect(key).toBeInstanceOf(PhaseKey);
    expect(key.getBytes().length).toBe(32);
  });

  test('should create from secret buffer', () => {
    const secret = Buffer.alloc(32);
    const key = PhaseKey.fromSecret(secret);
    expect(key).toBeInstanceOf(PhaseKey);
  });

  test('should generate random key', () => {
    const key1 = PhaseKey.generate();
    const key2 = PhaseKey.generate();
    
    expect(key1.getBytes()).not.toEqual(key2.getBytes());
  });

  test('should derive child keys', () => {
    const rootKey = PhaseKey.fromPassphrase('root-key');
    const child1 = rootKey.deriveKey('topic-1');
    const child2 = rootKey.deriveKey('topic-2');
    
    expect(child1.getBytes()).not.toEqual(child2.getBytes());
  });

  test('should compute HMAC', () => {
    const key = PhaseKey.fromPassphrase('test-key');
    const data = Buffer.from('test-data');
    const hmac = key.computeHMAC(data);
    
    expect(hmac).toBeInstanceOf(Buffer);
    expect(hmac.length).toBe(32); // SHA-256 output
  });

  test('should track creation time', () => {
    const key = PhaseKey.generate();
    const createdAt = key.getCreatedAt();
    
    expect(createdAt).toBeInstanceOf(Date);
    expect(createdAt.getTime()).toBeLessThanOrEqual(Date.now());
  });

  test('should detect when rotation needed', () => {
    const key = PhaseKey.generate();
    expect(key.shouldRotate()).toBe(false);
  });

  test('should throw on invalid key length', () => {
    const invalidKey = Buffer.alloc(16); // Too short
    expect(() => new PhaseKey(invalidKey)).toThrow();
  });
});
