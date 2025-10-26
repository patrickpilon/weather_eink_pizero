#!/usr/bin/env python3
"""
Weather E-Ink Display for Raspberry Pi Zero
Main application with performance optimizations
"""

import argparse
import gc
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Optional

import yaml

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from weather_api import WeatherAPIClient
from display_controller import DisplayController
from resource_monitor import ResourceMonitor, measure_execution_time


class WeatherEInkApp:
    """
    Main application class with optimized update loop.

    Performance features:
    - Smart update scheduling (quiet hours, change detection)
    - Resource monitoring and throttling
    - Graceful shutdown handling
    - Error recovery with backoff
    - Memory optimization
    """

    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize application with configuration."""
        self.config = self._load_config(config_path)
        self._setup_logging()

        logger.info("=" * 60)
        logger.info("Weather E-Ink Display for Raspberry Pi Zero")
        logger.info("=" * 60)

        # Initialize components
        self.weather_client = WeatherAPIClient(self.config)
        self.display = DisplayController(self.config)
        self.resource_monitor = ResourceMonitor(self.config)

        # Application state
        self.running = False
        self.update_count = 0
        self.error_count = 0
        self.last_update_time = 0

        # Configuration
        self.update_interval = self.config.get('update', {}).get('interval', 1800)
        self.update_only_on_change = self.config.get('update', {}).get('update_only_on_change', True)
        self.quiet_hours_start = self.config.get('update', {}).get('quiet_hours_start', 23)
        self.quiet_hours_end = self.config.get('update', {}).get('quiet_hours_end', 7)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"Application initialized (update interval: {self.update_interval}s)")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            print(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            print(f"Error: Configuration file not found: {config_path}")
            print("Please copy config.yaml.example to config.yaml and configure it.")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing configuration file: {e}")
            sys.exit(1)

    def _setup_logging(self):
        """Setup logging configuration with fallback for permission issues."""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', 'app.log')

        # Try to create log directory if needed
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except PermissionError:
                # Fallback to local logs directory if we can't write to system location
                print(f"Warning: Cannot create log directory {log_dir} (permission denied)")
                local_log_dir = os.path.join(os.path.dirname(__file__), 'logs')
                log_file = os.path.join(local_log_dir, os.path.basename(log_file))
                print(f"Falling back to local log directory: {log_file}")

                # Create local logs directory
                os.makedirs(local_log_dir, exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

        global logger
        logger = logging.getLogger(__name__)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        current_hour = datetime.now().hour

        if self.quiet_hours_start < self.quiet_hours_end:
            # Normal case (e.g., 23:00 - 07:00 next day)
            return current_hour >= self.quiet_hours_start or current_hour < self.quiet_hours_end
        else:
            # Spans midnight (e.g., 22:00 - 06:00)
            return self.quiet_hours_start <= current_hour < self.quiet_hours_end

    @measure_execution_time
    def _perform_update(self) -> bool:
        """
        Perform a single weather update cycle.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check resources before starting
            self.resource_monitor.wait_for_resources("weather update")

            # Fetch weather data
            logger.info("Fetching weather data...")
            weather_data = self.weather_client.get_weather()

            if not weather_data:
                logger.error("Failed to fetch weather data")
                self.error_count += 1
                return False

            # Log weather info
            temp = weather_data.get('temperature', 'N/A')
            desc = weather_data.get('description', 'N/A')
            logger.info(f"Weather: {temp}°C, {desc}")

            # Update display
            logger.info("Updating display...")
            force_update = not self.update_only_on_change
            updated = self.display.update_display(weather_data, force_update=force_update)

            if updated:
                logger.info("Display updated successfully")
                self.update_count += 1
            else:
                logger.info("Display unchanged (data identical)")

            # Clean up memory
            self.resource_monitor.optimize_memory()

            # Log system stats
            self.resource_monitor.log_system_stats()

            self.error_count = 0  # Reset error count on success
            return True

        except Exception as e:
            logger.error(f"Update failed with exception: {e}", exc_info=True)
            self.error_count += 1
            return False

    def run(self):
        """Main application loop."""
        self.running = True

        logger.info("Starting main loop...")
        logger.info(f"Update interval: {self.update_interval}s")
        logger.info(f"Quiet hours: {self.quiet_hours_start}:00 - {self.quiet_hours_end}:00")

        # Enable low-power optimizations
        self.resource_monitor.enable_low_power_mode()

        # Perform initial update
        logger.info("Performing initial update...")
        self._perform_update()
        self.last_update_time = time.time()

        # Main loop
        while self.running:
            try:
                # Calculate time until next update
                elapsed = time.time() - self.last_update_time
                time_until_update = max(0, self.update_interval - elapsed)

                # Sleep in small intervals to allow for responsive shutdown
                while time_until_update > 0 and self.running:
                    sleep_time = min(10, time_until_update)  # Wake up every 10s to check
                    time.sleep(sleep_time)
                    time_until_update -= sleep_time

                if not self.running:
                    break

                # Check quiet hours
                if self._is_quiet_hours():
                    logger.debug("Quiet hours active, skipping update")
                    self.last_update_time = time.time()
                    continue

                # Perform update
                success = self._perform_update()
                self.last_update_time = time.time()

                # Error handling with backoff
                if not success:
                    if self.error_count >= 3:
                        # Multiple failures: increase wait time
                        backoff = min(self.error_count * 300, 3600)  # Max 1 hour
                        logger.warning(f"Multiple failures ({self.error_count}), waiting {backoff}s before retry")
                        time.sleep(backoff)

                # Log statistics
                logger.info(f"Update #{self.update_count} complete (errors: {self.error_count})")

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.running = False
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                time.sleep(60)  # Wait before retrying

        # Shutdown
        self.shutdown()

    def shutdown(self):
        """Clean shutdown of application."""
        logger.info("Shutting down application...")

        try:
            # Put display to sleep
            self.display.sleep_display()

            # Final stats
            logger.info(f"Total updates performed: {self.update_count}")
            logger.info(f"Total errors: {self.error_count}")

            # Resource report
            report = self.resource_monitor.get_resource_report()
            logger.info(f"Final resource usage: CPU={report['cpu_percent']:.1f}%, "
                       f"Memory={report['memory'].get('percent', 0):.1f}%")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        logger.info("Shutdown complete")

    def test_update(self):
        """Perform a single test update (for testing)."""
        logger.info("Running test update...")
        success = self._perform_update()

        if success:
            logger.info("Test update successful!")
            return 0
        else:
            logger.error("Test update failed!")
            return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Weather E-Ink Display for Raspberry Pi Zero')
    parser.add_argument('-c', '--config', default='config.yaml',
                       help='Path to configuration file (default: config.yaml)')
    parser.add_argument('-t', '--test', action='store_true',
                       help='Run a single test update and exit')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    # Create application
    try:
        app = WeatherEInkApp(config_path=args.config)

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Run in test mode or continuous mode
        if args.test:
            sys.exit(app.test_update())
        else:
            app.run()

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
