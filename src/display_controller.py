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

# WMO Weather Code to Description Mapping
WMO_CODES = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Heavy rain",
    80: "Showers", 81: "Showers", 82: "Heavy showers",
    95: "Thunderstorm", 96: "TS w/ hail", 99: "TS w/ hail"
}


# ========== Weather Icon Drawing Functions ==========

def choose_icon_name(wcode: int) -> str:
    """Map WMO weather code to icon name."""
    if wcode in (0, 1):
        return "sun"
    if wcode == 2:
        return "partly"
    if wcode == 3:
        return "cloud"
    if wcode in (45, 48):
        return "fog"
    if wcode in (51, 53, 55):
        return "drizzle"
    if wcode in (61, 63, 65):
        return "rain"
    if wcode in (80, 81, 82):
        return "showers"
    if wcode in (95, 96, 99):
        return "thunder"
    return "cloud"


def draw_sun(d, x, y, r):
    """Draw a sun icon with rays."""
    import math
    d.ellipse((x-r, y-r, x+r, y+r), outline=0, width=6)
    for i in range(12):
        a = i * (360 / 12)
        r1 = int(r * 1.35)
        r2 = int(r * 1.7)
        x1 = x + int(r1 * math.cos(math.radians(a)))
        y1 = y + int(r1 * math.sin(math.radians(a)))
        x2 = x + int(r2 * math.cos(math.radians(a)))
        y2 = y + int(r2 * math.sin(math.radians(a)))
        d.line((x1, y1, x2, y2), fill=0, width=5)


