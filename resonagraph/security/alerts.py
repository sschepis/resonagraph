"""
Security alert definitions and types for ResonaGraph.

Defines alert structures, types, and basic alert handling functionality.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from resonagraph.security.threat_detection import ThreatLevel


class AlertType(Enum):
    """Types of security alerts."""
    ANOMALY_DETECTED = "anomaly_detected"
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    REPLAY_ATTACK_PATTERN = "replay_attack_pattern"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SUSPICIOUS_KEY_ACCESS = "suspicious_key_access"
    MASS_DATA_ACCESS = "mass_data_access"
    MULTIPLE_FAILURES = "multiple_failures"
    GEOGRAPHIC_ANOMALY = "geographic_anomaly"
    TIME_ANOMALY = "time_anomaly"
    SYSTEM_COMPROMISE = "system_compromise"


@dataclass
class SecurityAlert:
    """Represents a security alert."""
    alert_type: AlertType
    threat_level: ThreatLevel
    timestamp: float
    description: str
    affected_resources: List[str]
    actor: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)
    alert_id: Optional[str] = None
    
    def __post_init__(self):
        """Generate alert ID if not provided."""
        if self.alert_id is None:
            self.alert_id = f"alert_{int(self.timestamp)}_{hash(self.description) % 10000:04d}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "threat_level": self.threat_level.value,
            "timestamp": self.timestamp,
            "description": self.description,
            "affected_resources": self.affected_resources,
            "actor": self.actor,
            "evidence": self.evidence,
            "recommended_actions": self.recommended_actions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecurityAlert':
        """Create alert from dictionary."""
        return cls(
            alert_type=AlertType(data["alert_type"]),
            threat_level=ThreatLevel(data["threat_level"]),
            timestamp=data["timestamp"],
            description=data["description"],
            affected_resources=data["affected_resources"],
            actor=data.get("actor"),
            evidence=data.get("evidence", {}),
            recommended_actions=data.get("recommended_actions", []),
            alert_id=data.get("alert_id")
        )
    
    def get_severity_score(self) -> int:
        """Get numeric severity score for sorting."""
        severity_map = {
            ThreatLevel.CRITICAL: 5,
            ThreatLevel.HIGH: 4,
            ThreatLevel.MEDIUM: 3,
            ThreatLevel.LOW: 2,
            ThreatLevel.INFO: 1
        }
        return severity_map.get(self.threat_level, 0)
    
    def is_high_priority(self) -> bool:
        """Check if alert is high priority."""
        return self.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
    
    def add_evidence(self, key: str, value: Any) -> None:
        """Add evidence to the alert."""
        self.evidence[key] = value
    
    def add_recommendation(self, action: str) -> None:
        """Add a recommended action."""
        if action not in self.recommended_actions:
            self.recommended_actions.append(action)