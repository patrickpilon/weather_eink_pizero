# Weather E-Ink Display for Raspberry Pi Zero

A lightweight, highly optimized weather display application for Raspberry Pi Zero with e-ink displays. Designed to run efficiently on limited hardware with aggressive caching, resource monitoring, and smart update strategies.

## Features

- **Weather Data Fetching** with multi-level caching (memory + file)
- **E-Ink Display Support** with partial refresh optimization
- **Resource Monitoring** (CPU, memory, temperature)
- **Smart Update Scheduling** (quiet hours, change detection)
- **Low Power Mode** optimizations
- **Automatic Error Recovery** with exponential backoff
- **Systemd Integration** for auto-start

## Performance Optimizations for Raspberry Pi Zero

This application is specifically optimized for the Raspberry Pi Zero's limited resources:

### CPU Optimization
- ⚡ **Configurable CPU throttling** - limits CPU usage to prevent overload
- ⚡ **Connection pooling** - reuses HTTP connections to reduce overhead
- ⚡ **Lazy initialization** - only loads display drivers when needed
- ⚡ **Low-priority execution** - runs with nice level 10

### Memory Optimization
- 💾 **Aggressive garbage collection** - automatic cleanup after operations
- 💾 **Memory limits** - configurable max memory for image processing (default: 50MB)
- 💾 **Streaming operations** - avoids loading large files into memory
- 💾 **Image cleanup** - explicit deletion of image objects after use
- 💾 **Systemd memory limits** - hard cap at 100MB

### Network Optimization
- 🌐 **Multi-level caching** - default 30-minute cache prevents excessive API calls
- 🌐 **Timeout protection** - prevents hanging on slow networks (10s default)
- 🌐 **Retry logic** - exponential backoff for failed requests
- 🌐 **File cache persistence** - survives restarts

### Display Optimization
- 🖥️ **Partial refresh mode** - faster updates, less wear (configurable)
- 🖥️ **Change detection** - only updates display when data changes
- 🖥️ **Smart refresh cycles** - full refresh every N partials to prevent ghosting
- 🖥️ **Sleep mode** - puts display to sleep between updates

### Power Optimization
- 🔋 **Quiet hours** - no updates during configured hours (default: 23:00-07:00)
- 🔋 **Long update intervals** - default 30 minutes between updates
- 🔋 **Temperature monitoring** - throttles when overheating
- 🔋 **Optional HDMI disable** - save ~20mA

## Hardware Requirements

