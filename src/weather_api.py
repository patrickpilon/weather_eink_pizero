"""
Weather API Client with Aggressive Caching
Optimized for Raspberry Pi Zero - minimizes API calls and network usage
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import requests
from cachetools import TTLCache

logger = logging.getLogger(__name__)


class WeatherAPIClient:
    """
    Lightweight weather API client with file-based and memory caching.

    Performance optimizations:
    - Memory cache (TTL-based) for instant lookups
    - File cache for persistence across restarts
    - Connection pooling via requests.Session
    - Configurable timeouts to prevent hanging
    - Retry logic with exponential backoff
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.weather_config = config.get('weather', {})
        self.error_config = config.get('error_handling', {})
        self.perf_config = config.get('performance', {})

        # Cache configuration
        cache_duration = self.weather_config.get('cache_duration', 1800)
        self.cache_dir = 'cache'
        self.cache_file = os.path.join(self.cache_dir, 'weather_data.json')

        # In-memory cache with TTL
        self.memory_cache = TTLCache(maxsize=1, ttl=cache_duration)

        # Reusable session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'WeatherEInk/1.0'})

        # API configuration
        self.provider = self.weather_config.get('provider', 'openweathermap')
        self.api_key = self.weather_config.get('api_key')
        self.latitude = self.weather_config.get('latitude')
        self.longitude = self.weather_config.get('longitude')
        self.units = self.weather_config.get('units', 'metric')

        # Timeout configuration
        self.timeout = self.perf_config.get('api_timeout', 10)

        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        logger.info(f"Weather API client initialized with {cache_duration}s cache")

    def get_weather(self) -> Optional[Dict[str, Any]]:
        """
        Get weather data with multi-level caching.

        Returns:
            Weather data dict or None if all attempts fail
        """
        # Level 1: Check memory cache (fastest)
        cached_data = self.memory_cache.get('weather')
        if cached_data:
            logger.debug("Weather data retrieved from memory cache")
            return cached_data

        # Level 2: Check file cache
        cached_data = self._load_from_file_cache()
        if cached_data:
            logger.debug("Weather data retrieved from file cache")
            # Populate memory cache
            self.memory_cache['weather'] = cached_data
            return cached_data

        # Level 3: Fetch from API
        logger.info("Fetching fresh weather data from API")
        weather_data = self._fetch_from_api()

        if weather_data:
            # Save to both caches
            self._save_to_file_cache(weather_data)
            self.memory_cache['weather'] = weather_data
            return weather_data

        logger.error("Failed to retrieve weather data from all sources")
        return None

    def _fetch_from_api(self) -> Optional[Dict[str, Any]]:
        """
        Fetch weather data from API with retry logic.

        Returns:
            Weather data or None if all retries fail
        """
        if not self.api_key:
            logger.error("No API key configured")
            return None

        retry_enabled = self.error_config.get('retry_enabled', True)
        max_retries = self.error_config.get('max_retries', 3) if retry_enabled else 1
        backoff = self.error_config.get('retry_backoff', 2)

        for attempt in range(max_retries):
            try:
                if self.provider == 'openweathermap':
                    data = self._fetch_openweathermap()
                elif self.provider == 'weatherapi':
                    data = self._fetch_weatherapi()
                else:
                    logger.error(f"Unsupported weather provider: {self.provider}")
                    return None

                if data:
                    logger.info("Successfully fetched weather data from API")
                    return data

            except requests.exceptions.Timeout:
                logger.warning(f"API request timeout (attempt {attempt + 1}/{max_retries})")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed (attempt {attempt + 1}/{max_retries}): {e}")
            except Exception as e:
                logger.error(f"Unexpected error fetching weather: {e}")
                break

            # Exponential backoff before retry
            if attempt < max_retries - 1:
                wait_time = backoff ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

        return None

    def _fetch_openweathermap(self) -> Optional[Dict[str, Any]]:
        """Fetch data from OpenWeatherMap API."""
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': self.latitude,
            'lon': self.longitude,
            'appid': self.api_key,
            'units': self.units
        }

        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        raw_data = response.json()

        # Normalize to common format
        return {
            'temperature': raw_data['main']['temp'],
            'feels_like': raw_data['main']['feels_like'],
            'humidity': raw_data['main']['humidity'],
            'pressure': raw_data['main']['pressure'],
            'wind_speed': raw_data['wind']['speed'],
            'description': raw_data['weather'][0]['description'],
            'icon': raw_data['weather'][0]['icon'],
            'location': raw_data['name'],
            'timestamp': int(time.time()),
            'sunrise': raw_data['sys'].get('sunrise'),
            'sunset': raw_data['sys'].get('sunset'),
        }

    def _fetch_weatherapi(self) -> Optional[Dict[str, Any]]:
        """Fetch data from WeatherAPI.com."""
        url = "https://api.weatherapi.com/v1/current.json"
        params = {
            'key': self.api_key,
            'q': f"{self.latitude},{self.longitude}",
        }

        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        raw_data = response.json()

        # Convert to metric if needed
        if self.units == 'metric':
            temp = raw_data['current']['temp_c']
            feels_like = raw_data['current']['feelslike_c']
            wind_speed = raw_data['current']['wind_kph']
        else:
            temp = raw_data['current']['temp_f']
            feels_like = raw_data['current']['feelslike_f']
            wind_speed = raw_data['current']['wind_mph']

        # Normalize to common format
        return {
            'temperature': temp,
            'feels_like': feels_like,
            'humidity': raw_data['current']['humidity'],
            'pressure': raw_data['current']['pressure_mb'],
            'wind_speed': wind_speed,
            'description': raw_data['current']['condition']['text'],
            'icon': raw_data['current']['condition']['icon'],
            'location': raw_data['location']['name'],
            'timestamp': int(time.time()),
        }

    def _load_from_file_cache(self) -> Optional[Dict[str, Any]]:
        """Load weather data from file cache if still valid."""
        if not os.path.exists(self.cache_file):
            return None

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            # Check if cache is still valid
            cache_duration = self.weather_config.get('cache_duration', 1800)
            timestamp = data.get('timestamp', 0)
            age = int(time.time()) - timestamp

            if age < cache_duration:
                logger.debug(f"File cache is {age}s old (valid for {cache_duration}s)")
                return data
            else:
                logger.debug(f"File cache expired ({age}s > {cache_duration}s)")
                return None

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load file cache: {e}")
            return None

    def _save_to_file_cache(self, data: Dict[str, Any]) -> None:
        """Save weather data to file cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Weather data saved to file cache")
        except IOError as e:
            logger.warning(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> None:
        """Clear all caches (useful for testing)."""
        self.memory_cache.clear()
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        logger.info("All caches invalidated")

    def __del__(self):
        """Clean up session on destruction."""
        if hasattr(self, 'session'):
            self.session.close()
