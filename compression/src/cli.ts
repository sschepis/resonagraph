#!/usr/bin/env node
/**
 * ResonaCompress CLI
 * 
 * Command-line interface for file compression using phase-encoding
 */

import { Command } from 'commander';
import * as path from 'path';
import * as fs from 'fs';
import { ResonaCompress } from './ResonaCompress';

const program = new Command();

program
  .name('resonacompress')
  .description('File compression using ResonaGraph phase-encoding principles')
  .version('1.0.0');

program
  .command('compress')
  .description('Compress a file using phase encoding')
  .argument('<input>', 'Input file path')
  .argument('[output]', 'Output file path (defaults to <input>.resc)')
  .option('-p, --primes <count>', 'Number of primes to use (32-64)', '48')
  .option('-a, --alpha <value>', 'Taper alpha parameter (0.05-0.15)', '0.1')
  .option('-s, --secret', 'Use secret for encryption', false)
  .action(async (input: string, output: string | undefined, options: any) => {
    try {
      const inputPath = path.resolve(input);
      const outputPath = output
        ? path.resolve(output)
        : inputPath + '.resc';

      if (!fs.existsSync(inputPath)) {
        console.error(`Error: Input file not found: ${inputPath}`);
        process.exit(1);
      }

      const primeCount = parseInt(options.primes);
      const taperAlpha = parseFloat(options.alpha);

      if (primeCount < 32 || primeCount > 64) {
        console.error('Error: Prime count must be between 32 and 64');
        process.exit(1);
      }

      if (taperAlpha < 0.05 || taperAlpha > 0.15) {
        console.error('Error: Taper alpha must be between 0.05 and 0.15');
        process.exit(1);
      }

      console.log('ResonaCompress - File Compression');
      console.log('=================================');
      console.log(`Input:  ${inputPath}`);
      console.log(`Output: ${outputPath}`);
      console.log(`Primes: ${primeCount}`);
      console.log(`Alpha:  ${taperAlpha}`);
      console.log(`Secret: ${options.secret ? 'Yes' : 'No'}`);
      console.log('');

      const compressor = new ResonaCompress();
      const result = await compressor.compressFile(inputPath, outputPath, {
        primeCount,
        taperAlpha,
        useSecret: options.secret,
      });

      console.log('Compression Complete!');
      console.log('====================');
      console.log(`Original size:    ${result.originalSize.toLocaleString()} bytes`);
      console.log(`Compressed size:  ${result.compressedSize.toLocaleString()} bytes`);
      console.log(`Ratio:            ${result.compressionRatio.toFixed(2)}x`);
      console.log(`Time:             ${result.encodingTime}ms`);
      console.log('');
      console.log(`Saved to: ${outputPath}`);
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : String(error));
      process.exit(1);
    }
  });

program
  .command('decompress')
  .description('Decompress a .resc file')
  .argument('<input>', 'Input .resc file path')
  .argument('[output]', 'Output file path (defaults to <input> without .resc)')
  .action(async (input: string, output: string | undefined) => {
    try {
      const inputPath = path.resolve(input);
      
      let outputPath: string;
      if (output) {
        outputPath = path.resolve(output);
      } else {
        // Remove .resc extension
        if (inputPath.endsWith('.resc')) {
          outputPath = inputPath.slice(0, -5);
        } else {
          outputPath = inputPath + '.decompressed';
        }
      }

      if (!fs.existsSync(inputPath)) {
        console.error(`Error: Input file not found: ${inputPath}`);
        process.exit(1);
      }

      console.log('ResonaCompress - File Decompression');
      console.log('===================================');
      console.log(`Input:  ${inputPath}`);
      console.log(`Output: ${outputPath}`);
      console.log('');

      const compressor = new ResonaCompress();
      const result = await compressor.decompressFile(inputPath, outputPath);

      console.log('Decompression Complete!');
      console.log('======================');
      console.log(`Output size:      ${result.data.length.toLocaleString()} bytes`);
      console.log(`Checksum valid:   ${result.checksumValid ? 'Yes ✓' : 'No ✗'}`);
      console.log(`Time:             ${result.decodingTime}ms`);
      console.log('');
      console.log(`Saved to: ${outputPath}`);
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : String(error));
      process.exit(1);
    }
  });

program
  .command('info')
  .description('Display information about a compressed file')
  .argument('<file>', 'Compressed .resc file path')
  .action(async (file: string) => {
    try {
      const filePath = path.resolve(file);
      
      if (!fs.existsSync(filePath)) {
        console.error(`Error: File not found: ${filePath}`);
        process.exit(1);
      }

      const data = fs.readFileSync(filePath);
      
      // Parse header
      let offset = 0;
      const magic = data.toString('ascii', 0, 4);
      offset += 4;
      
      if (magic !== 'RESC') {
        console.error('Error: Not a valid ResonaCompress file');
        process.exit(1);
      }

      const version = data.readUInt8(offset);
      offset += 1;

      const hasSecret = data.readUInt8(offset) === 1;
      offset += 1;

      if (hasSecret) {
        offset += 32; // Skip secret
      }

      const primeCount = data.readUInt16BE(offset);
      offset += 2;

      // Skip primes
      offset += primeCount * 2;

      const originalSize = data.readUInt32BE(offset);
      offset += 4;
      const symbolCount = data.readUInt32BE(offset);
      offset += 4;
      const checksum = data.toString('hex', offset, offset + 32);
      offset += 32;

      const phaseCount = data.readUInt32BE(offset);

      console.log('ResonaCompress File Information');
      console.log('===============================');
      console.log(`File:             ${filePath}`);
      console.log(`Version:          ${version}`);
      console.log(`Encrypted:        ${hasSecret ? 'Yes' : 'No'}`);
      console.log(`Prime count:      ${primeCount}`);
      console.log(`Original size:    ${originalSize.toLocaleString()} bytes`);
      console.log(`Symbol count:     ${symbolCount.toLocaleString()}`);
      console.log(`Phase count:      ${phaseCount.toLocaleString()}`);
      console.log(`Checksum:         ${checksum.substring(0, 16)}...`);
      console.log(`Compressed size:  ${data.length.toLocaleString()} bytes`);
      console.log(`Compression:      ${(originalSize / data.length).toFixed(2)}x`);
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : String(error));
      process.exit(1);
    }
  });

program.parse();
