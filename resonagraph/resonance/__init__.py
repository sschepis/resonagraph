"""
Resonance plane module for ResonaGraph.

Implements Phase 3 components from design.md Section 2.2.2:
- Probe synthesis: Generate probe states |Q⟩
- Locking dynamics: Iterative overlap computation
- Residue extraction: Phase difference measurement
- CRT reconstruction: Payload recovery

According to copilot-instructions.md Resonance Plane specifications.
"""

from resonagraph.resonance.probe import ProbeSynthesizer
from resonagraph.resonance.locking import ResonanceLock
from resonagraph.resonance.residue import ResidueExtractor

__all__ = [
    'ProbeSynthesizer',
    'ResonanceLock',
    'ResidueExtractor',
]
