"""
ResonaGraph - Prime-Resonant Graph Database

A next-generation distributed graph database implementing phase-modulated 
superpositions over prime-based Hilbert spaces for non-local data reconstruction.

Core Innovation:
- Compact "resonance beacons" for coordination (80-90% bandwidth savings)
- Resonant Eventual Consistency (REC) via entropy-guided conflict resolution
- Phase-key cryptographic access control
"""

__version__ = "0.1.0"
__author__ = "Sebastian Schepis"

from resonagraph.core.prime_selection import PrimeSelector
from resonagraph.core.phase_encoding import PhaseEncoder
from resonagraph.api.client import Client
from resonagraph.core.phase_key import PhaseKey
from resonagraph.api.query import Query
from resonagraph.resonance import ProbeSynthesizer, ResonanceLock, ResidueExtractor

__all__ = [
    "Client",
    "PhaseKey", 
    "Query",
    "PrimeSelector",
    "PhaseEncoder",
    "ProbeSynthesizer",
    "ResonanceLock",
    "ResidueExtractor",
]
