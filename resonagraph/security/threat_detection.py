"""
Threat detection and anomaly analysis for ResonaGraph security.

Provides pattern-based threat detection, behavioral analysis,
and statistical anomaly detection capabilities.
"""

import time
import threading
import statistics
from collections import defaultdict, deque
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from resonagraph.security.audit import AuditEvent, AuditEventType


class ThreatLevel(Enum):
    """Threat severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass 
class ThreatPattern:
    """Defines a pattern for threat detection."""
    name: str
    description: str
    event_types: Set[str]
    threshold_count: int
    time_window: float  # seconds
    threat_level: ThreatLevel
    conditions: Optional[Callable[[List[AuditEvent]], bool]] = None


@dataclass
class AnomalyBaseline:
    """Statistical baseline for anomaly detection."""
    metric_name: str
    normal_range: Tuple[float, float]  # (min, max)
    mean: float
    std_dev: float
    sample_count: int
    last_updated: float


class ThreatDetector:
    """
    Detects security threats and anomalies in real-time.
    
    Uses pattern matching, statistical analysis, and behavioral analysis
    to identify potential security incidents.
    """
    
    def __init__(
        self,
        alert_callback: Optional[Callable] = None,
        baseline_window: int = 24 * 3600  # 24 hours
    ):
        """
        Initialize threat detector.
        
        Args:
            alert_callback: Function to call when alerts are generated
            baseline_window: Time window for baseline calculations (seconds)
        """
        self.alert_callback = alert_callback
        self.baseline_window = baseline_window
        
        # Event storage for pattern analysis
        self._event_buffer: deque = deque(maxlen=10000)
        self._event_counts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Actor behavior tracking
        self._actor_patterns: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._failed_attempts: Dict[str, List[float]] = defaultdict(list)
        
        # Anomaly baselines
        self._baselines: Dict[str, AnomalyBaseline] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'events_analyzed': 0,
            'alerts_generated': 0,
            'threats_detected': 0,
            'anomalies_detected': 0
        }
        
        # Initialize threat patterns
        self._threat_patterns = self._initialize_threat_patterns()
    
    def analyze_event(self, event: AuditEvent) -> List:
        """
        Analyze an audit event for threats and anomalies.
        
        Args:
            event: Audit event to analyze
            
        Returns:
            List of security alerts generated
        """
        with self._lock:
            alerts = []
            
            # Add to event buffer
            self._event_buffer.append(event)
            self._event_counts[event.event_type].append(event.timestamp)
            
            # Update statistics
            self.stats['events_analyzed'] += 1
            
            # Pattern-based threat detection
            pattern_alerts = self._detect_pattern_threats(event)
            alerts.extend(pattern_alerts)
            
            # Behavioral anomaly detection
            behavioral_alerts = self._detect_behavioral_anomalies(event)
            alerts.extend(behavioral_alerts)
            
            # Statistical anomaly detection
            statistical_alerts = self._detect_statistical_anomalies(event)
            alerts.extend(statistical_alerts)
            
            # Update actor patterns
            self._update_actor_patterns(event)
            
            # Process alerts
            for alert in alerts:
                self.stats['alerts_generated'] += 1
                if alert.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                    self.stats['threats_detected'] += 1
                else:
                    self.stats['anomalies_detected'] += 1
                
                if self.alert_callback:
                    self.alert_callback(alert)
            
            return alerts
    
    def _detect_pattern_threats(self, event: AuditEvent) -> List:
        """Detect threats based on predefined patterns."""
        from resonagraph.security.alerts import SecurityAlert, AlertType
        
        alerts = []
        current_time = event.timestamp
        
        for pattern in self._threat_patterns:
            if event.event_type not in pattern.event_types:
                continue
            
            # Count recent events matching pattern
            recent_events = [
                e for e in self._event_buffer
                if (e.event_type in pattern.event_types and
                    current_time - e.timestamp <= pattern.time_window)
            ]
            
            # Check if pattern conditions are met
            if len(recent_events) >= pattern.threshold_count:
                if pattern.conditions is None or pattern.conditions(recent_events):
                    alert = SecurityAlert(
                        alert_type=AlertType.ANOMALY_DETECTED,
                        threat_level=pattern.threat_level,
                        timestamp=current_time,
                        description=f"Threat pattern detected: {pattern.description}",
                        affected_resources=[event.resource],
                        actor=event.actor,
                        evidence={
                            "pattern_name": pattern.name,
                            "event_count": len(recent_events),
                            "time_window": pattern.time_window,
                            "threshold": pattern.threshold_count
                        },
                        recommended_actions=[
                            "Investigate actor activity",
                            "Review system logs",
                            "Consider temporary access restrictions"
                        ]
                    )
                    alerts.append(alert)
        
        return alerts
    
    def _detect_behavioral_anomalies(self, event: AuditEvent) -> List:
        """Detect behavioral anomalies for actors."""
        from resonagraph.security.alerts import SecurityAlert, AlertType
        
        alerts = []
        
        if not event.actor:
            return alerts
        
        # Track failed login attempts
        if event.event_type == AuditEventType.LOGIN_FAILED.value:
            self._failed_attempts[event.actor].append(event.timestamp)
            
            # Remove old attempts
            cutoff = event.timestamp - 300  # 5 minutes
            self._failed_attempts[event.actor] = [
                t for t in self._failed_attempts[event.actor] if t > cutoff
            ]
            
            # Check for brute force
            if len(self._failed_attempts[event.actor]) >= 5:
                alert = SecurityAlert(
                    alert_type=AlertType.BRUTE_FORCE_ATTACK,
                    threat_level=ThreatLevel.HIGH,
                    timestamp=event.timestamp,
                    description=f"Brute force attack detected from {event.actor}",
                    affected_resources=[event.resource],
                    actor=event.actor,
                    evidence={
                        "failed_attempts": len(self._failed_attempts[event.actor]),
                        "time_window": 300
                    },
                    recommended_actions=[
                        "Block actor IP address",
                        "Require additional authentication",
                        "Alert security team"
                    ]
                )
                alerts.append(alert)
        
        # Detect unusual access patterns
        if event.actor in self._actor_patterns:
            patterns = self._actor_patterns[event.actor]
            
            # Check for unusual resource access
            if self._is_unusual_resource_access(event, patterns):
                alert = SecurityAlert(
                    alert_type=AlertType.SUSPICIOUS_KEY_ACCESS,
                    threat_level=ThreatLevel.MEDIUM,
                    timestamp=event.timestamp,
                    description=f"Unusual resource access by {event.actor}",
                    affected_resources=[event.resource],
                    actor=event.actor,
                    evidence={
                        "resource": event.resource,
                        "normal_resources": list(patterns.get("resources", set()))
                    },
                    recommended_actions=[
                        "Verify actor identity",
                        "Review access permissions",
                        "Monitor future activity"
                    ]
                )
                alerts.append(alert)
        
        return alerts
    
    def _detect_statistical_anomalies(self, event: AuditEvent) -> List:
        """Detect statistical anomalies in event patterns."""
        from resonagraph.security.alerts import SecurityAlert, AlertType
        
        alerts = []
        current_time = event.timestamp
        
        # Analyze event frequency
        event_type = event.event_type
        recent_events = [
            t for t in self._event_counts[event_type]
            if current_time - t <= 3600  # 1 hour window
        ]
        
        if len(recent_events) >= 10:  # Need minimum sample size
            # Calculate current rate (events per hour)
            current_rate = len(recent_events)
            
            # Get baseline if available
            baseline_key = f"event_rate_{event_type}"
            if baseline_key in self._baselines:
                baseline = self._baselines[baseline_key]
                
                # Check if current rate is anomalous (>3 standard deviations)
                z_score = abs(current_rate - baseline.mean) / max(baseline.std_dev, 1.0)
                
                if z_score > 3.0:
                    alert = SecurityAlert(
                        alert_type=AlertType.ANOMALY_DETECTED,
                        threat_level=ThreatLevel.MEDIUM if z_score > 5.0 else ThreatLevel.LOW,
                        timestamp=current_time,
                        description=f"Statistical anomaly in {event_type} frequency",
                        affected_resources=[event.resource],
                        evidence={
                            "current_rate": current_rate,
                            "baseline_mean": baseline.mean,
                            "baseline_std": baseline.std_dev,
                            "z_score": z_score
                        },
                        recommended_actions=[
                            "Investigate cause of event spike",
                            "Check system performance",
                            "Review recent changes"
                        ]
                    )
                    alerts.append(alert)
            else:
                # Create new baseline
                self._baselines[baseline_key] = AnomalyBaseline(
                    metric_name=baseline_key,
                    normal_range=(current_rate * 0.5, current_rate * 2.0),
                    mean=current_rate,
                    std_dev=current_rate * 0.3,
                    sample_count=1,
                    last_updated=current_time
                )
        
        return alerts
    
    def _update_actor_patterns(self, event: AuditEvent) -> None:
        """Update behavioral patterns for an actor."""
        if not event.actor:
            return
        
        patterns = self._actor_patterns[event.actor]
        current_time = event.timestamp
        
        # Track resources accessed
        if "resources" not in patterns:
            patterns["resources"] = set()
        patterns["resources"].add(event.resource)
        
        # Track event types
        if "event_types" not in patterns:
            patterns["event_types"] = defaultdict(int)
        patterns["event_types"][event.event_type] += 1
        
        # Track access times
        if "access_times" not in patterns:
            patterns["access_times"] = []
        patterns["access_times"].append(current_time)
        
        # Keep only recent times (last 30 days)
        cutoff = current_time - (30 * 24 * 3600)
        patterns["access_times"] = [
            t for t in patterns["access_times"] if t > cutoff
        ]
        
        # Track IP addresses if available
        if event.actor_ip:
            if "ip_addresses" not in patterns:
                patterns["ip_addresses"] = set()
            patterns["ip_addresses"].add(event.actor_ip)
        
        patterns["last_seen"] = current_time
    
    def _is_unusual_resource_access(self, event: AuditEvent, patterns: Dict) -> bool:
        """Check if resource access is unusual for this actor."""
        if "resources" not in patterns:
            return False
        
        known_resources = patterns["resources"]
        
        # If actor has accessed < 10 resources, don't flag as unusual yet
        if len(known_resources) < 10:
            return False
        
        # Check if this is a completely new resource
        if event.resource not in known_resources:
            # Check if it's a sensitive resource type
            sensitive_patterns = ["key_", "root_", "admin_", "secret_"]
            if any(pattern in event.resource.lower() for pattern in sensitive_patterns):
                return True
        
        return False
    
    def _initialize_threat_patterns(self) -> List[ThreatPattern]:
        """Initialize predefined threat detection patterns."""
        patterns = []
        
        # Multiple failed logins
        patterns.append(ThreatPattern(
            name="brute_force",
            description="Multiple failed login attempts",
            event_types={AuditEventType.LOGIN_FAILED.value},
            threshold_count=5,
            time_window=300,  # 5 minutes
            threat_level=ThreatLevel.HIGH
        ))
        
        # Rapid key access
        patterns.append(ThreatPattern(
            name="key_enumeration",
            description="Rapid key access attempts",
            event_types={AuditEventType.KEY_ACCESSED.value},
            threshold_count=20,
            time_window=60,  # 1 minute
            threat_level=ThreatLevel.MEDIUM
        ))
        
        # Multiple replay attacks
        patterns.append(ThreatPattern(
            name="replay_attack_pattern",
            description="Multiple replay attacks detected",
            event_types={AuditEventType.REPLAY_DETECTED.value},
            threshold_count=3,
            time_window=600,  # 10 minutes
            threat_level=ThreatLevel.HIGH
        ))
        
        # Mass data access
        patterns.append(ThreatPattern(
            name="mass_data_access",
            description="Mass data access pattern",
            event_types={AuditEventType.DATA_READ.value},
            threshold_count=100,
            time_window=300,  # 5 minutes
            threat_level=ThreatLevel.MEDIUM
        ))
        
        # Privilege escalation attempts
        patterns.append(ThreatPattern(
            name="privilege_escalation",
            description="Potential privilege escalation",
            event_types={AuditEventType.ACCESS_DENIED.value, AuditEventType.PERMISSION_CHANGED.value},
            threshold_count=10,
            time_window=600,  # 10 minutes
            threat_level=ThreatLevel.HIGH
        ))
        
        return patterns
    
    def update_baselines(self) -> None:
        """Update statistical baselines for anomaly detection."""
        with self._lock:
            current_time = time.time()
            
            for event_type, timestamps in self._event_counts.items():
                if len(timestamps) < 10:
                    continue
                
                # Calculate hourly rates over the baseline window
                baseline_start = current_time - self.baseline_window
                recent_timestamps = [t for t in timestamps if t > baseline_start]
                
                if len(recent_timestamps) < 10:
                    continue
                
                # Calculate hourly buckets
                hourly_rates = []
                for hour in range(int(self.baseline_window / 3600)):
                    hour_start = baseline_start + (hour * 3600)
                    hour_end = hour_start + 3600
                    hour_count = len([t for t in recent_timestamps if hour_start <= t < hour_end])
                    hourly_rates.append(hour_count)
                
                if len(hourly_rates) >= 24:  # Need at least 24 hours of data
                    baseline_key = f"event_rate_{event_type}"
                    mean_rate = statistics.mean(hourly_rates)
                    std_rate = statistics.stdev(hourly_rates) if len(hourly_rates) > 1 else mean_rate * 0.3
                    
                    self._baselines[baseline_key] = AnomalyBaseline(
                        metric_name=baseline_key,
                        normal_range=(max(0, mean_rate - 2 * std_rate), mean_rate + 2 * std_rate),
                        mean=mean_rate,
                        std_dev=std_rate,
                        sample_count=len(hourly_rates),
                        last_updated=current_time
                    )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get threat detector statistics."""
        stats = self.stats.copy()
        stats.update({
            'active_patterns': len(self._threat_patterns),
            'baselines_established': len(self._baselines),
            'actors_tracked': len(self._actor_patterns),
            'events_buffered': len(self._event_buffer)
        })
        return stats