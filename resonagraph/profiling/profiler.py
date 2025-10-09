"""
Performance profiler for ResonaGraph.

Provides decorators and context managers for tracking function
execution times, memory usage, and call counts.
"""

import time
import functools
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProfileStats:
    """Statistics for a profiled function or block."""
    name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    last_time: float = 0.0
    percentiles: Dict[int, float] = field(default_factory=dict)
    _times: List[float] = field(default_factory=list, repr=False)
    
    def record(self, elapsed: float) -> None:
        """Record a new timing."""
        self.call_count += 1
        self.total_time += elapsed
        self.min_time = min(self.min_time, elapsed)
        self.max_time = max(self.max_time, elapsed)
        self.avg_time = self.total_time / self.call_count
        self.last_time = elapsed
        self._times.append(elapsed)
    
    def compute_percentiles(self, percentiles: List[int] = None) -> None:
        """Compute percentiles from recorded times."""
        if not self._times:
            return
        
        if percentiles is None:
            percentiles = [50, 75, 90, 95, 99]
        
        sorted_times = sorted(self._times)
        n = len(sorted_times)
        
        for p in percentiles:
            idx = int(n * p / 100)
            if idx >= n:
                idx = n - 1
            self.percentiles[p] = sorted_times[idx]
    
    def clear_history(self) -> None:
        """Clear recorded times to save memory."""
        self._times.clear()
        self.percentiles.clear()


class Profiler:
    """
    Performance profiler for tracking function execution times.
    
    Features:
    - Track function call counts and execution times
    - Support for both sync and async functions
    - Context manager for profiling code blocks
    - Thread-safe operations
    - Aggregate statistics and percentiles
    """
    
    def __init__(self, name: str = "default"):
        """
        Initialize profiler.
        
        Args:
            name: Profiler instance name
        """
        self.name = name
        self._stats: Dict[str, ProfileStats] = {}
        self._lock = threading.RLock()
        self._enabled = True
    
    def enable(self) -> None:
        """Enable profiling."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable profiling."""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """Check if profiling is enabled."""
        return self._enabled
    
    def record(self, name: str, elapsed: float) -> None:
        """
        Record a timing measurement.
        
        Args:
            name: Function or block name
            elapsed: Elapsed time in seconds
        """
        if not self._enabled:
            return
        
        with self._lock:
            if name not in self._stats:
                self._stats[name] = ProfileStats(name=name)
            self._stats[name].record(elapsed)
    
    @contextmanager
    def profile_block(self, name: str):
        """
        Context manager for profiling a code block.
        
        Args:
            name: Block name
            
        Example:
            with profiler.profile_block("my_operation"):
                # code to profile
                ...
        """
        if not self._enabled:
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.record(name, elapsed)
    
    def get_stats(self, name: str) -> Optional[ProfileStats]:
        """
        Get statistics for a specific function or block.
        
        Args:
            name: Function or block name
            
        Returns:
            ProfileStats or None if not found
        """
        with self._lock:
            return self._stats.get(name)
    
    def get_all_stats(self) -> Dict[str, ProfileStats]:
        """
        Get all profiling statistics.
        
        Returns:
            Dictionary of name -> ProfileStats
        """
        with self._lock:
            return dict(self._stats)
    
    def compute_all_percentiles(self, percentiles: List[int] = None) -> None:
        """
        Compute percentiles for all tracked functions.
        
        Args:
            percentiles: List of percentile values (default: [50, 75, 90, 95, 99])
        """
        with self._lock:
            for stats in self._stats.values():
                stats.compute_percentiles(percentiles)
    
    def clear(self, name: Optional[str] = None) -> None:
        """
        Clear statistics.
        
        Args:
            name: Specific function name, or None to clear all
        """
        with self._lock:
            if name is None:
                self._stats.clear()
            elif name in self._stats:
                del self._stats[name]
    
    def clear_history(self, name: Optional[str] = None) -> None:
        """
        Clear timing history to save memory.
        
        Args:
            name: Specific function name, or None to clear all
        """
        with self._lock:
            if name is None:
                for stats in self._stats.values():
                    stats.clear_history()
            elif name in self._stats:
                self._stats[name].clear_history()
    
    def get_summary(self, sort_by: str = 'total_time', limit: int = 20) -> str:
        """
        Get human-readable summary of profiling data.
        
        Args:
            sort_by: Sort key ('total_time', 'avg_time', 'call_count', 'max_time')
            limit: Maximum number of functions to show
            
        Returns:
            Formatted summary string
        """
        with self._lock:
            if not self._stats:
                return "No profiling data collected"
            
            # Sort stats
            stats_list = list(self._stats.values())
            
            if sort_by == 'total_time':
                stats_list.sort(key=lambda s: s.total_time, reverse=True)
            elif sort_by == 'avg_time':
                stats_list.sort(key=lambda s: s.avg_time, reverse=True)
            elif sort_by == 'call_count':
                stats_list.sort(key=lambda s: s.call_count, reverse=True)
            elif sort_by == 'max_time':
                stats_list.sort(key=lambda s: s.max_time, reverse=True)
            
            # Limit results
            stats_list = stats_list[:limit]
            
            # Build summary
            lines = [
                f"Profiler: {self.name}",
                f"Total functions tracked: {len(self._stats)}",
                "",
                f"Top {len(stats_list)} by {sort_by}:",
                "",
                f"{'Function':<40} {'Calls':>8} {'Total (s)':>12} {'Avg (ms)':>12} {'Min (ms)':>12} {'Max (ms)':>12}"
            ]
            lines.append("-" * 108)
            
            for stats in stats_list:
                lines.append(
                    f"{stats.name:<40} "
                    f"{stats.call_count:>8} "
                    f"{stats.total_time:>12.6f} "
                    f"{stats.avg_time*1000:>12.3f} "
                    f"{stats.min_time*1000:>12.3f} "
                    f"{stats.max_time*1000:>12.3f}"
                )
            
            return "\n".join(lines)
    
    def export_json(self) -> Dict[str, Any]:
        """
        Export profiling data as JSON-serializable dict.
        
        Returns:
            Dictionary with profiling data
        """
        with self._lock:
            return {
                'profiler': self.name,
                'enabled': self._enabled,
                'stats': {
                    name: {
                        'call_count': stats.call_count,
                        'total_time': stats.total_time,
                        'avg_time': stats.avg_time,
                        'min_time': stats.min_time,
                        'max_time': stats.max_time,
                        'last_time': stats.last_time,
                        'percentiles': stats.percentiles
                    }
                    for name, stats in self._stats.items()
                }
            }


