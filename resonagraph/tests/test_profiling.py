"""
Tests for ResonaGraph profiling and benchmarking subsystem.

Tests profiler, metrics collection, and benchmarking framework.
"""

import unittest
import time
import asyncio
from threading import Thread

from resonagraph.profiling import (
    Profiler,
    profile,
    profile_async,
    MetricsCollector,
    PrometheusExporter,
    Benchmark,
    BenchmarkSuite,
    benchmark
)


class TestProfiler(unittest.TestCase):
    """Test profiler functionality."""
    
    def setUp(self):
        """Set up test profiler."""
        self.profiler = Profiler(name="test")
    
    def test_profile_decorator(self):
        """Test profile decorator."""
        @profile(profiler=self.profiler)
        def test_func():
            time.sleep(0.01)
        
        # Run function multiple times
        for _ in range(5):
            test_func()
        
        # Check stats
        stats = self.profiler.get_stats("test_func")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.call_count, 5)
        self.assertGreater(stats.total_time, 0.045)
        self.assertGreater(stats.avg_time, 0.009)
    
    def test_profile_async_decorator(self):
        """Test async profile decorator."""
        @profile_async(profiler=self.profiler)
        async def async_func():
            await asyncio.sleep(0.01)
        
        # Run async function
        async def run_test():
            for _ in range(3):
                await async_func()
        
        asyncio.run(run_test())
        
        # Check stats
        stats = self.profiler.get_stats("async_func")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.call_count, 3)
    
    def test_context_manager(self):
        """Test profile_block context manager."""
        for i in range(4):
            with self.profiler.profile_block("my_block"):
                time.sleep(0.005)
        
        stats = self.profiler.get_stats("my_block")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.call_count, 4)
        self.assertGreater(stats.total_time, 0.015)
    
    def test_min_max_avg(self):
        """Test min, max, avg calculations."""
        @profile(profiler=self.profiler)
        def varying_func(duration):
            time.sleep(duration)
        
        # Different durations
        varying_func(0.01)
        varying_func(0.02)
        varying_func(0.005)
        
        stats = self.profiler.get_stats("varying_func")
        
        self.assertLess(stats.min_time, 0.01)
        self.assertGreater(stats.max_time, 0.015)
        self.assertGreater(stats.avg_time, 0.01)
        self.assertLess(stats.avg_time, 0.015)
    
    def test_percentiles(self):
        """Test percentile computation."""
        # Record various times
        for i in range(100):
            self.profiler.record("test", i / 1000.0)
        
        # Compute percentiles
        self.profiler.compute_all_percentiles()
        
        stats = self.profiler.get_stats("test")
        self.assertIn(50, stats.percentiles)
        self.assertIn(95, stats.percentiles)
        self.assertIn(99, stats.percentiles)
        
        # 50th percentile should be around 0.049
        self.assertAlmostEqual(stats.percentiles[50], 0.049, delta=0.005)
    
    def test_enable_disable(self):
        """Test enabling/disabling profiler."""
        @profile(profiler=self.profiler)
        def test_func():
            pass
        
        # Enabled by default
        test_func()
        self.assertEqual(self.profiler.get_stats("test_func").call_count, 1)
        
        # Disable
        self.profiler.disable()
        test_func()
        test_func()
        # Count should still be 1
        self.assertEqual(self.profiler.get_stats("test_func").call_count, 1)
        
        # Re-enable
        self.profiler.enable()
        test_func()
        self.assertEqual(self.profiler.get_stats("test_func").call_count, 2)
    
    def test_clear_stats(self):
        """Test clearing statistics."""
        self.profiler.record("func1", 0.1)
        self.profiler.record("func2", 0.2)
        
        # Clear specific
        self.profiler.clear("func1")
        self.assertIsNone(self.profiler.get_stats("func1"))
        self.assertIsNotNone(self.profiler.get_stats("func2"))
        
        # Clear all
        self.profiler.clear()
        self.assertIsNone(self.profiler.get_stats("func2"))
    
    def test_summary(self):
        """Test summary generation."""
        for i in range(10):
            self.profiler.record(f"func{i}", i / 100.0)
        
        summary = self.profiler.get_summary(limit=5)
        
        self.assertIn("Profiler: test", summary)
        self.assertIn("Total functions tracked: 10", summary)
        self.assertIn("Top 5", summary)
    
    def test_export_json(self):
        """Test JSON export."""
        self.profiler.record("test", 0.1)
        
        data = self.profiler.export_json()
        
        self.assertEqual(data['profiler'], 'test')
        self.assertIn('test', data['stats'])
        self.assertEqual(data['stats']['test']['call_count'], 1)
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        @profile(profiler=self.profiler)
        def thread_func():
            time.sleep(0.001)
        
        def worker():
            for _ in range(10):
                thread_func()
        
        threads = [Thread(target=worker) for _ in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        stats = self.profiler.get_stats("thread_func")
        self.assertEqual(stats.call_count, 50)


class TestMetrics(unittest.TestCase):
    """Test metrics collection."""
    
    def setUp(self):
        """Set up test collector."""
        self.collector = MetricsCollector(namespace="test")
    
    def test_counter(self):
        """Test counter metric."""
        counter = self.collector.counter("requests", "Total requests")
        
        counter.inc()
        counter.inc(5)
        
        self.assertEqual(counter.get(), 6)
    
    def test_counter_with_labels(self):
        """Test counter with labels."""
        counter1 = self.collector.counter(
            "requests",
            "Total requests",
            labels={'method': 'GET'}
        )
        
        counter2 = self.collector.counter(
            "requests",
            "Total requests",
            labels={'method': 'POST'}
        )
        
        counter1.inc(10)
        counter2.inc(5)
        
        self.assertEqual(counter1.get(), 10)
        self.assertEqual(counter2.get(), 5)
    
    def test_gauge(self):
        """Test gauge metric."""
        gauge = self.collector.gauge("temperature", "Current temperature")
        
        gauge.set(20.5)
        self.assertEqual(gauge.get(), 20.5)
        
        gauge.inc(5)
        self.assertEqual(gauge.get(), 25.5)
        
        gauge.dec(10)
        self.assertEqual(gauge.get(), 15.5)
    
    def test_histogram(self):
        """Test histogram metric."""
        histogram = self.collector.histogram(
            "latency",
            "Request latency",
            buckets=[0.1, 0.5, 1.0, 5.0, float('inf')]
        )
        
        # Record observations
        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(0.7)
        histogram.observe(2.0)
        
        # Check counts
        self.assertEqual(histogram.get_count(), 4)
        self.assertAlmostEqual(histogram.get_sum(), 3.05)
        
        # Check buckets
        buckets = dict(histogram.get_buckets())
        self.assertEqual(buckets[0.1], 1)  # One value <= 0.1
        self.assertEqual(buckets[0.5], 2)  # Two values <= 0.5
        self.assertEqual(buckets[1.0], 3)  # Three values <= 1.0
    
    def test_prometheus_export(self):
        """Test Prometheus export format."""
        # Create metrics
        counter = self.collector.counter("requests", "Total requests")
        counter.inc(42)
        
        gauge = self.collector.gauge("temperature", "Current temp")
        gauge.set(23.5)
        
        # Export
        exporter = PrometheusExporter(self.collector)
        output = exporter.export()
        
        # Check format
        self.assertIn("# HELP test_requests Total requests", output)
        self.assertIn("# TYPE test_requests counter", output)
        self.assertIn("test_requests 42", output)
        
        self.assertIn("# HELP test_temperature Current temp", output)
        self.assertIn("# TYPE test_temperature gauge", output)
        self.assertIn("test_temperature 23.5", output)
    
    def test_prometheus_export_with_labels(self):
        """Test Prometheus export with labels."""
        counter = self.collector.counter(
            "requests",
            "Total requests",
            labels={'method': 'GET', 'status': '200'}
        )
        counter.inc(100)
        
        exporter = PrometheusExporter(self.collector)
        output = exporter.export()
        
        self.assertIn('method="GET"', output)
        self.assertIn('status="200"', output)
        self.assertIn("test_requests", output)
    
    def test_histogram_export(self):
        """Test histogram Prometheus export."""
        histogram = self.collector.histogram(
            "latency",
            "Request latency"
        )
        
        histogram.observe(0.05)
        histogram.observe(0.5)
        
        exporter = PrometheusExporter(self.collector)
        output = exporter.export()
        
        self.assertIn("# TYPE test_latency histogram", output)
        self.assertIn("test_latency_bucket", output)
        self.assertIn("test_latency_sum", output)
        self.assertIn("test_latency_count", output)
        self.assertIn('le="+Inf"', output)


class TestBenchmark(unittest.TestCase):
    """Test benchmark functionality."""
    
    def test_simple_benchmark(self):
        """Test basic benchmark."""
        def sleep_func():
            time.sleep(0.001)
        
        benchmark = Benchmark("test", sleep_func, iterations=10, warmup=2)
        result = benchmark.run()
        
        self.assertEqual(result.name, "test")
        self.assertEqual(result.iterations, 10)
        self.assertGreater(result.total_time, 0.008)
        self.assertGreater(result.mean_time, 0.0008)
        self.assertGreater(result.ops_per_sec, 0)
    
    def test_benchmark_with_args(self):
        """Test benchmark with arguments."""
        def multiply(x, y):
            return x * y
        
        benchmark = Benchmark("multiply", multiply, iterations=100)
        result = benchmark.run(5, 10)
        
        self.assertEqual(result.iterations, 100)
    
    def test_benchmark_decorator(self):
        """Test benchmark decorator."""
        @benchmark(iterations=50, warmup=5)
        def test_func():
            time.sleep(0.001)
        
        result = test_func.benchmark()
        
        self.assertEqual(result.iterations, 50)
        self.assertGreater(result.mean_time, 0.0008)
    
    def test_benchmark_suite(self):
        """Test benchmark suite."""
        suite = BenchmarkSuite("test_suite")
        
        def func1():
            time.sleep(0.001)
        
        def func2():
            time.sleep(0.002)
        
        suite.add_function("fast", func1, iterations=10)
        suite.add_function("slow", func2, iterations=10)
        
        results = suite.run_all()
        
        self.assertEqual(len(results), 2)
        self.assertIn("fast", results)
        self.assertIn("slow", results)
        
        # Fast should be faster than slow
        self.assertLess(results["fast"].mean_time, results["slow"].mean_time)
    
    def test_suite_summary(self):
        """Test suite summary generation."""
        suite = BenchmarkSuite("test")
        
        def func():
            pass
        
        suite.add_function("test", func, iterations=10)
        suite.run_all()
        
        summary = suite.get_summary()
        
        self.assertIn("Benchmark Suite: test", summary)
        self.assertIn("Total benchmarks: 1", summary)
    
    def test_suite_comparison(self):
        """Test benchmark comparison."""
        suite = BenchmarkSuite("comparison")
        
        def baseline():
            time.sleep(0.002)
        
        def optimized():
            time.sleep(0.001)
        
        suite.add_function("baseline", baseline, iterations=10)
        suite.add_function("optimized", optimized, iterations=10)
        
        suite.run_all()
        
        comparison = suite.compare("baseline")
        
        self.assertIn("Comparison to baseline", comparison)
        self.assertIn("BASELINE", comparison)
        self.assertIn("optimized", comparison)
    
    def test_result_summary(self):
        """Test benchmark result summary."""
        def func():
            time.sleep(0.001)
        
        benchmark = Benchmark("test", func, iterations=10)
        result = benchmark.run()
        
        summary = result.summary()
        
        self.assertIn("Benchmark: test", summary)
        self.assertIn("Iterations: 10", summary)
        self.assertIn("Mean time", summary)
        self.assertIn("Ops/sec", summary)
    
    def test_result_to_dict(self):
        """Test result export to dict."""
        def func():
            pass
        
        benchmark = Benchmark("test", func, iterations=5)
        result = benchmark.run()
        
        data = result.to_dict()
        
        self.assertEqual(data['name'], 'test')
        self.assertEqual(data['iterations'], 5)
        self.assertIn('mean_time', data)
        self.assertIn('ops_per_sec', data)


class TestIntegration(unittest.TestCase):
    """Integration tests for profiling subsystem."""
    
    def test_profiler_with_metrics(self):
        """Test using profiler and metrics together."""
        profiler = Profiler()
        collector = MetricsCollector()
        
        # Create metrics
        call_counter = collector.counter("calls", "Function calls")
        latency_hist = collector.histogram("latency", "Function latency")
        
        @profile(profiler=profiler)
        def tracked_func():
            call_counter.inc()
            start = time.perf_counter()
            time.sleep(0.001)
            latency_hist.observe(time.perf_counter() - start)
        
        # Run function
        for _ in range(10):
            tracked_func()
        
        # Check profiler
        stats = profiler.get_stats("tracked_func")
        self.assertEqual(stats.call_count, 10)
        
        # Check metrics
        self.assertEqual(call_counter.get(), 10)
        self.assertEqual(latency_hist.get_count(), 10)


if __name__ == '__main__':
    unittest.main()