#!/usr/bin/env node
/**
 * ResonaGraph CLI tool
 * 
 * Command-line interface for interacting with ResonaGraph.
 */

import { Command } from 'commander';
import { Client, PhaseKey } from './index';
import * as fs from 'fs';

const program = new Command();

program
  .name('resonagraph')
  .description('ResonaGraph CLI - Prime-Resonant Graph Database')
  .version('0.1.0');

// Put command
program
  .command('put')
  .description('Store data in ResonaGraph')
  .argument('<key>', 'Unique key for the data')
  .argument('<data>', 'JSON data to store')
  .option('-e, --endpoint <url>', 'API endpoint', 'http://localhost:8443')
  .option('-k, --key <secret>', 'Phase key secret', 'default-secret-key')
  .option('-p, --primes <number>', 'Number of primes (32-64)', '48')
  .option('-a, --alpha <number>', 'Taper alpha (0.05-0.15)', '0.1')
  .action((key: string, data: string, options: any) => {
    try {
      const client = new Client(options.endpoint);
      const phaseKey = PhaseKey.fromPassphrase(options.key);
      const payload = JSON.parse(data);
      
      const beacon = client.put(key, payload, phaseKey, {
        kPrimes: parseInt(options.primes),
        taperAlpha: parseFloat(options.alpha),
      });
      
      console.log('Data stored successfully!');
      console.log('Beacon:', JSON.stringify(beacon, null, 2));
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

// Get command
program
  .command('get')
  .description('Retrieve data from ResonaGraph')
  .argument('<key>', 'Unique key for the data')
  .option('-e, --endpoint <url>', 'API endpoint', 'http://localhost:8443')
  .option('-k, --key <secret>', 'Phase key secret', 'default-secret-key')
  .action((key: string, options: any) => {
    try {
      const client = new Client(options.endpoint);
      const phaseKey = PhaseKey.fromPassphrase(options.key);
      
      const result = client.get(key, phaseKey);
      
      console.log('Data retrieved successfully!');
      console.log('Payload:', JSON.stringify(result.payload, null, 2));
      console.log('\nMetrics:');
      console.log(`  Converged: ${result.metrics.converged}`);
      console.log(`  Iterations: ${result.metrics.iterations}`);
      console.log(`  Lock time: ${result.metrics.metrics.lockTime}ms`);
      console.log(`  Final overlap: ${result.metrics.finalOverlap.toFixed(4)}`);
      console.log(`  Final entropy: ${result.metrics.finalEntropy.toFixed(6)}`);
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

// Stats command
program
  .command('stats')
  .description('Show client statistics')
  .option('-e, --endpoint <url>', 'API endpoint', 'http://localhost:8443')
  .action((options: any) => {
    try {
      const client = new Client(options.endpoint);
      const stats = client.getStats();
      
      console.log('ResonaGraph Client Statistics:');
      console.log(`  Endpoint: ${stats.endpoint}`);
      console.log(`  Stored keys: ${stats.storedKeys}`);
      console.log(`  Prime cache size: ${stats.primeCacheSize}`);
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

// Generate key command
program
  .command('genkey')
  .description('Generate a new phase key')
  .option('-o, --output <file>', 'Output file for key')
  .action((options: any) => {
    try {
      const phaseKey = PhaseKey.generate();
      const keyHex = phaseKey.getBytes().toString('hex');
      
      if (options.output) {
        fs.writeFileSync(options.output, keyHex);
        console.log(`Key generated and saved to ${options.output}`);
      } else {
        console.log('Generated key (hex):');
        console.log(keyHex);
        console.log('\nKeep this key secure!');
      }
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

program.parse();
