/**
 * Phase Key module for cryptographic access control.
 * 
 * According to design.md Section 5.1:
 * - HMAC-based cryptographic binding
 * - Key hierarchy via HKDF
 * - Rotate keys every 24h for security
 */

import * as crypto from 'crypto';

// Constants
const DEFAULT_KEY_LENGTH = 32; // 256 bits
const HKDF_ALGORITHM = 'sha256';
const HMAC_ALGORITHM = 'sha256';

export class PhaseKey {
  private keyBytes: Buffer;
  private createdAt: Date;

  /**
   * Create a PhaseKey from raw bytes.
   * 
   * @param keyBytes - 32-byte secret key
   */
  constructor(keyBytes: Buffer) {
    if (keyBytes.length !== DEFAULT_KEY_LENGTH) {
      throw new Error(`PhaseKey must be ${DEFAULT_KEY_LENGTH} bytes, got ${keyBytes.length}`);
    }
    this.keyBytes = keyBytes;
    this.createdAt = new Date();
  }

  /**
   * Create a PhaseKey from a secret buffer.
   * 
   * @param secret - Secret buffer (will be hashed if not 32 bytes)
   * @returns New PhaseKey instance
   */
  static fromSecret(secret: Buffer): PhaseKey {
    if (secret.length === DEFAULT_KEY_LENGTH) {
      return new PhaseKey(secret);
    }
    
    // Hash the secret to get 32 bytes
    const hash = crypto.createHash('sha256');
    hash.update(secret);
    return new PhaseKey(hash.digest());
  }

  /**
   * Create a PhaseKey from a passphrase string.
   * 
   * @param passphrase - String passphrase
   * @returns New PhaseKey instance
   */
  static fromPassphrase(passphrase: string): PhaseKey {
    return PhaseKey.fromSecret(Buffer.from(passphrase, 'utf-8'));
  }

  /**
   * Generate a random PhaseKey.
   * 
   * @returns New random PhaseKey instance
   */
  static generate(): PhaseKey {
    return new PhaseKey(crypto.randomBytes(DEFAULT_KEY_LENGTH));
  }

  /**
   * Derive a child key using HKDF.
   * 
   * @param info - Context information for key derivation
   * @returns New derived PhaseKey
   */
  deriveKey(info: string): PhaseKey {
    const salt = Buffer.alloc(DEFAULT_KEY_LENGTH); // Zero salt for deterministic derivation
    const derivedKey = crypto.hkdfSync(
      HKDF_ALGORITHM,
      this.keyBytes,
      salt,
      Buffer.from(info, 'utf-8'),
      DEFAULT_KEY_LENGTH
    );
    return new PhaseKey(Buffer.from(derivedKey));
  }

  /**
   * Compute HMAC for phase encoding.
   * 
   * @param data - Data to authenticate
   * @returns HMAC digest
   */
  computeHMAC(data: Buffer): Buffer {
    const hmac = crypto.createHmac(HMAC_ALGORITHM, this.keyBytes);
    hmac.update(data);
    return hmac.digest();
  }

  /**
   * Get the raw key bytes.
   * 
   * @returns Key bytes (copy)
   */
  getBytes(): Buffer {
    return Buffer.from(this.keyBytes);
  }

  /**
   * Get key creation timestamp.
   * 
   * @returns Creation date
   */
  getCreatedAt(): Date {
    return this.createdAt;
  }

  /**
   * Check if key should be rotated (older than 24 hours).
   * 
   * @returns true if key should be rotated
   */
  shouldRotate(): boolean {
    const age = Date.now() - this.createdAt.getTime();
    const DAY_MS = 24 * 60 * 60 * 1000;
    return age > DAY_MS;
  }
}
