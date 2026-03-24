"""
Performance Metrics Module

This module tracks and reports system performance metrics:
- CPU usage
- Memory usage
- Event loop latency
- Message throughput

Metrics are published to MQTT for external monitoring systems.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Optional psutil import (graceful degradation if not installed)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not installed - CPU/memory metrics will be unavailable")


@dataclass
class MetricsConfig:
    """Configuration for performance metrics."""
    enabled: bool = True
    publish_interval: float = 30.0         # Seconds between metric reports
    metrics_topic: str = "campus/fleet/metrics"
    latency_samples: int = 100             # Rolling average window

    @classmethod
    def from_dict(cls, config: dict) -> "MetricsConfig":
        """Create MetricsConfig from configuration dictionary."""
        return cls(
            enabled=config.get("enabled", True),
            publish_interval=config.get("publish_interval", 30.0),
        )


class PerformanceMetrics:
    """
    Tracks and reports system performance metrics.

    Collects:
    - CPU usage percentage
    - Memory usage (RSS and percentage)
    - Event loop latency (measures asyncio responsiveness)
    - Message throughput (messages per second)

    Usage:
        metrics = PerformanceMetrics(config)

        # Track message publishes:
        metrics.record_message()

        # Track tick latency:
        metrics.record_tick_latency(expected=5.0, actual=5.003)

        # Background task publishes metrics:
        asyncio.create_task(metrics.run_metrics_loop(mqtt_client))
    """

    def __init__(self, config: MetricsConfig | None = None):
        """
        Initialize performance metrics tracker.

        Args:
            config: MetricsConfig instance or None for defaults
        """
        self.config = config or MetricsConfig()
        self._running = False

        # Message tracking
        self._message_count = 0
        self._last_message_check = time.time()

        # Latency tracking (rolling window)
        self._latencies: list[float] = []
        self._max_latency_samples = self.config.latency_samples

        # Process handle for memory tracking
        self._process = psutil.Process(os.getpid()) if PSUTIL_AVAILABLE else None

    def record_message(self, count: int = 1) -> None:
        """
        Record published messages for throughput calculation.

        Args:
            count: Number of messages published
        """
        self._message_count += count

    def record_tick_latency(self, expected: float, actual: float) -> None:
        """
        Record the latency between expected and actual tick timing.

        Args:
            expected: Expected tick duration (seconds)
            actual: Actual tick duration (seconds)
        """
        latency = abs(actual - expected)
        self._latencies.append(latency)

        # Keep rolling window
        if len(self._latencies) > self._max_latency_samples:
            self._latencies.pop(0)

    def get_cpu_usage(self) -> float | None:
        """
        Get current CPU usage percentage.

        Returns:
            CPU percentage (0-100) or None if unavailable
        """
        if not PSUTIL_AVAILABLE:
            return None
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return None

    def get_memory_usage(self) -> dict[str, Any]:
        """
        Get current memory usage statistics.

        Returns:
            Dictionary with memory metrics or empty dict if unavailable
        """
        if not PSUTIL_AVAILABLE or not self._process:
            return {}

        try:
            mem_info = self._process.memory_info()
            mem_percent = self._process.memory_percent()

            return {
                "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                "vms_mb": round(mem_info.vms / (1024 * 1024), 2),
                "percent": round(mem_percent, 2)
            }
        except Exception:
            return {}

    def get_message_throughput(self) -> float:
        """
        Calculate messages per second since last check.

        Returns:
            Messages per second
        """
        now = time.time()
        elapsed = now - self._last_message_check
        if elapsed <= 0:
            return 0.0

        throughput = self._message_count / elapsed

        # Reset counters
        self._message_count = 0
        self._last_message_check = now

        return round(throughput, 2)

    def get_latency_stats(self) -> dict[str, float]:
        """
        Calculate latency statistics from recorded samples.

        Returns:
            Dictionary with avg, min, max, p95, p99 latencies
        """
        if not self._latencies:
            return {
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0
            }

        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)

        avg = sum(sorted_latencies) / n
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)

        return {
            "avg_ms": round(avg * 1000, 3),
            "min_ms": round(sorted_latencies[0] * 1000, 3),
            "max_ms": round(sorted_latencies[-1] * 1000, 3),
            "p95_ms": round(sorted_latencies[min(p95_idx, n - 1)] * 1000, 3),
            "p99_ms": round(sorted_latencies[min(p99_idx, n - 1)] * 1000, 3)
        }

    def get_full_report(self) -> dict[str, Any]:
        """
        Generate complete performance metrics report.

        Returns:
            Dictionary with all performance metrics
        """
        return {
            "timestamp": int(time.time()),
            "cpu_percent": self.get_cpu_usage(),
            "memory": self.get_memory_usage(),
            "messages_per_second": self.get_message_throughput(),
            "latency": self.get_latency_stats(),
            "psutil_available": PSUTIL_AVAILABLE
        }

    async def measure_event_loop_latency(self) -> float:
        """
        Measure event loop responsiveness.

        Schedules a callback and measures how long it takes to execute.

        Returns:
            Latency in milliseconds
        """
        start = time.perf_counter()
        await asyncio.sleep(0)  # Yield to event loop
        latency = time.perf_counter() - start
        return latency * 1000  # Convert to ms

    async def run_metrics_loop(
        self,
        mqtt_client,
        shutdown_event: asyncio.Event | None = None
    ) -> None:
        """
        Background task that periodically publishes performance metrics.

        Args:
            mqtt_client: MQTT client for publishing metrics
            shutdown_event: Event to signal shutdown
        """
        if not self.config.enabled:
            logger.info("Performance metrics disabled")
            return

        self._running = True

        # Initialize CPU tracking (first call returns 0)
        if PSUTIL_AVAILABLE:
            psutil.cpu_percent(interval=None)

        logger.info(
            f"Metrics monitor started: interval={self.config.publish_interval}s"
        )

        while self._running:
            if shutdown_event and shutdown_event.is_set():
                break

            try:
                await asyncio.sleep(self.config.publish_interval)

                # Measure event loop latency
                loop_latency = await self.measure_event_loop_latency()

                # Generate report
                report = self.get_full_report()
                report["event_loop_latency_ms"] = round(loop_latency, 3)

                # Publish to MQTT
                payload = json.dumps(report)
                try:
                    await mqtt_client.publish(
                        self.config.metrics_topic,
                        payload,
                        qos=0
                    )
                    logger.debug(f"Published metrics to {self.config.metrics_topic}")
                except Exception as e:
                    logger.error(f"Failed to publish metrics: {e}")

                # Log summary
                mem = report.get("memory", {})
                logger.info(
                    f"Metrics: CPU={report.get('cpu_percent', 'N/A')}%, "
                    f"Mem={mem.get('rss_mb', 'N/A')}MB, "
                    f"Msgs/s={report['messages_per_second']}, "
                    f"Loop latency={loop_latency:.3f}ms"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics error: {e}")

        logger.info("Metrics monitor stopped")

    def stop(self) -> None:
        """Signal the metrics loop to stop."""
        self._running = False
