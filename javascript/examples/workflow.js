#!/usr/bin/env node
/**
 * Complete workflow example
 * 
 * Demonstrates put and get operations in a single session.
 */

const { Client, PhaseKey } = require('../dist/index');

console.log('╔══════════════════════════════════════════════════════════╗');
console.log('║  ResonaGraph JavaScript - Complete Workflow Example     ║');
console.log('╚══════════════════════════════════════════════════════════╝\n');

// Initialize client
const client = new Client('http://localhost:8443');
console.log('✓ Client initialized\n');

// Create phase key
const phaseKey = PhaseKey.fromPassphrase('my-secret-passphrase');
console.log('✓ Phase key created\n');

// Example 1: Store and retrieve user data
console.log('Example 1: User Data');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
const userData = {
  name: 'Alice',
  email: 'alice@example.com',
  age: 30,
  interests: ['quantum computing', 'graph databases'],
};

const beacon1 = client.put('user:alice', userData, phaseKey, {
  kPrimes: 48,
  taperAlpha: 0.1,
});
console.log('✓ Stored user data');
console.log(`  Key: ${beacon1.key}`);
console.log(`  Primes: ${beacon1.primes.length}`);

const result1 = client.get('user:alice', phaseKey);
console.log('✓ Retrieved user data');
console.log(`  Converged: ${result1.metrics.converged}`);
console.log(`  Iterations: ${result1.metrics.iterations}`);
console.log(`  Lock time: ${result1.metrics.metrics.lockTime}ms\n`);

// Example 2: Store and retrieve different data
console.log('Example 2: Product Data');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
const productData = {
  id: 'prod-123',
  name: 'ResonaGraph License',
  price: 99.99,
  available: true,
};

const beacon2 = client.put('product:123', productData, phaseKey, {
  kPrimes: 32, // Use fewer primes for faster operations
  taperAlpha: 0.05,
});
console.log('✓ Stored product data');
console.log(`  Key: ${beacon2.key}`);
console.log(`  Primes: ${beacon2.primes.length}`);

const result2 = client.get('product:123', phaseKey);
console.log('✓ Retrieved product data');
console.log(`  Converged: ${result2.metrics.converged}`);
console.log(`  Iterations: ${result2.metrics.iterations}`);
console.log(`  Lock time: ${result2.metrics.metrics.lockTime}ms\n`);

// Show statistics
console.log('Client Statistics');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
const stats = client.getStats();
console.log(`  Endpoint: ${stats.endpoint}`);
console.log(`  Stored keys: ${stats.storedKeys}`);
console.log(`  Prime cache size: ${stats.primeCacheSize} primes\n`);

console.log('✓ All operations completed successfully!\n');
