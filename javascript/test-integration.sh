#!/bin/bash
# Integration test for ResonaGraph JavaScript port
# This script demonstrates the full workflow: CLI, server, and library

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ResonaGraph JavaScript - Integration Test              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

cd /home/runner/work/resonagraph/resonagraph/javascript

# Build if not already built
if [ ! -d "dist" ]; then
    echo "Building TypeScript..."
    npm run build
fi

echo "1. Testing CLI - Generate Key"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
node dist/cli.js genkey
echo ""

echo "2. Testing CLI - Store Data"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
node dist/cli.js put 'user:alice' '{"name":"Alice","email":"alice@example.com","age":30}' \
    --key test-secret
echo ""

echo "3. Testing CLI - Retrieve Data"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
node dist/cli.js get 'user:alice' --key test-secret
echo ""

echo "4. Testing CLI - Statistics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
node dist/cli.js stats
echo ""

echo "5. Running Unit Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
npm test -- --verbose
echo ""

echo "✓ All integration tests passed!"
echo ""
