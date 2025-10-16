/**
 * ResonaCompress - File compression using phase-encoding principles
 * 
 * Main compression engine that coordinates prime selection,
 * phase encoding, and data reconstruction
 */

import * as fs from 'fs';
import * as crypto from 'crypto';
import { PrimeSelector } from './PrimeSelector';
import { PhaseEncoder, EncodedData } from './PhaseEncoder';

export interface CompressionOptions {
  primeCount?: number;    // Number of primes to use (default: 48)
  taperAlpha?: number;    // Taper parameter (default: 0.1)
  useSecret?: boolean;    // Use secret for encryption (default: false)
}

export interface CompressionResult {
  compressedSize: number;
  originalSize: number;
  compressionRatio: number;
  encodingTime: number;
}

export interface DecompressionResult {
  data: Buffer;
  decodingTime: number;
  checksumValid: boolean;
}

export class ResonaCompress {
  private primeSelector: PrimeSelector;
  private phaseEncoder: PhaseEncoder;

  constructor() {
    this.primeSelector = new PrimeSelector();
    this.phaseEncoder = new PhaseEncoder();
  }

  /**
   * Compress a file using phase encoding
   * 
   * @param inputPath - Path to input file
   * @param outputPath - Path to output compressed file
   * @param options - Compression options
   * @returns Compression statistics
   */
  async compressFile(
    inputPath: string,
    outputPath: string,
    options: CompressionOptions = {}
  ): Promise<CompressionResult> {
    const startTime = Date.now();

    // Read input file
    const data = fs.readFileSync(inputPath);
    const originalSize = data.length;

    // Generate deterministic seed from file hash
    const fileHash = crypto.createHash('sha256').update(data).digest();

    // Select primes
    const primeCount = options.primeCount ?? 48;
    const primes = this.primeSelector.selectPrimes(fileHash, primeCount);

    // Generate secret if encryption requested
    let secret: Buffer | undefined;
    if (options.useSecret) {
      secret = crypto.randomBytes(32);
    }

    // Encode data
    const encoder = new PhaseEncoder(options.taperAlpha);
    const encoded = encoder.encode(data, primes, secret);

    // Create compressed format
    const compressed = this.serializeEncoded(encoded, secret);

    // Write output file
    fs.writeFileSync(outputPath, compressed);

    const encodingTime = Date.now() - startTime;
    const compressedSize = compressed.length;
    const compressionRatio = originalSize / compressedSize;

    return {
      compressedSize,
      originalSize,
      compressionRatio,
      encodingTime,
    };
  }

  /**
   * Decompress a file
   * 
   * @param inputPath - Path to compressed file
   * @param outputPath - Path to output decompressed file
   * @returns Decompression statistics
   */
  async decompressFile(
    inputPath: string,
    outputPath: string
  ): Promise<DecompressionResult> {
    const startTime = Date.now();

    // Read compressed file
    const compressed = fs.readFileSync(inputPath);

    // Deserialize
    const { encoded, secret } = this.deserializeEncoded(compressed);

    // Decode data
    const decoder = new PhaseEncoder(); // Use default taper
    const data = decoder.decode(encoded, secret);

    // Verify checksum
    const actualChecksum = crypto.createHash('sha256').update(data).digest('hex');
    const checksumValid = actualChecksum === encoded.metadata.checksum;

    if (!checksumValid) {
      console.warn('Warning: Checksum mismatch! Data may be corrupted.');
    }

    // Write output file
    fs.writeFileSync(outputPath, data);

    const decodingTime = Date.now() - startTime;

    return {
      data,
      decodingTime,
      checksumValid,
    };
  }

