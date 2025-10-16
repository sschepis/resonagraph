/**
 * Integration tests for ResonaCompress
 */

import { ResonaCompress } from '../ResonaCompress';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

describe('ResonaCompress Integration', () => {
  let compressor: ResonaCompress;
  let tempDir: string;

  beforeEach(() => {
    compressor = new ResonaCompress();
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'resonacompress-test-'));
  });

  afterEach(() => {
    // Clean up temp directory
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  test('should compress and decompress text file', async () => {
    const inputPath = path.join(tempDir, 'input.txt');
    const compressedPath = path.join(tempDir, 'compressed.resc');
    const outputPath = path.join(tempDir, 'output.txt');

    const testData = 'Hello, ResonaCompress! This is a test.';
    fs.writeFileSync(inputPath, testData);

    // Compress
    const compressResult = await compressor.compressFile(inputPath, compressedPath);
    expect(compressResult.originalSize).toBe(testData.length);
    expect(compressResult.compressedSize).toBeGreaterThan(0);
    expect(fs.existsSync(compressedPath)).toBe(true);

    // Decompress
    const decompressResult = await compressor.decompressFile(compressedPath, outputPath);
    expect(decompressResult.checksumValid).toBe(true);
    expect(fs.existsSync(outputPath)).toBe(true);

    // Verify content
    const outputData = fs.readFileSync(outputPath, 'utf-8');
    expect(outputData).toBe(testData);
  });

  test('should handle binary data', async () => {
    const inputPath = path.join(tempDir, 'binary.bin');
    const compressedPath = path.join(tempDir, 'binary.resc');
    const outputPath = path.join(tempDir, 'binary-out.bin');

    // Create binary test data
    const testData = Buffer.from([0, 1, 2, 127, 128, 255, 42, 100, 200]);
    fs.writeFileSync(inputPath, testData);

    // Compress and decompress
    await compressor.compressFile(inputPath, compressedPath);
    const result = await compressor.decompressFile(compressedPath, outputPath);

    expect(result.checksumValid).toBe(true);

    const outputData = fs.readFileSync(outputPath);
    expect(Buffer.compare(testData, outputData)).toBe(0);
  });

  test('should compress with custom options', async () => {
    const inputPath = path.join(tempDir, 'custom.txt');
    const compressedPath = path.join(tempDir, 'custom.resc');

    fs.writeFileSync(inputPath, 'Test data for custom options');

    const result = await compressor.compressFile(inputPath, compressedPath, {
      primeCount: 32,
      taperAlpha: 0.05,
      useSecret: true,
    });

    expect(result.compressedSize).toBeGreaterThan(0);
    expect(fs.existsSync(compressedPath)).toBe(true);
  });

  test('should handle empty file', async () => {
    const inputPath = path.join(tempDir, 'empty.txt');
    const compressedPath = path.join(tempDir, 'empty.resc');
    const outputPath = path.join(tempDir, 'empty-out.txt');

    fs.writeFileSync(inputPath, '');

    await compressor.compressFile(inputPath, compressedPath);
    const result = await compressor.decompressFile(compressedPath, outputPath);

    expect(result.data.length).toBe(0);
    expect(result.checksumValid).toBe(true);
  });

  test('should maintain file integrity through multiple operations', async () => {
    const inputPath = path.join(tempDir, 'multi.txt');
    const compressed1 = path.join(tempDir, 'multi1.resc');
    const output1 = path.join(tempDir, 'multi-out1.txt');
    const compressed2 = path.join(tempDir, 'multi2.resc');
    const output2 = path.join(tempDir, 'multi-out2.txt');

    const testData = 'Testing multiple compression cycles';
    fs.writeFileSync(inputPath, testData);

    // First cycle
    await compressor.compressFile(inputPath, compressed1);
    await compressor.decompressFile(compressed1, output1);

    // Second cycle
    await compressor.compressFile(output1, compressed2);
    const result = await compressor.decompressFile(compressed2, output2);

    expect(result.checksumValid).toBe(true);
    const finalData = fs.readFileSync(output2, 'utf-8');
    expect(finalData).toBe(testData);
  });
});
