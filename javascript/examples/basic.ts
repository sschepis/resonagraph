/**
 * Basic ResonaGraph example
 * 
 * Demonstrates core put/get operations with phase encoding.
 */

import { Client, PhaseKey } from '../dist/index';

async function main() {
  console.log('╔══════════════════════════════════════════════════╗');
  console.log('║     ResonaGraph JavaScript - Basic Example      ║');
  console.log('╚══════════════════════════════════════════════════╝\n');

  // Initialize client
  const client = new Client('http://localhost:8443');
  console.log('✓ Client initialized');

  // Create phase key
  const phaseKey = PhaseKey.fromPassphrase('my-secret-passphrase');
  console.log('✓ Phase key created\n');

  // Store data
  console.log('Storing data...');
  const userData = {
    name: 'Alice',
    email: 'alice@example.com',
    age: 30,
    interests: ['quantum computing', 'graph databases'],
  };

  const beacon = client.put('user:alice', userData, phaseKey, {
    kPrimes: 48,
    taperAlpha: 0.1,
  });

  console.log('✓ Data stored successfully!');
  console.log(`  Key: ${beacon.key}`);
  console.log(`  Primes selected: ${beacon.primes.length}`);
  console.log(`  Epoch: ${beacon.epoch}`);
  console.log();

  // Retrieve data
  console.log('Retrieving data...');
  const result = client.get('user:alice', phaseKey);

  console.log('✓ Data retrieved successfully!');
  console.log('  Payload:', JSON.stringify(result.payload, null, 2));
  console.log('\nLock Metrics:');
  console.log(`  Converged: ${result.metrics.converged}`);
  console.log(`  Iterations: ${result.metrics.iterations}`);
  console.log(`  Lock time: ${result.metrics.metrics.lockTime}ms`);
  console.log(`  Final overlap: ${result.metrics.finalOverlap.toFixed(4)}`);
  console.log(`  Final entropy: ${result.metrics.finalEntropy.toFixed(6)}`);
  console.log();

  // Client stats
  const stats = client.getStats();
  console.log('Client Statistics:');
  console.log(`  Stored keys: ${stats.storedKeys}`);
  console.log(`  Prime cache size: ${stats.primeCacheSize} primes`);
  console.log();

  console.log('✓ Example completed successfully!\n');
}

main().catch((error) => {
  console.error('Error:', error.message);
  process.exit(1);
});
