#!/bin/bash
# AllTool-Linux Installer - installs to ~/.config/alltool

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if make is installed
if ! command -v make &> /dev/null; then
    echo "Error: 'make' is not installed. Please install it first."
    echo "  Debian/Ubuntu: sudo apt install make"
    echo "  Fedora: sudo dnf install make"
    echo "  Arch: sudo pacman -S make"
    exit 1
fi

# Check for gcc
if ! command -v gcc &> /dev/null; then
    echo "Error: 'gcc' is not installed. Please install build-essential or equivalent."
    echo "  Debian/Ubuntu: sudo apt install build-essential"
    echo "  Fedora: sudo dnf install gcc"
    echo "  Arch: sudo pacman -S base-devel"
    exit 1
fi

# Check for pip3
if ! command -v pip3 &> /dev/null; then
    echo "Error: 'pip3' is not installed. Please install python3-pip."
    echo "  Debian/Ubuntu: sudo apt install python3-pip"
    echo "  Fedora: sudo dnf install python3-pip"
    echo "  Arch: sudo pacman -S python-pip"
    exit 1
fi

# Check for pkg-config (needed for some builds)
if ! command -v pkg-config &> /dev/null; then
    echo "Warning: 'pkg-config' not found. Some builds may fail."
    echo "  Debian/Ubuntu: sudo apt install pkg-config"
    echo "  Fedora: sudo dnf install pkg-config"
    echo "  Arch: sudo pacman -S pkg-config"
fi

# Check Python dependencies
echo "Checking Python dependencies..."
python3 -c "import requests" 2>/dev/null || {
    echo "Installing missing Python package: requests"
    pip3 install requests --break-system-packages 2>/dev/null || pip3 install requests
}
python3 -c "import bs4" 2>/dev/null || {
    echo "Installing missing Python package: beautifulsoup4"
    pip3 install beautifulsoup4 --break-system-packages 2>/dev/null || pip3 install beautifulsoup4
}
python3 -c "import packaging" 2>/dev/null || {
    echo "Installing missing Python package: packaging"
    pip3 install packaging --break-system-packages 2>/dev/null || pip3 install packaging
}

# Check external commands (warn only, not fatal)
echo "Checking external commands..."
MISSING_CMDS=()
for cmd in mpv ffmpeg yt-dlp speedtest-cli inxi; do
    if ! command -v "$cmd" &> /dev/null; then
        MISSING_CMDS+=("$cmd")
    fi
done

if [ ${#MISSING_CMDS[@]} -gt 0 ]; then
    echo "Warning: The following optional commands are not installed:"
    printf '  %s\n' "${MISSING_CMDS[@]}"
    echo "Some AllTool features will not work without them."
    echo ""
    echo "Install with:"
    echo "  Debian/Ubuntu: sudo apt install mpv ffmpeg yt-dlp speedtest-cli inxi"
    echo "  Fedora: sudo dnf install mpv ffmpeg yt-dlp speedtest-cli inxi"
    echo "  Arch: sudo pacman -S mpv ffmpeg yt-dlp speedtest-cli inxi"
    echo ""
fi

# Detect power management system
echo "Detecting power management system..."
POWER_MGMT=""
POWER_PROFILES=()

if command -v powerprofilesctl &> /dev/null; then
    POWER_MGMT="powerprofilesctl"
    # Get available profiles
    mapfile -t POWER_PROFILES < <(powerprofilesctl list 2>/dev/null | grep -E '^\s+\*' | sed 's/.*\*//' | xargs)
    [ ${#POWER_PROFILES[@]} -eq 0 ] && POWER_PROFILES=("power-saver" "balanced" "performance")
elif command -v tlp &> /dev/null; then
    POWER_MGMT="tlp"
    POWER_PROFILES=("ac" "battery")
elif command -v auto-cpufreq &> /dev/null; then
    POWER_MGMT="auto-cpufreq"
    POWER_PROFILES=("performance" "powersave" "balanced")
elif command -v cpupower &> /dev/null; then
    POWER_MGMT="cpupower"
    POWER_PROFILES=("performance" "powersave" "ondemand" "conservative")
elif [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    POWER_MGMT="sysfs"
    mapfile -t POWER_PROFILES < <(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null | tr ' ' '\n')
    [ ${#POWER_PROFILES[@]} -eq 0 ] && POWER_PROFILES=("performance" "powersave" "ondemand")
else
    POWER_MGMT="none"
    POWER_PROFILES=()
fi

echo "Detected power management: $POWER_MGMT"
[ ${#POWER_PROFILES[@]} -gt 0 ] && echo "Available profiles: ${POWER_PROFILES[*]}"

# Update .confs.json with power management config
CONF_FILE="$SCRIPT_DIR/.confs.json"
if [ -f "$CONF_FILE" ]; then
    # Use python to update the JSON
    python3 << EOF
import json
import os

conf_file = "$CONF_FILE"
with open(conf_file, 'r') as f:
    conf = json.load(f)

conf["power_management"] = {
    "backend": "$POWER_MGMT",
    "profiles": ${POWER_PROFILES[@]@Q}
}

with open(conf_file, 'w') as f:
    json.dump(conf, f, indent=2)

print("Updated .confs.json with power management config")
EOF
fi

echo "Installing AllTool-Linux to ~/.config/alltool..."
make install
echo "Installation complete!"
echo "Run 'alltool refresh' to update your PATH"
