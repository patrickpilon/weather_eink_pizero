#!/usr/bin/env python3
"""
Test display rendering with mock weather data.
This bypasses the API and tests the display controller directly.
"""

import sys
import os
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from display_controller import DisplayController
import yaml

# Mock weather data
mock_weather_data = {
    'temperature': 24.5,
    'feels_like': 23.8,
    'humidity': 65,
    'wind_speed': 12.5,
    'weather_code': 2,  # Partly cloudy
    'precipitation': 0,
    'location': 'São Paulo - Vila Nova Conceição',
    'timestamp': int(datetime.now().timestamp()),
    'hourly': {
        'time': [
            '2025-10-26T22:00',
            '2025-10-26T23:00',
            '2025-10-27T00:00',
            '2025-10-27T01:00',
            '2025-10-27T02:00',
            '2025-10-27T03:00',
        ],
        'temperature': [24.2, 23.8, 23.1, 22.5, 22.0, 21.8],
        'precipitation_probability': [10, 15, 20, 25, 30, 20],
        'weather_code': [2, 2, 3, 3, 51, 51]
    }
}

def main():
    print("Testing e-ink display with mock weather data...")

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Create display controller
    display = DisplayController(config)

    print(f"Display initialized: {display.display_type} ({display.width}x{display.height})")

    # Render weather image
    print("Rendering weather image...")
    image = display._render_weather_image(mock_weather_data)

    # Save image to file for inspection
    output_path = 'test_display_output.png'
    image.save(output_path)
    print(f"Image saved to: {output_path}")
    print(f"Image size: {image.size}")

    # Try to update the display
    print("\nAttempting to update display...")
    success = display.update_display(mock_weather_data, force_update=True)

    if success:
        print("✓ Display updated successfully!")
        print(f"Display driver type: {type(display.display_driver).__name__}")
    else:
        print("✗ Display update failed")
        return 1

    print("\n" + "="*60)
    print("Test completed successfully!")
    print(f"Check the generated image: {output_path}")
    print("="*60)

    return 0

if __name__ == '__main__':
    sys.exit(main())
