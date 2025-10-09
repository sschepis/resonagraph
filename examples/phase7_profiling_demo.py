"""
Phase 7.4 Profiling Demo - Performance Profiling and Benchmarking

Demonstrates the ResonaGraph profiling subsystem with:
- Function profiling with decorators
- Prometheus metrics collection
- Benchmark framework
- Performance analysis and reporting
"""

import time
import numpy as np
from typing import List

from resonagraph.profiling import (
    Profiler,
    profile,
    get_profiler,
    MetricsCollector,
    PrometheusExporter,
    get_metrics_collector,
    Benchmark,
    BenchmarkSuite,
    benchmark
)


def demo_profiler():
    """Demonstrate function profiling."""
    print("\n" + "="*60)
    print("PROFILER DEMO")
    print("="*60)
    
    # Create profiler
    profiler = Profiler(name="demo")
    
    print("\n1. Profiling with decorators...")
    
    # Define profiled functions
    @profile(profiler=profiler)
    def fast_operation():
        """Simulates a fast operation."""
        time.sleep(0.001)
        return sum(range(1000))
    
    @profile(profiler=profiler)
    def slow_operation():
        """Simulates a slow operation."""
        time.sleep(0.01)
        return sum(range(10000))
    
    @profile(profiler=profiler)
    def variable_operation(duration):
        """Simulates variable duration operation."""
        time.sleep(duration)
    
    # Run operations
    print("   Running fast_operation 20 times...")
    for _ in range(20):
        fast_operation()
    
    print("   Running slow_operation 10 times...")
    for _ in range(10):
        slow_operation()
    
    print("   Running variable_operation with different durations...")
    for duration in [0.001, 0.005, 0.01, 0.002, 0.008]:
        variable_operation(duration)
    
    # Show individual stats
    print("\n2. Individual function statistics:")
    
    for func_name in ["fast_operation", "slow_operation", "variable_operation"]:
        stats = profiler.get_stats(func_name)
        if stats:
            print(f"\n   {func_name}:")
            print(f"     Calls: {stats.call_count}")
            print(f"     Total time: {stats.total_time*1000:.2f}ms")
            print(f"     Mean time: {stats.avg_time*1000:.3f}ms")
            print(f"     Min time: {stats.min_time*1000:.3f}ms")
            print(f"     Max time: {stats.max_time*1000:.3f}ms")
    
    # Compute percentiles
    print("\n3. Computing percentiles...")
    profiler.compute_all_percentiles()
    
    stats = profiler.get_stats("variable_operation")
    if stats.percentiles:
        print(f"   variable_operation percentiles:")
        for p, value in sorted(stats.percentiles.items()):
            print(f"     p{p}: {value*1000:.3f}ms")
    
    # Show summary
    print("\n4. Overall summary:")
    print(profiler.get_summary(sort_by='total_time', limit=10))
    
    print("\n5. Using context manager for code blocks...")
    
    for i in range(5):
        with profiler.profile_block("custom_block"):
            # Simulate some work
            _ = [x**2 for x in range(1000)]
            time.sleep(0.002)
    
    stats = profiler.get_stats("custom_block")
    print(f"   custom_block: {stats.call_count} calls, avg={stats.avg_time*1000:.3f}ms")