  /**
   * Serialize encoded data to binary format
   * 
   * Format:
   * - Magic bytes (4 bytes): "RESC"
   * - Version (1 byte): 1
   * - Has secret flag (1 byte): 0 or 1
   * - Secret (32 bytes, if present)
   * - Prime count (2 bytes)
   * - Primes (prime_count * 2 bytes)
   * - Original size (4 bytes)
   * - Symbol count (4 bytes)
   * - Checksum (32 bytes)
   * - Phase count (4 bytes)
   * - Phases (phase_count * 8 bytes, as doubles)
   */
  private serializeEncoded(encoded: EncodedData, secret?: Buffer): Buffer {
    const { phases, primes, metadata } = encoded;

    // Calculate total size
    const magicSize = 4;
    const versionSize = 1;
    const secretFlagSize = 1;
    const secretSize = secret ? 32 : 0;
    const primeCountSize = 2;
    const primesSize = primes.length * 2;
    const metadataSize = 4 + 4 + 32; // originalSize + symbolCount + checksum
    const phaseCountSize = 4;
    const phasesSize = phases.length * 8;

    const totalSize =
      magicSize +
      versionSize +
      secretFlagSize +
      secretSize +
      primeCountSize +
      primesSize +
      metadataSize +
      phaseCountSize +
      phasesSize;

    const buffer = Buffer.alloc(totalSize);
    let offset = 0;

    // Magic bytes
    buffer.write('RESC', offset, 'ascii');
    offset += 4;

    // Version
    buffer.writeUInt8(1, offset);
    offset += 1;

    // Secret flag
    buffer.writeUInt8(secret ? 1 : 0, offset);
    offset += 1;

    // Secret (if present)
    if (secret) {
      secret.copy(buffer, offset);
      offset += 32;
    }

    // Prime count
    buffer.writeUInt16BE(primes.length, offset);
    offset += 2;

    // Primes
    for (const prime of primes) {
      buffer.writeUInt16BE(prime, offset);
      offset += 2;
    }

    // Metadata
    buffer.writeUInt32BE(metadata.originalSize, offset);
    offset += 4;
    buffer.writeUInt32BE(metadata.symbolCount, offset);
    offset += 4;
    buffer.write(metadata.checksum, offset, 'hex');
    offset += 32;

    // Phase count
    buffer.writeUInt32BE(phases.length, offset);
    offset += 4;

    // Phases (as doubles)
    for (const phase of phases) {
      buffer.writeDoubleBE(phase, offset);
      offset += 8;
    }

    return buffer;
  }

  /**
   * Deserialize binary format to encoded data
   */
  private deserializeEncoded(buffer: Buffer): {
    encoded: EncodedData;
    secret?: Buffer;
  } {
    let offset = 0;

    // Read magic bytes
    const magic = buffer.toString('ascii', offset, offset + 4);
    offset += 4;
    if (magic !== 'RESC') {
      throw new Error('Invalid file format: magic bytes mismatch');
    }

    // Read version
    const version = buffer.readUInt8(offset);
    offset += 1;
    if (version !== 1) {
      throw new Error(`Unsupported version: ${version}`);
    }

    // Read secret flag
    const hasSecret = buffer.readUInt8(offset) === 1;
    offset += 1;

    // Read secret
    let secret: Buffer | undefined;
    if (hasSecret) {
      secret = buffer.subarray(offset, offset + 32);
      offset += 32;
    }

    // Read prime count
    const primeCount = buffer.readUInt16BE(offset);
    offset += 2;

    // Read primes
    const primes: number[] = [];
    for (let i = 0; i < primeCount; i++) {
      primes.push(buffer.readUInt16BE(offset));
      offset += 2;
    }

    // Read metadata
    const originalSize = buffer.readUInt32BE(offset);
    offset += 4;
    const symbolCount = buffer.readUInt32BE(offset);
    offset += 4;
    const checksum = buffer.toString('hex', offset, offset + 32);
    offset += 32;

    // Read phase count
    const phaseCount = buffer.readUInt32BE(offset);
    offset += 4;

    // Read phases
    const phases: number[] = [];
    for (let i = 0; i < phaseCount; i++) {
      phases.push(buffer.readDoubleBE(offset));
      offset += 8;
    }

    return {
      encoded: {
        phases,
        primes,
        metadata: {
          originalSize,
          symbolCount,
          checksum,
        },
      },
      secret,
    };
  }
}
