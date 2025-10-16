#!/bin/bash
# ResonaCompress Demo Script
# 
# Demonstrates file compression using phase-encoding principles

set -e

echo "========================================="
echo "  ResonaCompress Demonstration"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "Error: Please run this from the compression directory"
    exit 1
fi

# Build if needed
if [ ! -d "dist" ]; then
    echo "Building ResonaCompress..."
    npm run build
    echo ""
fi

# Create a test file
echo "Creating test file..."
cat > /tmp/resonacompress-demo.txt << 'EOF'
ResonaGraph: Prime-Resonant Graph Database
==========================================

This is a demonstration of ResonaCompress, a file compression tool
that applies the phase-encoding principles of ResonaGraph to file
compression.

Key Concepts:
- Phase encoding in prime-indexed space
- Chinese Remainder Theorem for reconstruction
- Optional HMAC-based encryption
- Deterministic compression

While this creates larger files than traditional compression (due to
phase angle storage overhead), it demonstrates an innovative
application of distributed graph database concepts.

Each byte is encoded as 48 phase angles, requiring 384 bytes of storage
per original byte. The CRT guarantees exact reconstruction.
EOF

echo "✓ Test file created"
echo ""

# Show original file
echo "Original file content:"
echo "---------------------"
head -10 /tmp/resonacompress-demo.txt
echo "..."
echo ""

# Show file size
ORIG_SIZE=$(wc -c < /tmp/resonacompress-demo.txt)
echo "Original file size: $ORIG_SIZE bytes"
echo ""

# Compress the file
echo "Compressing with ResonaCompress..."
echo "------------------------------------"
node dist/cli.js compress /tmp/resonacompress-demo.txt
echo ""

# Show compressed file info
echo "Compressed file information:"
echo "------------------------------------"
node dist/cli.js info /tmp/resonacompress-demo.txt.resc
echo ""

# Decompress the file
echo "Decompressing file..."
echo "------------------------------------"
node dist/cli.js decompress /tmp/resonacompress-demo.txt.resc /tmp/resonacompress-demo-restored.txt
echo ""

# Verify integrity
echo "Verifying file integrity..."
if diff /tmp/resonacompress-demo.txt /tmp/resonacompress-demo-restored.txt > /dev/null; then
    echo "✓ Files match perfectly! Lossless compression verified."
else
    echo "✗ Files differ! Something went wrong."
    exit 1
fi
echo ""

# Compare with gzip
echo "Comparison with traditional compression:"
echo "----------------------------------------"
gzip -c /tmp/resonacompress-demo.txt > /tmp/resonacompress-demo.txt.gz
GZIP_SIZE=$(wc -c < /tmp/resonacompress-demo.txt.gz)
RESC_SIZE=$(wc -c < /tmp/resonacompress-demo.txt.resc)

echo "Original:      $ORIG_SIZE bytes"
echo "gzip:          $GZIP_SIZE bytes ($(echo "scale=2; $ORIG_SIZE / $GZIP_SIZE" | bc)x compression)"
echo "ResonaCompress: $RESC_SIZE bytes ($(echo "scale=2; $RESC_SIZE / $ORIG_SIZE" | bc)x expansion!)"
echo ""
echo "Note: ResonaCompress is a demonstration tool. Traditional algorithms"
echo "      are much more efficient for actual file compression."
echo ""

# Cleanup
echo "Cleaning up temporary files..."
rm -f /tmp/resonacompress-demo.txt
rm -f /tmp/resonacompress-demo.txt.resc
rm -f /tmp/resonacompress-demo.txt.gz
rm -f /tmp/resonacompress-demo-restored.txt

echo ""
echo "========================================="
echo "  Demonstration Complete!"
echo "========================================="
echo ""
echo "Try it yourself:"
echo "  node dist/cli.js compress <your-file>"
echo "  node dist/cli.js info <your-file>.resc"
echo "  node dist/cli.js decompress <your-file>.resc"