def demo_metrics():
    """Demonstrate Prometheus metrics collection."""
    print("\n" + "="*60)
    print("METRICS DEMO")
    print("="*60)
    
    # Create metrics collector
    collector = MetricsCollector(namespace="resonagraph")
    
    print("\n1. Counter metrics...")
    
    # Request counter
    request_counter = collector.counter(
        "requests_total",
        "Total number of requests"
    )
    
    # Labeled counters for different methods
    get_counter = collector.counter(
        "requests_total",
        "Total number of requests",
        labels={'method': 'GET', 'status': '200'}
    )
    
    post_counter = collector.counter(
        "requests_total",
        "Total number of requests",
        labels={'method': 'POST', 'status': '201'}
    )
    
    # Simulate requests
    for _ in range(100):
        get_counter.inc()
    
    for _ in range(50):
        post_counter.inc()
    
    print(f"   GET requests: {get_counter.get()}")
    print(f"   POST requests: {post_counter.get()}")
    
    print("\n2. Gauge metrics...")
    
    # Active connections gauge
    connections = collector.gauge(
        "active_connections",
        "Number of active connections"
    )
    
    # Memory usage gauge
    memory_mb = collector.gauge(
        "memory_usage_mb",
        "Memory usage in megabytes"
    )
    
    # Simulate changes
    connections.set(10)
    connections.inc(5)
    print(f"   Active connections: {connections.get()}")
    
    memory_mb.set(128.5)
    memory_mb.inc(32.0)
    print(f"   Memory usage: {memory_mb.get()} MB")
    
    print("\n3. Histogram metrics...")
    
    # Response time histogram
    latency = collector.histogram(
        "response_latency_seconds",
        "Response latency in seconds",
        buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 5.0, float('inf')]
    )
    
    # Simulate response times
    response_times = [0.005, 0.008, 0.012, 0.025, 0.050, 0.100, 0.200, 0.300, 0.500, 1.2]
    
    for duration in response_times:
        latency.observe(duration)
    
    print(f"   Total observations: {latency.get_count()}")
    print(f"   Sum: {latency.get_sum():.3f}s")
    print(f"   Average: {latency.get_sum()/latency.get_count():.3f}s")
    
    # Show bucket distribution
    print(f"\n   Bucket distribution:")
    for bucket, count in latency.get_buckets():
        bucket_label = f"{bucket}s" if bucket != float('inf') else "+Inf"
        print(f"     <= {bucket_label:>8}: {count:>3} requests")
    
    print("\n4. Prometheus export format:")
    exporter = PrometheusExporter(collector)
    output = exporter.export()
    
    # Show first 20 lines
    lines = output.split('\n')[:20]
    for line in lines:
        if line:
            print(f"   {line}")
    
    print(f"   ... ({len(output.split(chr(10))) - 20} more lines)")


def demo_benchmarks():
    """Demonstrate benchmark framework."""
    print("\n" + "="*60)
    print("BENCHMARK DEMO")
    print("="*60)
    
    print("\n1. Simple benchmark...")
    
    # Define function to benchmark
    def list_comprehension():
        return [x**2 for x in range(1000)]
    
    # Create and run benchmark
    bench = Benchmark(
        name="list_comprehension",
        func=list_comprehension,
        iterations=1000,
        warmup=50
    )
    
    result = bench.run()
    print(result.summary())
    
    print("\n2. Benchmark decorator...")
    
    @benchmark(iterations=500, warmup=25)
    def generator_expression():
        return list(x**2 for x in range(1000))
    
    # Run benchmark
    result = generator_expression.benchmark()
    print(f"\n   Mean time: {result.mean_time*1000:.3f}ms")
    print(f"   Median time: {result.median_time*1000:.3f}ms")
    print(f"   95th percentile: {result.percentile_95*1000:.3f}ms")
    print(f"   Ops/sec: {result.ops_per_sec:.2f}")
    
    print("\n3. Benchmark suite...")
    
    # Create suite
    suite = BenchmarkSuite("array_operations")
    
    # Add benchmarks
    def numpy_array():
        return np.arange(1000) ** 2
    
    def python_list():
        return [x**2 for x in range(1000)]
    
    def generator():
        return list(x**2 for x in range(1000))
    
    suite.add_function("numpy_array", numpy_array, iterations=500)
    suite.add_function("python_list", python_list, iterations=500)
    suite.add_function("generator", generator, iterations=500)
    
    # Run all benchmarks
    results = suite.run_all()
    
    # Show summary
    print("\n4. Suite summary:")
    print(suite.get_summary(sort_by='mean_time'))
    
    # Compare to baseline
    print("\n5. Comparison to python_list baseline:")
    print(suite.compare("python_list"))


def demo_integration():
    """Demonstrate integrated profiling and metrics."""
    print("\n" + "="*60)
    print("INTEGRATION DEMO")
    print("="*60)
    
    profiler = Profiler(name="integrated")
    collector = MetricsCollector(namespace="app")
    
    # Create metrics
    call_counter = collector.counter("function_calls", "Function call count")
    latency_hist = collector.histogram("function_latency", "Function latency")
    
    @profile(profiler=profiler)
    def tracked_function(duration: float):
        """Function tracked by both profiler and metrics."""
        call_counter.inc()
        start = time.perf_counter()
        
        # Simulate work
        time.sleep(duration)
        result = sum(range(1000))
        
        elapsed = time.perf_counter() - start
        latency_hist.observe(elapsed)
        
        return result
    
    print("\n1. Running tracked function with varying durations...")
    
    durations = [0.001, 0.002, 0.005, 0.001, 0.003, 0.010, 0.002, 0.001]
    
    for duration in durations:
        tracked_function(duration)
    
    print(f"   Executed {len(durations)} calls")
    
    print("\n2. Profiler statistics:")
    stats = profiler.get_stats("tracked_function")
    print(f"   Call count: {stats.call_count}")
    print(f"   Mean time: {stats.avg_time*1000:.3f}ms")
    print(f"   Min time: {stats.min_time*1000:.3f}ms")
    print(f"   Max time: {stats.max_time*1000:.3f}ms")
    
    print("\n3. Metrics statistics:")
    print(f"   Counter: {call_counter.get()} calls")
    print(f"   Histogram observations: {latency_hist.get_count()}")
    print(f"   Histogram sum: {latency_hist.get_sum()*1000:.2f}ms")
    print(f"   Average latency: {(latency_hist.get_sum()/latency_hist.get_count())*1000:.2f}ms")
    
    print("\n4. Metrics in Prometheus format:")
    exporter = PrometheusExporter(collector)
    output = exporter.export()
    
    for line in output.split('\n'):
        if 'function' in line.lower():
            print(f"   {line}")


