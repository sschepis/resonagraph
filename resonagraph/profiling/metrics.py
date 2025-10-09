"""
Metrics collection and Prometheus export for ResonaGraph.

Provides counters, gauges, histograms, and summaries with
Prometheus-compatible export format.
"""

import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Counter:
    """Prometheus Counter - monotonically increasing value."""
    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    
    def inc(self, amount: float = 1.0) -> None:
        """Increment counter."""
        self.value += amount
    
    def get(self) -> float:
        """Get current value."""
        return self.value
    
    def reset(self) -> None:
        """Reset counter to zero."""
        self.value = 0.0


@dataclass
class Gauge:
    """Prometheus Gauge - value that can go up or down."""
    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    
    def set(self, value: float) -> None:
        """Set gauge value."""
        self.value = value
    
    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge."""
        self.value += amount
    
    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge."""
        self.value -= amount
    
    def get(self) -> float:
        """Get current value."""
        return self.value


@dataclass
class Histogram:
    """Prometheus Histogram - distribution of values."""
    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    buckets: List[float] = field(default_factory=lambda: [
        0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 
        0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')
    ])
    _bucket_counts: Dict[float, int] = field(default_factory=dict)
    _sum: float = 0.0
    _count: int = 0
    
    def __post_init__(self):
        """Initialize bucket counts."""
        for bucket in self.buckets:
            self._bucket_counts[bucket] = 0
    
    def observe(self, value: float) -> None:
        """Record an observation."""
        self._sum += value
        self._count += 1
        
        # Update bucket counts
        for bucket in self.buckets:
            if value <= bucket:
                self._bucket_counts[bucket] += 1
    
    def get_buckets(self) -> List[Tuple[float, int]]:
        """Get bucket counts."""
        return [(b, self._bucket_counts[b]) for b in sorted(self.buckets)]
    
    def get_sum(self) -> float:
        """Get sum of all observations."""
        return self._sum
    
    def get_count(self) -> int:
        """Get count of observations."""
        return self._count


