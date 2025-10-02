# ResonaGraph Examples

This directory contains examples demonstrating ResonaGraph functionality.

## Phase 1: Foundation

### phase1_demo.py

Demonstrates the foundation layer implementation:

```bash
cd /home/runner/work/resonagraph/resonagraph
PYTHONPATH=. python examples/phase1_demo.py
```

Features demonstrated:
- Phase key management with HKDF
- Prime selection using hash-seeded Eratosthenes sieve
- Phase encoding with golden ratio (φ)
- Basic client SDK operations (put, get, query)
- Query language with resonance extensions (COHERE)

## Running Examples

To run examples, ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

Then run with PYTHONPATH set:

```bash
PYTHONPATH=. python examples/phase1_demo.py
```

Or install the package in development mode:

```bash
pip install -e .
python examples/phase1_demo.py
```