- **Raspberry Pi Zero** (W or WH recommended for WiFi)
- **E-Ink Display** (Waveshare 4.26" 800x480, compatible with other Waveshare displays)
- **Power Supply** (5V micro USB, 2A+ recommended)
- **SD Card** (8GB+ recommended, Class 10)

## Software Requirements

- **Raspberry Pi OS Lite** (recommended for minimal overhead)
- **Python 3.7+**
- **Internet connection** (WiFi or Ethernet adapter)

## Installation

### Quick Install

```bash
git clone https://github.com/patrickpilon/weather_eink_pizero.git
cd weather_eink_pizero
chmod +x install.sh
./install.sh
```

The installation script will:
1. Install system dependencies
2. Create a Python virtual environment
3. Install Python packages
4. Create configuration file
5. Optionally install systemd service
6. Optionally apply Pi Zero optimizations

### Manual Install

```bash
# 1. Install system dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-pil libopenjp2-7 libtiff5

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure application
cp config.yaml.example config.yaml
nano config.yaml  # Edit with your settings
```

## Configuration

Edit `config.yaml` to configure:

### Weather API

Get a free API key from [OpenWeatherMap](https://openweathermap.org/api) or [WeatherAPI](https://www.weatherapi.com/)

```yaml
weather:
  provider: "openweathermap"
  api_key: "YOUR_API_KEY_HERE"
  latitude: 40.7128
  longitude: -74.0060
  cache_duration: 1800  # 30 minutes
```

### Performance Tuning

```yaml
performance:
  max_image_memory: 50        # MB
  api_timeout: 10             # seconds
  gc_enabled: true            # Enable garbage collection
  low_power_mode: true        # Enable power optimizations
  max_cpu_percent: 80         # CPU throttling threshold
```

### Update Schedule

```yaml
update:
  interval: 1800              # 30 minutes
  update_only_on_change: true # Only update if data changed
  quiet_hours_start: 23       # 11 PM
  quiet_hours_end: 7          # 7 AM
```

See `config.yaml.example` for all options.

## Usage

### Test Mode

Run a single update to test configuration:

```bash
./venv/bin/python3 main.py --test
```

### Continuous Mode

Run continuously with automatic updates:

```bash
./venv/bin/python3 main.py
```

### Systemd Service

For automatic startup on boot:

```bash
# Install service (if not done during install.sh)
sudo cp systemd/weather-eink.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable weather-eink
sudo systemctl start weather-eink

# Check status
sudo systemctl status weather-eink

# View logs
sudo journalctl -u weather-eink -f
```

## Performance Monitoring

The application logs resource usage regularly:

```
System stats: CPU: 12.5% | Memory: 45.2% (230/512 MB) | Temp: 42.3°C | Uptime: 48h
```

### Interpreting Metrics

- **CPU**: Should stay well below max_cpu_percent (default 80%)
- **Memory**: Should stay below 80% (< 410MB on Pi Zero)
- **Temperature**: Should stay below 70°C (throttles at 75°C+)

### Troubleshooting High Resource Usage

If you see high resource usage:

1. **Increase update interval** - Less frequent updates = lower resource usage
   ```yaml
   update:
     interval: 3600  # 1 hour instead of 30 minutes
   ```

2. **Enable update-only-on-change** - Skip unnecessary display refreshes
   ```yaml
   update:
     update_only_on_change: true
   ```

3. **Reduce max CPU percent** - More aggressive throttling
   ```yaml
   performance:
     max_cpu_percent: 50  # Lower threshold
   ```

4. **Use partial refresh** - Faster, less resource-intensive
   ```yaml
   display:
     partial_refresh: true
   ```

5. **Check temperature** - Ensure adequate cooling
   ```bash
   vcgencmd measure_temp
   ```

## Advanced Optimizations

### Disable HDMI (saves ~20mA)

```bash
sudo /usr/bin/tvservice -o
```

Add to `/boot/config.txt`:
```
hdmi_blanking=1
```

### Set CPU Governor to Powersave

```bash
echo "powersave" | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
```

### Reduce GPU Memory

Add to `/boot/config.txt`:
```
gpu_mem=16
```

### Disable Swap (optional, extends SD card life)

```bash
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo update-rc.d dphys-swapfile remove
```

## Project Structure

```
weather_eink_pizero/
├── main.py                    # Main application
├── config.yaml.example        # Example configuration
├── config.yaml                # Your configuration (create this)
├── requirements.txt           # Python dependencies
├── install.sh                 # Installation script
├── src/
│   ├── weather_api.py        # Weather API client with caching
│   ├── display_controller.py # E-ink display controller
│   └── resource_monitor.py   # Resource monitoring and throttling
├── systemd/
│   └── weather-eink.service  # Systemd service file
├── cache/                     # Cache directory (auto-created)
└── logs/                      # Log directory (auto-created)
```

## Resource Usage Benchmarks

Typical resource usage on Raspberry Pi Zero:

| Metric | Idle | During Update | Notes |
|--------|------|---------------|-------|
| **CPU** | <5% | 20-40% | Spikes during API call and display refresh |
| **Memory** | 40-50MB | 70-90MB | Within 100MB systemd limit |
| **Temperature** | 35-45°C | 40-50°C | Depends on ambient temperature |
| **Power** | ~120mA | ~180mA | With WiFi and e-ink display |

## Display Support

### Tested Displays
- Waveshare 4.26" (800x480) - **Default**
- Waveshare 2.13" (250x122)
- Waveshare 2.9" (296x128)
- Waveshare 4.2" (400x300)

### Adding New Displays

1. Install the display driver library
2. Update `display_controller.py` to import the driver
3. Add display dimensions to `_get_display_dimensions()`
4. Configure in `config.yaml`:
   ```yaml
   display:
     type: "your_display_type"
   ```

## Logging

Logs are written to:
- **File**: `logs/app.log` (default, configurable)
- **Console**: stdout
- **Systemd Journal**: `journalctl -u weather-eink`

Log levels:
- `DEBUG`: Verbose debugging info
- `INFO`: Normal operations (default)
- `WARNING`: Non-critical issues
- `ERROR`: Failures requiring attention

## Troubleshooting

### "Failed to fetch weather data"
- Check API key in `config.yaml`
- Verify internet connection: `ping 8.8.8.8`
- Check API service status

### "High CPU usage"
- Increase update interval
- Enable CPU throttling
- Check for runaway processes: `top`

### "High memory usage"
- Reduce max_image_memory
- Enable garbage collection
- Check for memory leaks: `free -h`

### "Display not updating"
- Check display driver installation
- Verify display type in config
- Check GPIO connections
- Review logs: `tail -f logs/app.log`

## Performance Tips

1. **Use Raspberry Pi OS Lite** - GUI uses significant resources
2. **Minimize running services** - Disable unnecessary systemd services
3. **Use local DNS cache** - Install `dnsmasq` for faster lookups
4. **Mount /tmp as tmpfs** - Reduce SD card wear
5. **Use quality SD card** - Faster I/O = better performance

## Contributing

Contributions welcome! Areas for improvement:
- Additional weather providers
- More display drivers
- Better layout rendering
- Icon support
- Multi-location support

## License

MIT License - feel free to use and modify

## Credits

- Weather data: [OpenWeatherMap](https://openweathermap.org/) / [WeatherAPI](https://www.weatherapi.com/)
- E-ink drivers: Waveshare / Adafruit
- Built for the awesome Raspberry Pi Zero community

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/patrickpilon/weather_eink_pizero/issues
- Documentation: See `docs/` directory

---

**Note**: This application prioritizes efficiency and reliability over features. It's designed to run 24/7 on a Raspberry Pi Zero without overloading the system. All optimizations are carefully chosen to balance functionality with resource constraints.
