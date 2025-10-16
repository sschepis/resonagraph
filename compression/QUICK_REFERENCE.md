# ResonaCompress Quick Reference

## Installation

```bash
cd compression
npm install
npm run build
```

## Basic Commands

### Compress a File
```bash
node dist/cli.js compress input.txt
# Creates: input.txt.resc
```

### Decompress a File
```bash
node dist/cli.js decompress input.txt.resc
# Creates: input.txt
```

### View File Info
```bash
node dist/cli.js info input.txt.resc
```

## Advanced Options

### Custom Prime Count (32-64)
```bash
node dist/cli.js compress file.txt -p 64
# More primes = larger file, better security
```

### Custom Taper Alpha (0.05-0.15)
```bash
node dist/cli.js compress file.txt -a 0.05
# Lower alpha = faster convergence
```

### Enable Encryption
```bash
node dist/cli.js compress file.txt -s
# Adds HMAC-based cryptographic binding
```

### Specify Output Path
```bash
node dist/cli.js compress input.txt output.resc
node dist/cli.js decompress input.resc output.txt
```

## Command Combinations

```bash
# High security compression
node dist/cli.js compress sensitive.txt -p 64 -a 0.15 -s

# Fast compression
node dist/cli.js compress quick.txt -p 32 -a 0.05

# View detailed info
node dist/cli.js info compressed.resc
```

## Example Workflow

```bash
# 1. Compress
node dist/cli.js compress document.pdf

# 2. Check info
node dist/cli.js info document.pdf.resc

# 3. Decompress to verify
node dist/cli.js decompress document.pdf.resc restored.pdf

# 4. Verify integrity
diff document.pdf restored.pdf
```

## Run Demo

```bash
./demo.sh
# Runs complete demonstration with comparison to gzip
```

## Programmatic API

```javascript
const { ResonaCompress } = require('./dist/index');

const compressor = new ResonaCompress();

// Compress
await compressor.compressFile('input.txt', 'output.resc', {
  primeCount: 48,
  taperAlpha: 0.1,
  useSecret: false
});

// Decompress
await compressor.decompressFile('output.resc', 'restored.txt');
```

## File Format

- Extension: `.resc`
- Format: Binary (custom format)
- Structure:
  - Header: Magic bytes "RESC" + version + flags
  - Prime data: Selected primes
  - Metadata: Size + checksum
  - Phase data: Encoded phase angles

## Important Notes

⚠️ **File Size**: Compressed files are ~384x LARGER than originals!

✅ **Lossless**: Guaranteed exact reconstruction via CRT

🎓 **Educational**: Demonstrates phase-encoding concepts, not for production

🔐 **Optional Encryption**: Built-in HMAC-based security

## Troubleshooting

### "Cannot find module"
```bash
npm run build
# Rebuild TypeScript files
```

### "No such file or directory"
```bash
# Check file path - use absolute or relative paths
ls -la yourfile.txt
```

### Checksum mismatch
```bash
# Verify file wasn't corrupted during transfer
# Try decompressing again
```

## Performance Tips

- **Smaller files** decompress faster (linear in file size)
- **Fewer primes** (32) = faster but less secure
- **More primes** (64) = slower but more secure
- **Default (48)** is balanced

## Further Reading

- [README.md](README.md) - Complete documentation
- [TECHNICAL_OVERVIEW.md](TECHNICAL_OVERVIEW.md) - Algorithm details
- [ResonaGraph](../README.md) - Parent project

## Support

File issues at: https://github.com/sschepis/resonagraph/issues