def demo_real_world():
    """Demonstrate real-world performance analysis."""
    print("\n" + "="*60)
    print("REAL-WORLD PERFORMANCE ANALYSIS")
    print("="*60)
    
    profiler = get_profiler()
    collector = get_metrics_collector()
    
    # Metrics
    cache_hits = collector.counter("cache_hits", "Cache hits")
    cache_misses = collector.counter("cache_misses", "Cache misses")
    processing_time = collector.histogram("processing_time", "Processing time")
    
    # Simulate cache with profiling
    cache = {}
    
    @profile()
    def get_from_cache(key: str):
        if key in cache:
            cache_hits.inc()
            return cache[key]
        else:
            cache_misses.inc()
            return None
    
    @profile()
    def expensive_computation(key: str):
        start = time.perf_counter()
        
        # Simulate expensive work
        time.sleep(0.01)
        result = sum(range(10000))
        
        elapsed = time.perf_counter() - start
        processing_time.observe(elapsed)
        
        cache[key] = result
        return result
    
    @profile()
    def process_request(key: str):
        # Try cache first
        result = get_from_cache(key)
        
        if result is None:
            # Cache miss - compute
            result = expensive_computation(key)
        
        return result
    
    print("\n1. Simulating 100 requests...")
    
    # Simulate requests with 20% cache hit rate
    keys = [f"key_{i % 20}" for i in range(100)]
    
    for key in keys:
        process_request(key)
    
    print("   Complete")
    
    print("\n2. Performance statistics:")
    
    for func_name in ["process_request", "get_from_cache", "expensive_computation"]:
        stats = profiler.get_stats(func_name)
        if stats:
            print(f"\n   {func_name}:")
            print(f"     Calls: {stats.call_count}")
            print(f"     Avg time: {stats.avg_time*1000:.3f}ms")
            print(f"     Total time: {stats.total_time*1000:.2f}ms")
    
    print("\n3. Cache performance:")
    hit_count = cache_hits.get()
    miss_count = cache_misses.get()
    total = hit_count + miss_count
    hit_rate = hit_count / total if total > 0 else 0
    
    print(f"   Hits: {hit_count}")
    print(f"   Misses: {miss_count}")
    print(f"   Hit rate: {hit_rate:.1%}")
    
    print("\n4. Processing time distribution:")
    print(f"   Observations: {processing_time.get_count()}")
    print(f"   Total time: {processing_time.get_sum()*1000:.2f}ms")
    print(f"   Avg time: {(processing_time.get_sum()/processing_time.get_count())*1000:.2f}ms")


def main():
    """Run all profiling and benchmarking demos."""
    print("\n" + "="*60)
    print("RESONAGRAPH PHASE 7.4 - PROFILING & BENCHMARKING DEMO")
    print("="*60)
    print("\nDemonstrating:")
    print("- Function profiling with decorators and context managers")
    print("- Prometheus metrics (counters, gauges, histograms)")
    print("- Benchmark framework with statistical analysis")
    print("- Integrated performance monitoring")
    
    # Run demos
    demo_profiler()
    demo_metrics()
    demo_benchmarks()
    demo_integration()
    demo_real_world()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nKey Takeaways:")
    print("✓ @profile decorator for automatic function timing")
    print("✓ Context managers for profiling code blocks")
    print("✓ Prometheus-compatible metrics export")
    print("✓ Statistical benchmarking with percentiles")
    print("✓ Benchmark suites for comparative analysis")
    print("✓ Thread-safe operations for concurrent profiling")
    print("✓ Integration with existing monitoring systems")


if __name__ == '__main__':
    main()