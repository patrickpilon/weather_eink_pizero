"""
E-Ink Display Controller with Memory Optimization
Optimized for Raspberry Pi Zero - minimizes memory usage and display updates
"""

import gc
import hashlib
import logging
import os
from typing import Dict, Any, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class DisplayController:
    """
    Memory-efficient e-ink display controller.

    Performance optimizations:
    - Partial refresh support (faster, less wear)
    - Image hash comparison (only update on change)
    - Memory cleanup after operations
    - Pre-allocated buffers
    - Lazy display driver initialization
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.display_config = config.get('display', {})
        self.perf_config = config.get('performance', {})

        # Display properties
        self.display_type = self.display_config.get('type', 'waveshare_2in13')
        self.rotation = self.display_config.get('rotation', 0)
        self.partial_refresh = self.display_config.get('partial_refresh', True)
        self.partial_refresh_limit = self.display_config.get('partial_refresh_limit', 10)

        # Display dimensions (set based on display type)
        self.width, self.height = self._get_display_dimensions()

        # State tracking
        self.last_image_hash = None
        self.partial_refresh_count = 0
        self.display_driver = None

        # Memory limit for image processing (MB)
        self.max_image_memory = self.perf_config.get('max_image_memory', 50) * 1024 * 1024

        logger.info(f"Display controller initialized: {self.display_type} ({self.width}x{self.height})")

    def _get_display_dimensions(self) -> Tuple[int, int]:
        """Get display dimensions based on display type."""
        # Common e-ink display sizes
        dimensions = {
            'waveshare_2in13': (250, 122),
            'waveshare_2in13_v2': (250, 122),
            'waveshare_2in9': (296, 128),
            'waveshare_4in2': (400, 300),
            'waveshare_4in26': (800, 480),
            'waveshare_7in5': (800, 480),
        }

        dims = dimensions.get(self.display_type, (250, 122))

        # Apply rotation
        if self.rotation in (90, 270):
            return (dims[1], dims[0])
        return dims

    def _init_display_driver(self):
        """
        Lazy initialization of display driver.
        Only import and initialize when actually needed.
        """
        if self.display_driver is not None:
            return

        try:
            # Import display driver based on type
            if 'waveshare' in self.display_type.lower():
                # Import appropriate Waveshare display driver
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lib'))

                if self.display_type == 'waveshare_4in26':
                    from waveshare_epd import epd4in26
                    self.display_driver = epd4in26.EPD()
                    logger.info("Loaded Waveshare 4.26\" display driver")
                elif self.display_type == 'waveshare_2in13_v2':
                    from waveshare_epd import epd2in13_v2
                    self.display_driver = epd2in13_v2.EPD()
                    logger.info("Loaded Waveshare 2.13\" V2 display driver")
                else:
                    logger.warning(f"No specific driver for {self.display_type}, using mock")
                    self.display_driver = MockDisplayDriver()
            else:
                logger.warning(f"Unsupported display type: {self.display_type}")
                self.display_driver = MockDisplayDriver()

            # Initialize display
            if hasattr(self.display_driver, 'init') and not isinstance(self.display_driver, MockDisplayDriver):
                self.display_driver.init()
                logger.info("Display driver initialized")

        except ImportError as e:
            logger.error(f"Failed to import display driver: {e}")
            logger.info("Using mock display driver (no physical display)")
            self.display_driver = MockDisplayDriver()
        except Exception as e:
            logger.error(f"Failed to initialize display: {e}")
            self.display_driver = MockDisplayDriver()

    def update_display(self, weather_data: Dict[str, Any], force_update: bool = False) -> bool:
        """
        Update e-ink display with weather data.

        Args:
            weather_data: Weather data dictionary
            force_update: Force update even if data hasn't changed

        Returns:
            True if display was updated, False otherwise
        """
        try:
            # Generate display image
            image = self._render_weather_image(weather_data)

            # Calculate image hash to detect changes
            image_hash = self._calculate_image_hash(image)

            # Check if update is needed
            if not force_update and image_hash == self.last_image_hash:
                logger.info("Weather data unchanged, skipping display update")
                return False

            # Initialize display driver if needed
            self._init_display_driver()

            # Determine refresh mode
            use_partial = (
                self.partial_refresh and
                self.partial_refresh_count < self.partial_refresh_limit
            )

            # Update display
            if use_partial:
                logger.info(f"Updating display (partial refresh {self.partial_refresh_count + 1}/{self.partial_refresh_limit})")
                self._display_partial_refresh(image)
                self.partial_refresh_count += 1
            else:
                logger.info("Updating display (full refresh)")
                self._display_full_refresh(image)
                self.partial_refresh_count = 0

            # Save image hash
            self.last_image_hash = image_hash

            # Clean up memory
            del image
            if self.perf_config.get('gc_enabled', True):
                gc.collect()

            logger.info("Display updated successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to update display: {e}")
            return False

    def _render_weather_image(self, weather_data: Dict[str, Any]) -> Image.Image:
        """
        Render weather data to an image.

        This is a simplified version. In production, you'd add:
        - Custom fonts
        - Weather icons
        - Layouts for different display sizes
        """
        # Create image with white background
        image = Image.new('1', (self.width, self.height), 255)  # '1' = 1-bit pixels (black/white)
        draw = ImageDraw.Draw(image)

        try:
            # Use default font (or load custom font if available)
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

            # Extract weather data
            temp = weather_data.get('temperature', 0)
            desc = weather_data.get('description', 'N/A')
            humidity = weather_data.get('humidity', 0)
            location = weather_data.get('location', 'Unknown')

            # Layout (simplified)
            y_offset = 10

            # Location
            draw.text((10, y_offset), location, font=font_small, fill=0)
            y_offset += 20

            # Temperature (large)
            temp_text = f"{temp:.1f}°C" if self.config.get('weather', {}).get('units') == 'metric' else f"{temp:.1f}°F"
            draw.text((10, y_offset), temp_text, font=font_large, fill=0)
            y_offset += 30

            # Description
            draw.text((10, y_offset), desc.capitalize(), font=font_small, fill=0)
            y_offset += 20

            # Humidity
            draw.text((10, y_offset), f"Humidity: {humidity}%", font=font_small, fill=0)

        except Exception as e:
            logger.error(f"Error rendering weather image: {e}")
            # Fallback: simple error message
            draw.text((10, 10), "Error", font=font_small, fill=0)

        # Apply rotation if needed
        if self.rotation != 0:
            image = image.rotate(self.rotation, expand=True)

        return image

    def _calculate_image_hash(self, image: Image.Image) -> str:
        """Calculate hash of image for change detection."""
        return hashlib.md5(image.tobytes()).hexdigest()

    def _display_partial_refresh(self, image: Image.Image) -> None:
        """Perform partial display refresh (faster)."""
        if hasattr(self.display_driver, 'display_Partial'):
            # Waveshare drivers use getbuffer method
            buffer = self._image_to_buffer(image)
            self.display_driver.display_Partial(buffer)
        elif hasattr(self.display_driver, 'display_partial'):
            # Alternative method name
            buffer = self._image_to_buffer(image)
            self.display_driver.display_partial(buffer)
        else:
            # Fallback to full refresh
            self._display_full_refresh(image)

    def _display_full_refresh(self, image: Image.Image) -> None:
        """Perform full display refresh (cleaner)."""
        if hasattr(self.display_driver, 'display'):
            # Convert PIL image to format expected by driver
            buffer = self._image_to_buffer(image)
            self.display_driver.display(buffer)
        else:
            logger.warning("Display driver has no display method")

    def _image_to_buffer(self, image: Image.Image) -> bytes:
        """Convert PIL image to byte buffer for display driver."""
        # Waveshare drivers provide a getbuffer method
        if hasattr(self.display_driver, 'getbuffer') and not isinstance(self.display_driver, MockDisplayDriver):
            return self.display_driver.getbuffer(image)
        # Fallback for mock or other drivers
        return image.tobytes()

    def clear_display(self) -> None:
        """Clear the display (show all white)."""
        try:
            self._init_display_driver()

            if hasattr(self.display_driver, 'Clear'):
                # Waveshare drivers use Clear (capitalized)
                self.display_driver.Clear()
                logger.info("Display cleared")
            elif hasattr(self.display_driver, 'clear'):
                self.display_driver.clear()
                logger.info("Display cleared")
            else:
                # Fallback: display white image
                white_image = Image.new('1', (self.width, self.height), 255)
                self._display_full_refresh(white_image)

        except Exception as e:
            logger.error(f"Failed to clear display: {e}")

    def sleep_display(self) -> None:
        """Put display into low-power sleep mode."""
        try:
            if self.display_driver and hasattr(self.display_driver, 'sleep'):
                self.display_driver.sleep()
                logger.info("Display entered sleep mode")
        except Exception as e:
            logger.error(f"Failed to sleep display: {e}")

    def __del__(self):
        """Clean up on destruction."""
        try:
            self.sleep_display()
        except:
            pass


class MockDisplayDriver:
    """Mock display driver for testing without hardware."""

    def __init__(self):
        self.initialized = False

    def init(self):
        logger.info("Mock display initialized")
        self.initialized = True

    def display(self, buffer):
        logger.debug(f"Mock display: full refresh ({len(buffer)} bytes)")

    def display_partial(self, buffer):
        logger.debug(f"Mock display: partial refresh ({len(buffer)} bytes)")

    def clear(self):
        logger.debug("Mock display: cleared")

    def sleep(self):
        logger.debug("Mock display: sleep mode")
