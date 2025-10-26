"""
Resource Monitor and Throttler for Raspberry Pi Zero
Monitors CPU, memory, and temperature to prevent system overload
"""

import gc
import logging
import os
import time
from typing import Dict, Any, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, resource monitoring disabled")

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    Monitor system resources and throttle operations if needed.

    Performance features:
    - CPU usage monitoring with throttling
    - Memory usage tracking
    - Temperature monitoring (Pi-specific)
    - Automatic garbage collection
    - Low-power mode support
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.perf_config = config.get('performance', {})
        self.logging_config = config.get('logging', {})

        # Thresholds
        self.max_cpu_percent = self.perf_config.get('max_cpu_percent', 80)
        self.gc_enabled = self.perf_config.get('gc_enabled', True)
        self.low_power_mode = self.perf_config.get('low_power_mode', True)

        # Performance logging
        self.log_performance = self.logging_config.get('log_performance', True)

        # Process handle
        self.process = psutil.Process() if PSUTIL_AVAILABLE else None

        # Temperature file path (Raspberry Pi)
        self.temp_file = '/sys/class/thermal/thermal_zone0/temp'

        logger.info(f"Resource monitor initialized (CPU limit: {self.max_cpu_percent}%)")

    def check_cpu_usage(self, wait: bool = True) -> float:
        """
        Check current CPU usage and throttle if needed.

        Args:
            wait: If True, sleep until CPU usage is acceptable

        Returns:
            Current CPU usage percentage
        """
        if not PSUTIL_AVAILABLE:
            return 0.0

        try:
            cpu_percent = psutil.cpu_percent(interval=1)

            if cpu_percent > self.max_cpu_percent:
                logger.warning(f"High CPU usage: {cpu_percent:.1f}% (limit: {self.max_cpu_percent}%)")

                if wait:
                    # Throttle: wait until CPU usage decreases
                    while cpu_percent > self.max_cpu_percent:
                        logger.debug("Throttling: waiting for CPU to decrease...")
                        time.sleep(2)
                        cpu_percent = psutil.cpu_percent(interval=1)

                    logger.info(f"CPU usage acceptable: {cpu_percent:.1f}%")

            return cpu_percent

        except Exception as e:
            logger.error(f"Failed to check CPU usage: {e}")
            return 0.0

    def get_memory_usage(self) -> Dict[str, float]:
        """
        Get current memory usage statistics.

        Returns:
            Dict with memory stats (percent, available MB, used MB)
        """
        if not PSUTIL_AVAILABLE:
            return {'percent': 0, 'available_mb': 0, 'used_mb': 0}

        try:
            memory = psutil.virtual_memory()

            stats = {
                'percent': memory.percent,
                'available_mb': memory.available / (1024 * 1024),
                'used_mb': memory.used / (1024 * 1024),
                'total_mb': memory.total / (1024 * 1024),
            }

            if memory.percent > 80:
                logger.warning(f"High memory usage: {memory.percent:.1f}%")

            return stats

        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {'percent': 0, 'available_mb': 0, 'used_mb': 0}

    def get_temperature(self) -> Optional[float]:
        """
        Get CPU temperature (Raspberry Pi specific).

        Returns:
            Temperature in Celsius or None if unavailable
        """
        try:
            if os.path.exists(self.temp_file):
                with open(self.temp_file, 'r') as f:
                    temp = float(f.read().strip()) / 1000.0

                if temp > 70:
                    logger.warning(f"High CPU temperature: {temp:.1f}°C")
                elif temp > 80:
                    logger.error(f"Critical CPU temperature: {temp:.1f}°C - throttling likely!")

                return temp

        except Exception as e:
            logger.debug(f"Failed to read temperature: {e}")

        return None

    def optimize_memory(self) -> None:
        """
        Perform memory optimization.

        Actions:
        - Force garbage collection
        - Log memory stats
        """
        if self.gc_enabled:
            # Get memory before GC
            mem_before = self.get_memory_usage()

            # Force garbage collection
            gc.collect()

            # Get memory after GC
            mem_after = self.get_memory_usage()

            freed_mb = mem_before['used_mb'] - mem_after['used_mb']

            if freed_mb > 1:  # Only log if significant
                logger.info(f"Garbage collection freed {freed_mb:.1f} MB")

    def log_system_stats(self) -> None:
        """Log current system statistics."""
        if not self.log_performance:
            return

        try:
            stats = []

            # CPU
            if PSUTIL_AVAILABLE:
                cpu = psutil.cpu_percent(interval=0.5)
                stats.append(f"CPU: {cpu:.1f}%")

            # Memory
            mem = self.get_memory_usage()
            if mem['percent'] > 0:
                stats.append(f"Memory: {mem['percent']:.1f}% ({mem['used_mb']:.0f}/{mem['total_mb']:.0f} MB)")

            # Temperature
            temp = self.get_temperature()
            if temp:
                stats.append(f"Temp: {temp:.1f}°C")

            # Uptime
            if PSUTIL_AVAILABLE:
                uptime = time.time() - psutil.boot_time()
                hours = int(uptime / 3600)
                stats.append(f"Uptime: {hours}h")

            if stats:
                logger.info("System stats: " + " | ".join(stats))

        except Exception as e:
            logger.error(f"Failed to log system stats: {e}")

    def enable_low_power_mode(self) -> None:
        """
        Enable low-power mode optimizations.

        Note: This is a placeholder. Actual implementation would require
        system-level changes (e.g., CPU governor settings).
        """
        if not self.low_power_mode:
            return

        logger.info("Low-power mode enabled (placeholder)")

        # On a real Raspberry Pi, you might:
        # 1. Set CPU governor to 'powersave'
        #    echo "powersave" | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
        # 2. Disable HDMI output
        #    /usr/bin/tvservice -o
        # 3. Disable LEDs
        #    echo 0 | sudo tee /sys/class/leds/led0/brightness
        # 4. Reduce GPU memory

    def wait_for_resources(self, operation_name: str = "operation") -> None:
        """
        Wait until system resources are available for operation.

        Args:
            operation_name: Name of operation for logging
        """
        logger.debug(f"Checking resources before {operation_name}")

        # Check CPU
        cpu = self.check_cpu_usage(wait=True)

        # Check memory
        mem = self.get_memory_usage()
        if mem['percent'] > 90:
            logger.warning(f"Memory very high ({mem['percent']:.1f}%), optimizing...")
            self.optimize_memory()

            # Wait a bit for memory to stabilize
            time.sleep(1)

        # Check temperature
        temp = self.get_temperature()
        if temp and temp > 75:
            logger.warning(f"Temperature high ({temp:.1f}°C), waiting to cool down...")
            while temp and temp > 70:
                time.sleep(5)
                temp = self.get_temperature()

        logger.debug(f"Resources OK for {operation_name}")

    def get_resource_report(self) -> Dict[str, Any]:
        """
        Get comprehensive resource report.

        Returns:
            Dict with all resource metrics
        """
        report = {
            'timestamp': time.time(),
            'cpu_percent': 0,
            'memory': {},
            'temperature': None,
        }

        try:
            if PSUTIL_AVAILABLE:
                report['cpu_percent'] = psutil.cpu_percent(interval=0.5)

            report['memory'] = self.get_memory_usage()
            report['temperature'] = self.get_temperature()

        except Exception as e:
            logger.error(f"Failed to generate resource report: {e}")

        return report


def measure_execution_time(func):
    """
    Decorator to measure and log function execution time.

    Usage:
        @measure_execution_time
        def my_function():
            pass
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        logger.info(f"{func.__name__} completed in {elapsed:.2f}s")

        return result

    return wrapper