def profile(profiler: Optional[Profiler] = None, name: Optional[str] = None):
    """
    Decorator for profiling synchronous functions.
    
    Args:
        profiler: Profiler instance (uses default if None)
        name: Custom name for the function (uses func.__name__ if None)
        
    Example:
        @profile()
        def my_function():
            ...
        
        @profile(profiler=my_profiler, name="custom_name")
        def another_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__
        prof = profiler or get_profiler()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not prof.is_enabled():
                return func(*args, **kwargs)
            
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                prof.record(func_name, elapsed)
        
        return wrapper
    return decorator


def profile_async(profiler: Optional[Profiler] = None, name: Optional[str] = None):
    """
    Decorator for profiling asynchronous functions.
    
    Args:
        profiler: Profiler instance (uses default if None)
        name: Custom name for the function (uses func.__name__ if None)
        
    Example:
        @profile_async()
        async def my_async_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__
        prof = profiler or get_profiler()
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not prof.is_enabled():
                return await func(*args, **kwargs)
            
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                prof.record(func_name, elapsed)
        
        return wrapper
    return decorator


# Global profiler instance
_default_profiler: Optional[Profiler] = None


def get_profiler(name: str = "default") -> Profiler:
    """
    Get or create the default profiler instance.
    
    Args:
        name: Profiler name
        
    Returns:
        Profiler instance
    """
    global _default_profiler
    if _default_profiler is None:
        _default_profiler = Profiler(name=name)
    return _default_profiler