def draw_cloud(d, box):
    """Draw a cloud icon."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx, cy = x0 + int(w * 0.5), y0 + int(h * 0.55)
    r1 = int(h * 0.30)
    r2 = int(h * 0.24)
    r3 = int(h * 0.20)
    # Three lobes + base
    d.ellipse((cx - int(w * 0.22) - r1, cy - r1, cx - int(w * 0.22) + r1, cy + r1),
              fill=1, outline=0, width=5)
    d.ellipse((cx + r1 - int(w * 0.10) - r2, cy - r2, cx + r1 - int(w * 0.10) + r2, cy + r2),
              fill=1, outline=0, width=5)
    d.ellipse((cx - int(w * 0.1) - r3, cy - int(h * 0.2) - r3,
               cx - int(w * 0.1) + r3, cy - int(h * 0.2) + r3),
              fill=1, outline=0, width=5)
    d.rectangle((x0 + int(w * 0.08), cy, x1 - int(w * 0.08), cy + int(h * 0.25)),
                fill=1, outline=0, width=0)
    # Outline bottom
    d.arc((x0 + int(w * 0.02), cy - int(h * 0.05), x1 - int(w * 0.02), cy + int(h * 0.55)),
          0, 180, fill=0, width=5)


def draw_raindrops(d, x, y, spacing, n, size):
    """Draw rain drops."""
    for i in range(n):
        xi = x + i * spacing
        d.ellipse((xi - size, y, xi + size, y + size * 2), outline=0, width=4)


def draw_zap(d, x, y, scale):
    """Draw a lightning bolt."""
    s = scale
    pts = [(x, y), (x + int(0.22 * s), y), (x - int(0.05 * s), y + int(0.35 * s)),
           (x + int(0.18 * s), y + int(0.35 * s)), (x - int(0.28 * s), y + int(0.95 * s)),
           (x, y + int(0.45 * s))]
    d.polygon(pts, outline=0, fill=0)


def draw_fog(d, x0, y0, w, lines, gap, thickness=6):
    """Draw fog lines."""
    y = y0
    for _ in range(lines):
        d.line((x0, y, x0 + w, y), fill=0, width=thickness)
        y += gap


def draw_icon(icon_name: str, size: int = 240) -> Image.Image:
    """
    Draw a weather icon as a vector-style image.

    Args:
        icon_name: Icon name (sun, cloud, rain, etc.)
        size: Icon size in pixels (default 240)

    Returns:
        PIL Image with the drawn icon
    """
    img = Image.new("1", (size, size), 1)
    d = ImageDraw.Draw(img)
    pad = 14

    if icon_name == "sun":
        draw_sun(d, size // 2, size // 2, size // 3)
    elif icon_name == "partly":
        # Small sun behind cloud
        draw_sun(d, int(size * 0.35), int(size * 0.35), int(size * 0.22))
        draw_cloud(d, (pad, int(size * 0.35), size - pad, size - int(size * 0.05)))
    elif icon_name == "cloud":
        draw_cloud(d, (pad, int(size * 0.28), size - pad, size - int(size * 0.05)))
    elif icon_name == "drizzle":
        draw_cloud(d, (pad, int(size * 0.22), size - pad, int(size * 0.70)))
        draw_raindrops(d, int(size * 0.25), int(size * 0.72), int(size * 0.16), 5, int(size * 0.035))
    elif icon_name == "rain":
        draw_cloud(d, (pad, int(size * 0.18), size - pad, int(size * 0.66)))
        draw_raindrops(d, int(size * 0.20), int(size * 0.70), int(size * 0.14), 6, int(size * 0.045))
    elif icon_name == "showers":
        draw_cloud(d, (pad, int(size * 0.14), size - pad, int(size * 0.62)))
        draw_raindrops(d, int(size * 0.18), int(size * 0.66), int(size * 0.14), 6, int(size * 0.05))
    elif icon_name == "thunder":
        draw_cloud(d, (pad, int(size * 0.14), size - pad, int(size * 0.64)))
        draw_zap(d, int(size * 0.50), int(size * 0.70), int(size * 0.40))
    elif icon_name == "fog":
        draw_cloud(d, (pad, int(size * 0.20), size - pad, int(size * 0.58)))
        draw_fog(d, int(size * 0.12), int(size * 0.70), int(size * 0.76), 3, int(size * 0.10), thickness=6)
    else:
        draw_cloud(d, (pad, int(size * 0.22), size - pad, int(size * 0.68)))

    return img


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
                result = self.display_driver.init()
                if result == 0:
                    logger.info("Display driver initialized successfully")
                elif result == -1:
                    logger.error("Display driver initialization failed (returned -1)")
                    logger.error("Check hardware connections and SPI configuration")
                    raise RuntimeError("Display initialization failed")
                else:
                    logger.warning(f"Display driver init returned unexpected value: {result}")
                    logger.info("Display driver initialized (with warnings)")

        except ImportError as e:
            error_msg = str(e)
            if 'spidev' in error_msg or 'gpiozero' in error_msg:
                # Expected when running on non-Raspberry Pi hardware (development/testing)
                logger.info("Running without hardware dependencies (spidev/gpiozero)")
                logger.info("Using mock display driver - no physical display output")
                logger.debug("To use real hardware, install with: pip install -r requirements-hardware.txt")
            else:
                # Unexpected import error
                logger.error(f"Failed to import display driver: {e}")
                logger.info("Using mock display driver")
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
            logger.debug("Initializing display driver...")
            self._init_display_driver()
            logger.debug(f"Display driver ready: {type(self.display_driver).__name__}")

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
        Render weather data to an image with big icon layout.

        Layout:
        - Header with location and date/time
        - Current weather (top-left)
        - Big weather icon (bottom-left)
        - Next 6 hours forecast (right side)
        - Footer with data source
        """
        from datetime import datetime

        W, H = self.width, self.height  # 800x480 for Waveshare 4.26"
        image = Image.new('1', (W, H), 1)  # '1' = 1-bit pixels, white background
        draw = ImageDraw.Draw(image)

        try:
            # Load fonts (using DejaVu Sans if available, fallback to default)
            try:
                font_h1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
                font_h2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
                font_m = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
                font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            except Exception:
                logger.warning("Could not load DejaVu fonts, using default")
                font_h1 = ImageFont.load_default()
                font_h2 = ImageFont.load_default()
                font_m = ImageFont.load_default()
                font_s = ImageFont.load_default()

            # Get current time
            now = datetime.now()

            # Extract weather data
            temp = weather_data.get('temperature', 0)
            feels_like = weather_data.get('feels_like', temp)
            humidity = weather_data.get('humidity', 0)
            wind_speed = weather_data.get('wind_speed', 0)
            weather_code = int(weather_data.get('weather_code', 0))
            description = WMO_CODES.get(weather_code, f"Code {weather_code}")
            location = weather_data.get('location', 'São Paulo')

            # Header
            draw.text((20, 18), f"{location} Weather", font=font_h1, fill=0)
            draw.text((20, 72), now.strftime("%a %d %b %Y • %H:%M"), font=font_m, fill=0)
            draw.line((20, 100, W - 20, 100), fill=0, width=2)

            # Current weather block (top-left)
            y = 120
            draw.text((20, y), f"{temp:.0f}°C", font=font_h1, fill=0)
            y += 50
            draw.text((20, y), description, font=font_h2, fill=0)
            y += 34
            draw.text((20, y), f"Feels {feels_like:.0f}°  Hum {humidity}%  Wind {wind_speed:.0f} km/h",
                     font=font_m, fill=0)

            # BIG weather icon (bottom-left)
            icon_name = choose_icon_name(weather_code)
            icon_img = draw_icon(icon_name, size=240)
            # Place with margin from left/bottom
            bx = 20
            by = H - 20 - icon_img.height
            image.paste(icon_img, (bx, by))

            # Next 6 hours forecast (right side)
            hourly_data = weather_data.get('hourly', {})
            times = hourly_data.get('time', [])
            temps = hourly_data.get('temperature', [])
            pops = hourly_data.get('precipitation_probability', [])
            codes = hourly_data.get('weather_code', [])

            rows = []
            for i, time_str in enumerate(times):
                if len(rows) == 6:
                    break
                try:
                    # Parse time (format: "2024-01-01T12:00" or similar)
                    if 'T' in time_str:
                        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M")
                    else:
                        continue
                except Exception:
                    continue

                # Only show future hours
                if dt >= now:
                    T = temps[i] if i < len(temps) and temps[i] is not None else 0
                    P = pops[i] if i < len(pops) and pops[i] is not None else 0
                    C = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
                    desc_hour = WMO_CODES.get(C, f"Code {C}")
                    rows.append((dt.strftime("%H:%M"), T, P, desc_hour))

            # Draw forecast section
            gx, gy = 430, 120
            draw.text((gx, gy), "Next hours", font=font_h2, fill=0)
            gy += 10
            draw.line((gx, gy + 22, W - 20, gy + 22), fill=0, width=1)
            gy += 35

            for hh, T, P, desc_hour in rows:
                draw.text((gx, gy), f"{hh}  {T:.0f}°C  POP {P:>2}%", font=font_m, fill=0)
                draw.text((gx + 250, gy), desc_hour, font=font_m, fill=0)
                gy += 40

            # Footer
            draw.line((20, H - 58, W - 20, H - 58), fill=0, width=1)
            draw.text((20, H - 48), "Data: open-meteo.com • Updates every 15 min",
                     font=font_s, fill=0)

        except Exception as e:
            logger.error(f"Error rendering weather image: {e}", exc_info=True)
            # Fallback: simple error message
            draw.text((10, 10), "Weather update failed", fill=0)
            draw.text((10, 30), str(e)[:70], fill=0)

        # Apply rotation if needed
        if self.rotation != 0:
            image = image.rotate(self.rotation, expand=True)

        return image

    def _calculate_image_hash(self, image: Image.Image) -> str:
        """Calculate hash of image for change detection."""
        return hashlib.md5(image.tobytes()).hexdigest()

    def _display_partial_refresh(self, image: Image.Image) -> None:
        """Perform partial display refresh (faster)."""
        try:
            if hasattr(self.display_driver, 'display_Partial'):
                # Waveshare drivers use getbuffer method
                buffer = self._image_to_buffer(image)
                logger.debug(f"Calling display_Partial with {len(buffer)} byte buffer")
                self.display_driver.display_Partial(buffer)
                logger.debug("display_Partial completed")
            elif hasattr(self.display_driver, 'display_partial'):
                # Alternative method name
                buffer = self._image_to_buffer(image)
                logger.debug(f"Calling display_partial with {len(buffer)} byte buffer")
                self.display_driver.display_partial(buffer)
                logger.debug("display_partial completed")
            else:
                # Fallback to full refresh
                logger.debug("No partial refresh method found, using full refresh")
                self._display_full_refresh(image)
        except Exception as e:
            logger.error(f"Partial refresh failed: {e}", exc_info=True)
            raise

    def _display_full_refresh(self, image: Image.Image) -> None:
        """Perform full display refresh (cleaner)."""
        try:
            if hasattr(self.display_driver, 'display'):
                # Convert PIL image to format expected by driver
                buffer = self._image_to_buffer(image)
                logger.debug(f"Calling display with {len(buffer)} byte buffer")
                self.display_driver.display(buffer)
                logger.debug("Full display refresh completed")
            else:
                logger.warning("Display driver has no display method")
                raise AttributeError("Display driver missing 'display' method")
        except Exception as e:
            logger.error(f"Full refresh failed: {e}", exc_info=True)
            raise

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