class MetricsCollector:
    """
    Collects and manages Prometheus-style metrics.
    
    Features:
    - Counters, Gauges, and Histograms
    - Label support for multi-dimensional metrics
    - Thread-safe operations
    - Prometheus export format
    """
    
    def __init__(self, namespace: str = "resonagraph"):
        """
        Initialize metrics collector.
        
        Args:
            namespace: Metric namespace prefix
        """
        self.namespace = namespace
        self._counters: Dict[str, Dict[tuple, Counter]] = defaultdict(dict)
        self._gauges: Dict[str, Dict[tuple, Gauge]] = defaultdict(dict)
        self._histograms: Dict[str, Dict[tuple, Histogram]] = defaultdict(dict)
        self._lock = threading.RLock()
    
    def _make_label_key(self, labels: Optional[Dict[str, str]]) -> tuple:
        """Create hashable key from labels."""
        if not labels:
            return ()
        return tuple(sorted(labels.items()))
    
    def counter(
        self,
        name: str,
        help: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Counter:
        """
        Get or create a counter.
        
        Args:
            name: Metric name
            help: Help text
            labels: Optional labels
            
        Returns:
            Counter instance
        """
        with self._lock:
            full_name = f"{self.namespace}_{name}"
            label_key = self._make_label_key(labels)
            
            if label_key not in self._counters[full_name]:
                self._counters[full_name][label_key] = Counter(
                    name=full_name,
                    help=help,
                    labels=labels or {}
                )
            
            return self._counters[full_name][label_key]
    
    def gauge(
        self,
        name: str,
        help: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Gauge:
        """
        Get or create a gauge.
        
        Args:
            name: Metric name
            help: Help text
            labels: Optional labels
            
        Returns:
            Gauge instance
        """
        with self._lock:
            full_name = f"{self.namespace}_{name}"
            label_key = self._make_label_key(labels)
            
            if label_key not in self._gauges[full_name]:
                self._gauges[full_name][label_key] = Gauge(
                    name=full_name,
                    help=help,
                    labels=labels or {}
                )
            
            return self._gauges[full_name][label_key]
    
    def histogram(
        self,
        name: str,
        help: str,
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None
    ) -> Histogram:
        """
        Get or create a histogram.
        
        Args:
            name: Metric name
            help: Help text
            labels: Optional labels
            buckets: Optional bucket boundaries
            
        Returns:
            Histogram instance
        """
        with self._lock:
            full_name = f"{self.namespace}_{name}"
            label_key = self._make_label_key(labels)
            
            if label_key not in self._histograms[full_name]:
                hist = Histogram(
                    name=full_name,
                    help=help,
                    labels=labels or {}
                )
                # Only override buckets if provided
                if buckets is not None:
                    hist.buckets = buckets
                    hist._bucket_counts = {b: 0 for b in buckets}
                
                self._histograms[full_name][label_key] = hist
            
            return self._histograms[full_name][label_key]
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.
        
        Returns:
            Dictionary of all metrics
        """
        with self._lock:
            return {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'histograms': dict(self._histograms)
            }
    
    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


class PrometheusExporter:
    """
    Exports metrics in Prometheus text format.
    
    Implements the Prometheus exposition format:
    https://prometheus.io/docs/instrumenting/exposition_formats/
    """
    
    def __init__(self, collector: MetricsCollector):
        """
        Initialize exporter.
        
        Args:
            collector: MetricsCollector instance
        """
        self.collector = collector
    
    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus."""
        if not labels:
            return ""
        
        label_parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(label_parts) + "}"
    
    def _export_counter(self, name: str, metrics: Dict[tuple, Counter]) -> List[str]:
        """Export counter metrics."""
        lines = []
        
        if not metrics:
            return lines
        
        # Get help text from first metric
        first_metric = next(iter(metrics.values()))
        lines.append(f"# HELP {name} {first_metric.help}")
        lines.append(f"# TYPE {name} counter")
        
        # Export each labeled variant
        for metric in metrics.values():
            label_str = self._format_labels(metric.labels)
            lines.append(f"{name}{label_str} {metric.value}")
        
        return lines
    
    def _export_gauge(self, name: str, metrics: Dict[tuple, Gauge]) -> List[str]:
        """Export gauge metrics."""
        lines = []
        
        if not metrics:
            return lines
        
        # Get help text from first metric
        first_metric = next(iter(metrics.values()))
        lines.append(f"# HELP {name} {first_metric.help}")
        lines.append(f"# TYPE {name} gauge")
        
        # Export each labeled variant
        for metric in metrics.values():
            label_str = self._format_labels(metric.labels)
            lines.append(f"{name}{label_str} {metric.value}")
        
        return lines
    
    def _export_histogram(self, name: str, metrics: Dict[tuple, Histogram]) -> List[str]:
        """Export histogram metrics."""
        lines = []
        
        if not metrics:
            return lines
        
        # Get help text from first metric
        first_metric = next(iter(metrics.values()))
        lines.append(f"# HELP {name} {first_metric.help}")
        lines.append(f"# TYPE {name} histogram")
        
        # Export each labeled variant
        for metric in metrics.values():
            base_labels = dict(metric.labels)
            
            # Export buckets
            for bucket, count in metric.get_buckets():
                bucket_labels = base_labels.copy()
                bucket_labels['le'] = str(bucket) if bucket != float('inf') else '+Inf'
                label_str = self._format_labels(bucket_labels)
                lines.append(f"{name}_bucket{label_str} {count}")
            
            # Export sum and count
            label_str = self._format_labels(base_labels)
            lines.append(f"{name}_sum{label_str} {metric.get_sum()}")
            lines.append(f"{name}_count{label_str} {metric.get_count()}")
        
        return lines
    
    def export(self) -> str:
        """
        Export all metrics in Prometheus format.
        
        Returns:
            Prometheus text format string
        """
        lines = []
        metrics = self.collector.get_all_metrics()
        
        # Export counters
        for name, counter_metrics in metrics['counters'].items():
            lines.extend(self._export_counter(name, counter_metrics))
            lines.append("")
        
        # Export gauges
        for name, gauge_metrics in metrics['gauges'].items():
            lines.extend(self._export_gauge(name, gauge_metrics))
            lines.append("")
        
        # Export histograms
        for name, histogram_metrics in metrics['histograms'].items():
            lines.extend(self._export_histogram(name, histogram_metrics))
            lines.append("")
        
        return "\n".join(lines)
    
    def export_to_file(self, filepath: str) -> None:
        """
        Export metrics to file.
        
        Args:
            filepath: Output file path
        """
        with open(filepath, 'w') as f:
            f.write(self.export())


# Global metrics collector
_default_collector: Optional[MetricsCollector] = None


def get_metrics_collector(namespace: str = "resonagraph") -> MetricsCollector:
    """
    Get or create the default metrics collector.
    
    Args:
        namespace: Metric namespace
        
    Returns:
        MetricsCollector instance
    """
    global _default_collector
    if _default_collector is None:
        _default_collector = MetricsCollector(namespace=namespace)
    return _default_collector