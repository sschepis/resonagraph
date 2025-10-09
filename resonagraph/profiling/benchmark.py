"""
Benchmarking framework for ResonaGraph.

Provides tools for running performance benchmarks with
consistent methodology and result reporting.
"""

import time
import statistics
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass, field
import functools
import logging

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""
    name: str
    iterations: int
    total_time: float
    min_time: float
    max_time: float
    mean_time: float
    median_time: float
    stddev: float
    percentile_95: float
    percentile_99: float
    ops_per_sec: float
    _times: List[float] = field(default_factory=list, repr=False)
    
    @classmethod
    def from_times(cls, name: str, times: List[float]) -> 'BenchmarkResult':
        """Create result from list of timing measurements."""
        if not times:
            raise ValueError("No timing data provided")
        
        sorted_times = sorted(times)
        n = len(sorted_times)
        
        return cls(
            name=name,
            iterations=n,
            total_time=sum(times),
            min_time=min(times),
            max_time=max(times),
            mean_time=statistics.mean(times),
            median_time=statistics.median(times),
            stddev=statistics.stdev(times) if n > 1 else 0.0,
            percentile_95=sorted_times[int(n * 0.95)] if n > 1 else times[0],
            percentile_99=sorted_times[int(n * 0.99)] if n > 1 else times[0],
            ops_per_sec=n / sum(times) if sum(times) > 0 else 0.0,
            _times=times
        )
    
    def summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"Benchmark: {self.name}",
            f"  Iterations: {self.iterations}",
            f"  Total time: {self.total_time:.6f}s",
            f"  Mean time: {self.mean_time*1000:.3f}ms",
            f"  Median time: {self.median_time*1000:.3f}ms",
            f"  Min time: {self.min_time*1000:.3f}ms",
            f"  Max time: {self.max_time*1000:.3f}ms",
            f"  Std dev: {self.stddev*1000:.3f}ms",
            f"  95th percentile: {self.percentile_95*1000:.3f}ms",
            f"  99th percentile: {self.percentile_99*1000:.3f}ms",
            f"  Ops/sec: {self.ops_per_sec:.2f}"
        ]
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export as dictionary."""
        return {
            'name': self.name,
            'iterations': self.iterations,
            'total_time': self.total_time,
            'min_time': self.min_time,
            'max_time': self.max_time,
            'mean_time': self.mean_time,
            'median_time': self.median_time,
            'stddev': self.stddev,
            'percentile_95': self.percentile_95,
            'percentile_99': self.percentile_99,
            'ops_per_sec': self.ops_per_sec
        }


class Benchmark:
    """
    Individual benchmark for measuring function performance.
    
    Features:
    - Multiple iterations for statistical significance
    - Warmup runs to eliminate cold start effects
    - Automatic timing and statistics
    - Result reporting
    """
    
    def __init__(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10
    ):
        """
        Initialize benchmark.
        
        Args:
            name: Benchmark name
            func: Function to benchmark
            iterations: Number of iterations to run
            warmup: Number of warmup iterations
        """
        self.name = name
        self.func = func
        self.iterations = iterations
        self.warmup = warmup
        self._result: Optional[BenchmarkResult] = None
    
    def run(self, *args, **kwargs) -> BenchmarkResult:
        """
        Run the benchmark.
        
        Args:
            *args: Arguments to pass to function
            **kwargs: Keyword arguments to pass to function
            
        Returns:
            BenchmarkResult with timing data
        """
        logger.info(f"Running benchmark: {self.name}")
        
        # Warmup
        logger.debug(f"Warmup ({self.warmup} iterations)...")
        for _ in range(self.warmup):
            self.func(*args, **kwargs)
        
        # Benchmark
        logger.debug(f"Benchmarking ({self.iterations} iterations)...")
        times = []
        
        for i in range(self.iterations):
            start = time.perf_counter()
            self.func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            
            if (i + 1) % 10 == 0:
                logger.debug(f"  Progress: {i + 1}/{self.iterations}")
        
        # Create result
        self._result = BenchmarkResult.from_times(self.name, times)
        logger.info(f"Benchmark complete: {self.name}")
        
        return self._result
    
    def get_result(self) -> Optional[BenchmarkResult]:
        """Get last benchmark result."""
        return self._result


class BenchmarkSuite:
    """
    Collection of benchmarks to run together.
    
    Features:
    - Multiple benchmarks in one suite
    - Comparative results
    - Summary reporting
    """
    
    def __init__(self, name: str):
        """
        Initialize benchmark suite.
        
        Args:
            name: Suite name
        """
        self.name = name
        self.benchmarks: List[Benchmark] = []
        self.results: Dict[str, BenchmarkResult] = {}
    
    def add(self, benchmark: Benchmark) -> None:
        """
        Add a benchmark to the suite.
        
        Args:
            benchmark: Benchmark instance
        """
        self.benchmarks.append(benchmark)
    
    def add_function(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10
    ) -> None:
        """
        Add a function as a benchmark.
        
        Args:
            name: Benchmark name
            func: Function to benchmark
            iterations: Number of iterations
            warmup: Number of warmup iterations
        """
        self.add(Benchmark(name, func, iterations, warmup))
    
    def run_all(self, *args, **kwargs) -> Dict[str, BenchmarkResult]:
        """
        Run all benchmarks in the suite.
        
        Args:
            *args: Arguments to pass to functions
            **kwargs: Keyword arguments to pass to functions
            
        Returns:
            Dictionary of benchmark results
        """
        logger.info(f"Running benchmark suite: {self.name}")
        logger.info(f"Total benchmarks: {len(self.benchmarks)}")
        
        self.results.clear()
        
        for i, benchmark in enumerate(self.benchmarks, 1):
            logger.info(f"[{i}/{len(self.benchmarks)}] {benchmark.name}")
            result = benchmark.run(*args, **kwargs)
            self.results[benchmark.name] = result
        
        logger.info(f"Benchmark suite complete: {self.name}")
        return self.results
    
    def get_summary(self, sort_by: str = 'mean_time') -> str:
        """
        Get comparative summary of all benchmarks.
        
        Args:
            sort_by: Sort key ('mean_time', 'ops_per_sec', etc.)
            
        Returns:
            Formatted summary string
        """
        if not self.results:
            return "No benchmark results available"
        
        # Sort results
        sorted_results = sorted(
            self.results.values(),
            key=lambda r: getattr(r, sort_by)
        )
        
        if sort_by == 'ops_per_sec':
            sorted_results = list(reversed(sorted_results))
        
        # Build summary
        lines = [
            f"Benchmark Suite: {self.name}",
            f"Total benchmarks: {len(self.results)}",
            "",
            f"{'Benchmark':<40} {'Mean (ms)':>12} {'Median (ms)':>12} {'Ops/sec':>12} {'Iterations':>12}"
        ]
        lines.append("-" * 92)
        
        for result in sorted_results:
            lines.append(
                f"{result.name:<40} "
                f"{result.mean_time*1000:>12.3f} "
                f"{result.median_time*1000:>12.3f} "
                f"{result.ops_per_sec:>12.2f} "
                f"{result.iterations:>12}"
            )
        
        return "\n".join(lines)
    
    def compare(self, baseline: str) -> str:
        """
        Compare all benchmarks to a baseline.
        
        Args:
            baseline: Name of baseline benchmark
            
        Returns:
            Formatted comparison string
        """
        if baseline not in self.results:
            return f"Baseline '{baseline}' not found in results"
        
        baseline_result = self.results[baseline]
        baseline_time = baseline_result.mean_time
        
        lines = [
            f"Comparison to baseline: {baseline}",
            f"Baseline mean time: {baseline_time*1000:.3f}ms",
            "",
            f"{'Benchmark':<40} {'Mean (ms)':>12} {'vs Baseline':>12} {'Speedup':>10}"
        ]
        lines.append("-" * 78)
        
        for name, result in sorted(self.results.items(), key=lambda x: x[1].mean_time):
            if name == baseline:
                lines.append(
                    f"{name:<40} "
                    f"{result.mean_time*1000:>12.3f} "
                    f"{'BASELINE':>12} "
                    f"{'1.00x':>10}"
                )
            else:
                speedup = baseline_time / result.mean_time if result.mean_time > 0 else 0
                diff_pct = ((result.mean_time - baseline_time) / baseline_time * 100) if baseline_time > 0 else 0
                
                lines.append(
                    f"{name:<40} "
                    f"{result.mean_time*1000:>12.3f} "
                    f"{diff_pct:>11.1f}% "
                    f"{speedup:>9.2f}x"
                )
        
        return "\n".join(lines)
    
    def export_json(self) -> Dict[str, Any]:
        """
        Export results as JSON-serializable dict.
        
        Returns:
            Dictionary with all results
        """
        return {
            'suite': self.name,
            'benchmarks': {
                name: result.to_dict()
                for name, result in self.results.items()
            }
        }


def benchmark(
    iterations: int = 100,
    warmup: int = 10,
    name: Optional[str] = None
):
    """
    Decorator for creating benchmarkable functions.
    
    Args:
        iterations: Number of iterations
        warmup: Number of warmup iterations
        name: Custom name (uses func.__name__ if None)
        
    Example:
        @benchmark(iterations=1000)
        def my_function():
            ...
        
        result = my_function.benchmark()
        print(result.summary())
    """
    def decorator(func: Callable) -> Callable:
        bench_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Add benchmark method
        def run_benchmark(*args, **kwargs) -> BenchmarkResult:
            bench = Benchmark(bench_name, func, iterations, warmup)
            return bench.run(*args, **kwargs)
        
        wrapper.benchmark = run_benchmark
        return wrapper
    
    return decorator