#!/bin/bash
# Installation script for Weather E-Ink Display
# Optimized for Raspberry Pi Zero

set -e

echo "=================================="
echo "Weather E-Ink Display Installation"
echo "=================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get the directory where the script is located
INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$INSTALL_DIR"

echo "Installation directory: $INSTALL_DIR"
echo ""

# Step 1: Update system (optional)
echo "Step 1: System Update"
read -p "Update system packages? (recommended) (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Updating system packages..."
    sudo apt-get update
    sudo apt-get upgrade -y
fi

# Step 2: Install system dependencies
echo ""
echo "Step 2: Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-pil \
    libopenjp2-7 \
    libtiff5 \
    git

# Step 3: Create virtual environment
echo ""
echo "Step 3: Creating Python virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    echo "Virtual environment created"
fi

# Step 4: Install Python dependencies
echo ""
echo "Step 4: Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 5: Create configuration
echo ""
echo "Step 5: Creating configuration..."
if [ ! -f "config.yaml" ]; then
    cp config.yaml.example config.yaml
    echo "Configuration file created: config.yaml"
    echo "IMPORTANT: Edit config.yaml with your settings (API key, location, etc.)"
else
    echo "config.yaml already exists, skipping..."
fi

# Step 6: Create directories
echo ""
echo "Step 6: Creating directories..."
mkdir -p cache logs

# Step 7: Set permissions
echo ""
echo "Step 7: Setting permissions..."
chmod +x main.py
chmod 755 "$INSTALL_DIR"

# Step 8: Install systemd service (optional)
echo ""
echo "Step 8: Systemd Service"
read -p "Install systemd service for auto-start? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Update service file with current user and path
    CURRENT_USER=$(whoami)
    CURRENT_GROUP=$(id -gn)

    sed -e "s|/home/pi|$HOME|g" \
        -e "s|User=pi|User=$CURRENT_USER|g" \
        -e "s|Group=pi|Group=$CURRENT_GROUP|g" \
        systemd/weather-eink.service > /tmp/weather-eink.service

    sudo cp /tmp/weather-eink.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable weather-eink.service

    echo "Systemd service installed and enabled"
    echo "Commands:"
    echo "  Start:   sudo systemctl start weather-eink"
    echo "  Stop:    sudo systemctl stop weather-eink"
    echo "  Status:  sudo systemctl status weather-eink"
    echo "  Logs:    sudo journalctl -u weather-eink -f"
fi

# Step 9: Performance optimizations (optional)
echo ""
echo "Step 9: Performance Optimizations"
read -p "Apply Raspberry Pi Zero optimizations? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Applying optimizations..."

    # Disable HDMI (saves ~20mA)
    if ! grep -q "hdmi_blanking=1" /boot/config.txt 2>/dev/null; then
        echo "Adding HDMI blanking to /boot/config.txt"
        echo "hdmi_blanking=1" | sudo tee -a /boot/config.txt
    fi

    # Set CPU governor to powersave
    echo "Setting CPU governor to powersave..."
    echo "powersave" | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true

    echo "Optimizations applied (some require reboot)"
fi

# Step 10: Test installation
echo ""
echo "Step 10: Testing Installation"
read -p "Run test update? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running test update..."

    # Check if config has API key
    if grep -q "YOUR_API_KEY_HERE" config.yaml; then
        echo "ERROR: Please configure your API key in config.yaml first!"
        echo "Edit config.yaml and add your weather API key"
    else
        ./venv/bin/python3 main.py --test
    fi
fi

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit config.yaml with your settings"
echo "2. Test the application: ./venv/bin/python3 main.py --test"
echo "3. Run continuously: ./venv/bin/python3 main.py"
echo "4. Or use systemd: sudo systemctl start weather-eink"
echo ""
echo "Configuration file: $INSTALL_DIR/config.yaml"
echo "Log file: $INSTALL_DIR/logs/app.log"
echo ""
