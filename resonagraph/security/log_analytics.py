"""
Advanced log analytics and querying for ResonaGraph audit logs.

Provides sophisticated analysis capabilities including pattern detection,
statistical analysis, and custom query support for security investigations.
"""

import json
import time
import re
import statistics
from typing import Dict, List, Optional, Any, Callable, Iterator, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import logging

from resonagraph.security.audit import AuditEvent, AuditEventType


@dataclass
class QueryFilter:
    """Filter criteria for log queries."""
    event_types: Optional[List[str]] = None
    actors: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    outcomes: Optional[List[str]] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    ip_addresses: Optional[List[str]] = None
    session_ids: Optional[List[str]] = None
    metadata_filters: Optional[Dict[str, Any]] = None


@dataclass
class QueryResult:
    """Result of a log query operation."""
    events: List[AuditEvent]
    total_count: int
    execution_time: float
    query_summary: Dict[str, Any]


@dataclass
class AnalyticsReport:
    """Result of log analytics analysis."""
    name: str
    description: str
    time_period: Tuple[float, float]
    metrics: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    generated_at: float


class LogAnalyzer:
    """
    Advanced log analytics engine for audit log analysis.
    
    Provides querying, pattern detection, statistical analysis,
    and forensic investigation capabilities.
    """
    
    def __init__(self, log_file: str):
        """
        Initialize log analyzer.
        
        Args:
            log_file: Path to audit log file
        """
        self.log_file = log_file
        self.stats = {
            'queries_executed': 0,
            'events_analyzed': 0,
            'reports_generated': 0
        }
    
    def query_events(
        self,
        filters: QueryFilter,
        limit: Optional[int] = None,
        sort_by: str = 'timestamp',
        sort_desc: bool = True
    ) -> QueryResult:
        """
        Query audit events with flexible filtering.
        
        Args:
            filters: Query filter criteria
            limit: Maximum number of results
            sort_by: Field to sort by
            sort_desc: Sort in descending order
            
        Returns:
            Query results
        """
        start_time = time.time()
        events = []
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        event_dict = json.loads(line.strip())
                        event = self._dict_to_event(event_dict)
                        
                        if self._matches_filter(event, filters):
                            events.append(event)
                    
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        except FileNotFoundError:
            logging.warning(f"Log file not found: {self.log_file}")
        
        # Sort events
        if sort_by == 'timestamp':
            events.sort(key=lambda e: e.timestamp, reverse=sort_desc)
        elif sort_by == 'actor':
            events.sort(key=lambda e: e.actor or '', reverse=sort_desc)
        elif sort_by == 'resource':
            events.sort(key=lambda e: e.resource, reverse=sort_desc)
        
        # Apply limit
        total_count = len(events)
        if limit:
            events = events[:limit]
        
        execution_time = time.time() - start_time
        
        # Update statistics
        self.stats['queries_executed'] += 1
        self.stats['events_analyzed'] += total_count
        
        return QueryResult(
            events=events,
            total_count=total_count,
            execution_time=execution_time,
            query_summary=self._generate_query_summary(filters, total_count)
        )
    
    def _dict_to_event(self, event_dict: Dict[str, Any]) -> AuditEvent:
        """Convert dictionary to AuditEvent."""
        return AuditEvent(
            event_type=event_dict.get('event_type', ''),
            timestamp=event_dict.get('timestamp', 0),
            resource=event_dict.get('resource', ''),
            action=event_dict.get('action', ''),
            outcome=event_dict.get('outcome', ''),
            actor=event_dict.get('actor'),
            actor_ip=event_dict.get('actor_ip'),
            session_id=event_dict.get('session_id'),
            metadata=event_dict.get('metadata', {})
        )
    
    def _matches_filter(self, event: AuditEvent, filters: QueryFilter) -> bool:
        """Check if event matches filter criteria."""
        # Time range filter
        if filters.start_time and event.timestamp < filters.start_time:
            return False
        if filters.end_time and event.timestamp > filters.end_time:
            return False
        
        # Event type filter
        if filters.event_types and event.event_type not in filters.event_types:
            return False
        
        # Actor filter
        if filters.actors and event.actor not in filters.actors:
            return False
        
        # Resource filter
        if filters.resources:
            if not any(resource in event.resource for resource in filters.resources):
                return False
        
        # Outcome filter
        if filters.outcomes and event.outcome not in filters.outcomes:
            return False
        
        # IP address filter
        if filters.ip_addresses and event.actor_ip not in filters.ip_addresses:
            return False
        
        # Session ID filter
        if filters.session_ids and event.session_id not in filters.session_ids:
            return False
        
        # Metadata filters
        if filters.metadata_filters:
            for key, value in filters.metadata_filters.items():
                if key not in event.metadata or event.metadata[key] != value:
                    return False
        
        return True
    
    def _generate_query_summary(self, filters: QueryFilter, result_count: int) -> Dict[str, Any]:
        """Generate summary of query execution."""
        return {
            'result_count': result_count,
            'filters_applied': {
                'event_types': filters.event_types,
                'actors': filters.actors,
                'time_range': (filters.start_time, filters.end_time) if filters.start_time or filters.end_time else None
            }
        }
    
    def analyze_user_behavior(
        self,
        actor: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> AnalyticsReport:
        """
        Analyze behavior patterns for a specific user/actor.
        
        Args:
            actor: Actor to analyze
            start_time: Analysis start time
            end_time: Analysis end time
            
        Returns:
            User behavior analysis report
        """
        # Query events for the actor
        filters = QueryFilter(
            actors=[actor],
            start_time=start_time,
            end_time=end_time
        )
        
        query_result = self.query_events(filters)
        events = query_result.events
        
        if not events:
            return AnalyticsReport(
                name=f"User Behavior Analysis: {actor}",
                description="No events found for analysis",
                time_period=(start_time or 0, end_time or time.time()),
                metrics={},
                insights=["No activity detected for this actor"],
                recommendations=[],
                generated_at=time.time()
            )
        
        # Calculate metrics
        metrics = self._calculate_user_metrics(events)
        
        # Generate insights
        insights = self._generate_user_insights(events, metrics)
        
        # Generate recommendations
        recommendations = self._generate_user_recommendations(events, metrics)
        
        self.stats['reports_generated'] += 1
        
        return AnalyticsReport(
            name=f"User Behavior Analysis: {actor}",
            description=f"Behavioral analysis for actor {actor}",
            time_period=(
                min(e.timestamp for e in events),
                max(e.timestamp for e in events)
            ),
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            generated_at=time.time()
        )
    
    def _calculate_user_metrics(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """Calculate user behavior metrics."""
        if not events:
            return {}
        
        # Basic activity metrics
        total_events = len(events)
        unique_resources = len(set(e.resource for e in events))
        unique_event_types = len(set(e.event_type for e in events))
        
        # Time-based metrics
        timestamps = [e.timestamp for e in events]
        time_span = max(timestamps) - min(timestamps)
        
        # Activity patterns
        event_type_counts = Counter(e.event_type for e in events)
        outcome_counts = Counter(e.outcome for e in events)
        resource_counts = Counter(e.resource for e in events)
        
        # Hour-of-day analysis
        hours = [datetime.fromtimestamp(ts).hour for ts in timestamps]
        hour_distribution = Counter(hours)
        
        # Day-of-week analysis
        weekdays = [datetime.fromtimestamp(ts).weekday() for ts in timestamps]
        weekday_distribution = Counter(weekdays)
        
        # Success rate
        success_rate = outcome_counts.get('success', 0) / total_events * 100
        
        return {
            'total_events': total_events,
            'unique_resources': unique_resources,
            'unique_event_types': unique_event_types,
            'time_span_hours': time_span / 3600,
            'success_rate': success_rate,
            'event_type_distribution': dict(event_type_counts.most_common(10)),
            'outcome_distribution': dict(outcome_counts),
            'top_resources': dict(resource_counts.most_common(10)),
            'hour_distribution': dict(hour_distribution),
            'weekday_distribution': dict(weekday_distribution),
            'average_events_per_hour': total_events / max(time_span / 3600, 1)
        }
    
    def _generate_user_insights(self, events: List[AuditEvent], metrics: Dict[str, Any]) -> List[str]:
        """Generate insights from user behavior analysis."""
        insights = []
        
        # Activity level insights
        if metrics['total_events'] > 1000:
            insights.append("High activity user with extensive system usage")
        elif metrics['total_events'] < 10:
            insights.append("Low activity user with minimal system usage")
        
        # Success rate insights
        success_rate = metrics['success_rate']
        if success_rate < 80:
            insights.append(f"Low success rate ({success_rate:.1f}%) may indicate access issues")
        elif success_rate > 95:
            insights.append("High success rate indicates normal authorized access")
        
        # Resource access patterns
        if metrics['unique_resources'] > 100:
            insights.append("Accesses a wide variety of resources")
        
        # Time-based patterns
        hour_dist = metrics['hour_distribution']
        if hour_dist:
            peak_hour = max(hour_dist, key=hour_dist.get)
            if 0 <= peak_hour <= 6:
                insights.append("Unusual activity during night hours detected")
            elif 9 <= peak_hour <= 17:
                insights.append("Activity pattern consistent with business hours")
        
        # Event type patterns
        event_types = metrics['event_type_distribution']
        if 'login_failed' in event_types and event_types['login_failed'] > 10:
            insights.append("Multiple failed login attempts detected")
        
        return insights
    
    def _generate_user_recommendations(self, events: List[AuditEvent], metrics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on user behavior."""
        recommendations = []
        
        # Security recommendations
        if metrics['success_rate'] < 80:
            recommendations.append("Review user access permissions and training")
        
        failed_logins = metrics['event_type_distribution'].get('login_failed', 0)
        if failed_logins > 5:
            recommendations.append("Consider account security review and password reset")
        
        # Access pattern recommendations
        if metrics['unique_resources'] > 200:
            recommendations.append("Review if broad resource access is necessary for user role")
        
        # Time-based recommendations
        hour_dist = metrics['hour_distribution']
        night_activity = sum(hour_dist.get(h, 0) for h in range(0, 7))
        if night_activity > metrics['total_events'] * 0.2:
            recommendations.append("Investigate unusual after-hours activity")
        
        return recommendations
    
    def analyze_security_events(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> AnalyticsReport:
        """
        Analyze security-related events and patterns.
        
        Args:
            start_time: Analysis start time
            end_time: Analysis end time
            
        Returns:
            Security analysis report
        """
        # Security event types
        security_event_types = [
            AuditEventType.LOGIN_FAILED.value,
            AuditEventType.ACCESS_DENIED.value,
            AuditEventType.REPLAY_DETECTED.value,
            AuditEventType.INTEGRITY_VIOLATION.value,
            AuditEventType.SUSPICIOUS_ACTIVITY.value,
            AuditEventType.SIGNATURE_FAILED.value
        ]
        
        filters = QueryFilter(
            event_types=security_event_types,
            start_time=start_time,
            end_time=end_time
        )
        
        query_result = self.query_events(filters)
        events = query_result.events
        
        # Calculate security metrics
        metrics = self._calculate_security_metrics(events)
        
        # Generate security insights
        insights = self._generate_security_insights(events, metrics)
        
        # Generate security recommendations
        recommendations = self._generate_security_recommendations(events, metrics)
        
        self.stats['reports_generated'] += 1
        
        return AnalyticsReport(
            name="Security Events Analysis",
            description="Analysis of security-related events and potential threats",
            time_period=(start_time or 0, end_time or time.time()),
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            generated_at=time.time()
        )
    
    def _calculate_security_metrics(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """Calculate security-specific metrics."""
        if not events:
            return {}
        
        total_events = len(events)
        
        # Event type distribution
        event_type_counts = Counter(e.event_type for e in events)
        
        # Actor analysis
        actor_counts = Counter(e.actor for e in events if e.actor)
        
        # Resource analysis
        resource_counts = Counter(e.resource for e in events)
        
        # IP analysis
        ip_counts = Counter(e.actor_ip for e in events if e.actor_ip)
        
        # Time-based analysis
        timestamps = [e.timestamp for e in events]
        if len(timestamps) > 1:
            time_intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
            avg_interval = statistics.mean(time_intervals)
        else:
            avg_interval = 0
        
        return {
            'total_security_events': total_events,
            'event_type_distribution': dict(event_type_counts),
            'top_actors': dict(actor_counts.most_common(10)),
            'top_resources': dict(resource_counts.most_common(10)),
            'top_ip_addresses': dict(ip_counts.most_common(10)),
            'average_interval_seconds': avg_interval,
            'events_per_hour': self._calculate_hourly_distribution(timestamps)
        }
    
    def _calculate_hourly_distribution(self, timestamps: List[float]) -> Dict[int, int]:
        """Calculate distribution of events by hour."""
        hours = [datetime.fromtimestamp(ts).hour for ts in timestamps]
        return dict(Counter(hours))
    
    def _generate_security_insights(self, events: List[AuditEvent], metrics: Dict[str, Any]) -> List[str]:
        """Generate insights from security analysis."""
        insights = []
        
        # Volume insights
        total_events = metrics['total_security_events']
        if total_events > 100:
            insights.append("High volume of security events detected")
        elif total_events == 0:
            insights.append("No security events detected in the analyzed period")
        
        # Pattern insights
        event_types = metrics['event_type_distribution']
        
        if 'login_failed' in event_types:
            failed_logins = event_types['login_failed']
            if failed_logins > 50:
                insights.append("Significant number of failed login attempts detected")
        
        if 'replay_detected' in event_types:
            insights.append("Replay attacks detected - potential security breach")
        
        if 'integrity_violation' in event_types:
            insights.append("Data integrity violations detected")
        
        # Actor patterns
        top_actors = metrics['top_actors']
        if top_actors:
            top_actor, count = next(iter(top_actors.items()))
            if count > total_events * 0.5:
                insights.append(f"Single actor ({top_actor}) responsible for majority of security events")
        
        return insights
    
    def _generate_security_recommendations(self, events: List[AuditEvent], metrics: Dict[str, Any]) -> List[str]:
        """Generate security recommendations."""
        recommendations = []
        
        event_types = metrics['event_type_distribution']
        
        # Failed login recommendations
        if event_types.get('login_failed', 0) > 20:
            recommendations.extend([
                "Implement account lockout policies",
                "Enable multi-factor authentication",
                "Monitor for brute force attacks"
            ])
        
        # Access denied recommendations
        if event_types.get('access_denied', 0) > 50:
            recommendations.extend([
                "Review access control policies",
                "Provide user training on proper access procedures",
                "Investigate potential privilege escalation attempts"
            ])
        
        # Integrity violation recommendations
        if 'integrity_violation' in event_types:
            recommendations.extend([
                "Investigate data integrity issues immediately",
                "Review backup and recovery procedures",
                "Implement additional integrity checks"
            ])
        
        # Replay attack recommendations
        if 'replay_detected' in event_types:
            recommendations.extend([
                "Strengthen authentication mechanisms",
                "Implement time-based tokens",
                "Review network security controls"
            ])
        
        return recommendations
    
    def search_events(
        self,
        search_term: str,
        fields: Optional[List[str]] = None,
        case_sensitive: bool = False,
        regex: bool = False
    ) -> QueryResult:
        """
        Search for events containing specific terms.
        
        Args:
            search_term: Term to search for
            fields: Fields to search in (default: all text fields)
            case_sensitive: Whether search is case sensitive
            regex: Whether to treat search_term as regex
            
        Returns:
            Search results
        """
        if fields is None:
            fields = ['event_type', 'resource', 'action', 'actor', 'actor_ip']
        
        start_time = time.time()
        events = []
        
        # Compile regex if needed
        if regex:
            try:
                pattern = re.compile(search_term, 0 if case_sensitive else re.IGNORECASE)
            except re.error:
                raise ValueError(f"Invalid regex pattern: {search_term}")
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        event_dict = json.loads(line.strip())
                        event = self._dict_to_event(event_dict)
                        
                        # Check if search term matches any specified field
                        for field in fields:
                            field_value = getattr(event, field, None)
                            if field_value:
                                if regex:
                                    if pattern.search(str(field_value)):
                                        events.append(event)
                                        break
                                else:
                                    search_in = str(field_value) if case_sensitive else str(field_value).lower()
                                    term = search_term if case_sensitive else search_term.lower()
                                    if term in search_in:
                                        events.append(event)
                                        break
                    
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        except FileNotFoundError:
            logging.warning(f"Log file not found: {self.log_file}")
        
        execution_time = time.time() - start_time
        
        return QueryResult(
            events=events,
            total_count=len(events),
            execution_time=execution_time,
            query_summary={
                'search_term': search_term,
                'fields_searched': fields,
                'case_sensitive': case_sensitive,
                'regex': regex,
                'matches_found': len(events)
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get log analyzer statistics."""
        return self.stats.copy()


# Factory function for easy setup
def create_log_analyzer(log_file: str) -> LogAnalyzer:
    """
    Create log analyzer for the specified log file.
    
    Args:
        log_file: Path to audit log file
        
    Returns:
        Configured log analyzer
    """
    return LogAnalyzer(log_file)
