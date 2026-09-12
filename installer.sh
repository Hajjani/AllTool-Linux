#!/bin/bash
# AllTool-Linux Installer
# Clones the repo, installs dependencies, sets up the tool, then cleans up.

set -e

REPO_URL="https://github.com/Hajjani/AllTool-Linux.git"
INSTALL_DIR="$HOME/bin"
SCRIPT_NAME="AllTools.py"
ENTRY_POINT="alltool"

echo "🚀 AllTool-Linux Installer"
echo "========================================"

# Create temp directory
TMPDIR=$(mktemp -d)
REPO_PATH="$TMPDIR/AllTool-Linux"
echo "📂 Cloning repo to $REPO_PATH..."
git clone "$REPO_URL" "$REPO_PATH"
cd "$REPO_PATH"

# Detect distro
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        case "$ID" in
            debian|ubuntu) echo "debian" ;;
            arch) echo "arch" ;;
            fedora) echo "fedora" ;;
            opensuse*) echo "opensuse" ;;
            *) echo "unknown" ;;
        esac
    else
        echo "unknown"
    fi
}

DISTRO=$(detect_distro)
echo "📦 Detected distro: $DISTRO"

# Install system packages
install_packages() {
    case "$DISTRO" in
        debian)
            echo "📥 Installing packages for Debian/Ubuntu..."
            sudo apt update && sudo apt install -y \
                make git gcc python3-pip pkg-config \
                mpv ffmpeg yt-dlp speedtest-cli inxi power-profiles-daemon \
                python3 python3-pip nodejs ruby php default-jre g++ \
                python3-requests python3-bs4
            ;;
        arch)
            echo "📥 Installing packages for Arch Linux..."
            sudo pacman -S --noconfirm \
                make git gcc python-pip pkg-config \
                mpv ffmpeg yt-dlp speedtest-cli inxi power-profiles-daemon \
                python python-pip nodejs ruby php jre-openjdk gcc \
                python-requests python-beautifulsoup4
            ;;
        fedora)
            echo "📥 Installing packages for Fedora..."
            sudo dnf install -y \
                make git gcc python3-pip pkg-config \
                mpv ffmpeg yt-dlp speedtest-cli inxi power-profiles-daemon \
                python3 python3-pip nodejs ruby php java-latest-openjdk gcc-c++ \
                python3-requests python3-beautifulsoup4
            ;;
        opensuse)
            echo "📥 Installing packages for openSUSE..."
            sudo zypper install -y \
                make git gcc python3-pip pkg-config \
                mpv ffmpeg yt-dlp speedtest-cli inxi power-profiles-daemon \
                python3 python3-pip nodejs ruby php java-latest-openjdk gcc-c++ \
                python3-requests python3-beautifulsoup4
            ;;
        *)
            echo "⚠️  Unknown distro, skipping system package installation"
            ;;
    esac
}

install_packages

# Install Python packages
echo "🐍 Installing Python packages..."
python3 -m pip install --user requests beautifulsoup4 packaging

# Check external commands (warn only)
echo "🔍 Checking external commands..."
MISSING_CMDS=()
for cmd in mpv ffmpeg yt-dlp speedtest-cli inxi; do
    if ! command -v "$cmd" &> /dev/null; then
        MISSING_CMDS+=("$cmd")
    fi
done

if [ ${#MISSING_CMDS[@]} -gt 0 ]; then
    echo "⚠️  The following optional commands are not installed:"
    printf '  %s\n' "${MISSING_CMDS[@]}"
    echo "Some AllTool features will not work without them."
fi

# Detect power management system
echo "⚡ Detecting power management system..."
POWER_MGMT=""
POWER_PROFILES=()

if command -v powerprofilesctl &> /dev/null; then
    POWER_MGMT="powerprofilesctl"
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
CONF_FILE="$REPO_PATH/.confs.json"
if [ -f "$CONF_FILE" ]; then
    python3 << EOF
import json
conf_file = "$CONF_FILE"
with open(conf_file, 'r') as f:
    conf = json.load(f)

conf["power_management"] = {
    "backend": "$POWER_MGMT",
    "profiles": $(printf '%s\n' "${POWER_PROFILES[@]@Q}")
}

with open(conf_file, 'w') as f:
    json.dump(conf, f, indent=2)

print("Updated .confs.json with power management config")
EOF
fi

# Run make install
echo "🔨 Running make install..."
make install

# Set up the tool in ~/bin
echo "⚙️  Setting up AllTool in ~/bin..."
mkdir -p "$INSTALL_DIR"

if [[ -f "$REPO_PATH/$SCRIPT_NAME" ]]; then
    cp "$REPO_PATH/$SCRIPT_NAME" "$INSTALL_DIR/$SCRIPT_NAME"
    chmod +x "$INSTALL_DIR/$SCRIPT_NAME"
    echo "✅ Installed $SCRIPT_NAME to $INSTALL_DIR"

    if [[ ! -f "$INSTALL_DIR/$ENTRY_POINT" && -f "$REPO_PATH/$ENTRY_POINT" ]]; then
        cp "$REPO_PATH/$ENTRY_POINT" "$INSTALL_DIR/$ENTRY_POINT"
        chmod +x "$INSTALL_DIR/$ENTRY_POINT"
        echo "✅ Installed entry point '$ENTRY_POINT' to $INSTALL_DIR"
    fi
else
    echo "❌ Source script not found: $REPO_PATH/$SCRIPT_NAME"
    exit 1
fi

if [[ -d "$REPO_PATH/Tools" ]]; then
    rm -rf "$INSTALL_DIR/Tools"
    cp -r "$REPO_PATH/Tools" "$INSTALL_DIR/Tools"
    echo "✅ Installed Tools package to $INSTALL_DIR"
fi

# Add to PATH
SHELL_RC="$HOME/.bashrc"
PATH_EXPORT='export PATH="$HOME/bin:$PATH"'
if [[ -f "$SHELL_RC" ]]; then
    if ! grep -q "$PATH_EXPORT" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "$PATH_EXPORT" >> "$SHELL_RC"
        echo "✅ Added ~/bin to PATH in $SHELL_RC"
    else
        echo "ℹ️  PATH already configured in $SHELL_RC"
    fi
fi

# Clean up cloned repo
echo "🧹 Cleaning up cloned repository..."
rm -rf "$REPO_PATH"

# Remove installer
echo "🗑️  Removing installer..."
INSTALLER_PATH="$(readlink -f "$0")"
rm -f "$INSTALLER_PATH"
echo "✅ Installer removed"

echo ""
echo "✨ Installation complete!"
echo "   Run 'source ~/.bashrc' or restart your terminal"
echo "   Then use: $ENTRY_POINT <command>"
echo "   Or run: alltool refresh"
