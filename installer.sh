#!/bin/bash
# AllTool-Linux Installer

set -e

REPO_URL="https://github.com/Hajjani/AllTool-Linux.git"
INSTALL_DIR="$HOME/bin"
SCRIPT_NAME="AllTools.py"
ENTRY_POINT="alltool"

echo "🚀 AllTool-Linux Installer"
echo "========================================"

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

# --- Optional package selection ------------------------------------------
# Core packages are always installed (required). Every optional package is
# offered individually — nothing optional is installed without consent,
# unless -y/--yes is passed.
#
# Usage: ./installer.sh [-y|--yes] [--no-optional|--minimal] [-h|--help]
INSTALL_ALL_OPTIONAL=false
SKIP_OPTIONAL=false
for arg in "$@"; do
    case "$arg" in
        -y|--yes) INSTALL_ALL_OPTIONAL=true ;;
        --no-optional|--minimal) SKIP_OPTIONAL=true ;;
        -h|--help)
            echo "Usage: $0 [-y|--yes] [--no-optional|--minimal]"
            echo ""
            echo "  -y, --yes          install all optional packages without asking"
            echo "  --no-optional      skip all optional packages without asking"
            echo "  --minimal          alias of --no-optional"
            exit 0
            ;;
    esac
done

# ask_yes_no <prompt> [default=y|n] -> exit 0 = yes, 1 = no.
# Auto-answers yes with -y/--yes, no with --no-optional or when stdin is
# not interactive (piped/CI) so the installer never hangs on input.
ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"
    local hint reply

    if [[ "$INSTALL_ALL_OPTIONAL" == "true" ]]; then
        return 0
    fi
    if [[ "$SKIP_OPTIONAL" == "true" ]] || [[ ! -t 0 ]]; then
        return 1
    fi

    if [[ "$default" == "y" ]]; then
        hint="[Y/n]"
    else
        hint="[y/N]"
    fi

    read -r -p "$prompt $hint: " reply || reply=""
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy]$ ]]
}

# Per-distro package lists. Optional entries are "package|description".
case "$DISTRO" in
    debian)
        CORE_PKGS=(make git gcc pkg-config python3 python3-pip python3-requests python3-bs4 python3-packaging)
        OPTIONAL_PKGS=(
            "mpv|audio/video playback (sound command)"
            "ffmpeg|video processing (video command)"
            "yt-dlp|download videos/audio (downloadvs command)"
            "speedtest-cli|network speed test (netspeed command)"
            "inxi|detailed system info (sif command)"
            "power-profiles-daemon|power profiles (power command)"
            "nodejs|JavaScript runtime (run .js files)"
            "ruby|Ruby runtime (run .rb files)"
            "php|PHP runtime (run .php files)"
            "default-jre|Java runtime (run .jar files)"
            "g++|C++ compiler (run .cpp files)"
        )
        ;;
    arch)
        CORE_PKGS=(make git gcc pkg-config python python-pip python-requests python-beautifulsoup4 python-packaging)
        OPTIONAL_PKGS=(
            "mpv|audio/video playback (sound command)"
            "ffmpeg|video processing (video command)"
            "yt-dlp|download videos/audio (downloadvs command)"
            "speedtest-cli|network speed test (netspeed command)"
            "inxi|detailed system info (sif command)"
            "power-profiles-daemon|power profiles (power command)"
            "nodejs|JavaScript runtime (run .js files)"
            "ruby|Ruby runtime (run .rb files)"
            "php|PHP runtime (run .php files)"
            "jre-openjdk|Java runtime (run .jar files)"
            "gcc|C++ compiler g++ (run .cpp files, already covered by core gcc)"
        )
        ;;
    fedora)
        CORE_PKGS=(make git gcc pkg-config python3 python3-pip python3-requests python3-beautifulsoup4 python3-packaging)
        OPTIONAL_PKGS=(
            "mpv|audio/video playback (sound command)"
            "ffmpeg|video processing (video command)"
            "yt-dlp|download videos/audio (downloadvs command)"
            "speedtest-cli|network speed test (netspeed command)"
            "inxi|detailed system info (sif command)"
            "power-profiles-daemon|power profiles (power command)"
            "nodejs|JavaScript runtime (run .js files)"
            "ruby|Ruby runtime (run .rb files)"
            "php|PHP runtime (run .php files)"
            "java-latest-openjdk|Java runtime (run .jar files)"
            "gcc-c++|C++ compiler (run .cpp files)"
        )
        ;;
    opensuse)
        CORE_PKGS=(make git gcc pkg-config python3 python3-pip python3-requests python3-beautifulsoup4 python3-packaging)
        OPTIONAL_PKGS=(
            "mpv|audio/video playback (sound command)"
            "ffmpeg|video processing (video command)"
            "yt-dlp|download videos/audio (downloadvs command)"
            "speedtest-cli|network speed test (netspeed command)"
            "inxi|detailed system info (sif command)"
            "power-profiles-daemon|power profiles (power command)"
            "nodejs|JavaScript runtime (run .js files)"
            "ruby|Ruby runtime (run .rb files)"
            "php|PHP runtime (run .php files)"
            "java-latest-openjdk|Java runtime (run .jar files)"
            "gcc-c++|C++ compiler (run .cpp files)"
        )
        ;;
    *)
        CORE_PKGS=()
        OPTIONAL_PKGS=()
        ;;
esac

# Install system packages: core automatically, optional by user choice.
install_packages() {
    local entry pkg desc
    local selected=()

    if [ ${#CORE_PKGS[@]} -eq 0 ]; then
        echo "⚠️  Unknown distro, skipping system package installation"
        return 0
    fi

    # 1. Core (required) — always installed
    echo ""
    echo "📥 Installing required packages: ${CORE_PKGS[*]}"
    case "$DISTRO" in
        debian)
            sudo apt update
            sudo apt install -y "${CORE_PKGS[@]}"
            ;;
        arch)
            sudo pacman -S --noconfirm "${CORE_PKGS[@]}"
            ;;
        fedora)
            sudo dnf install -y "${CORE_PKGS[@]}"
            ;;
        opensuse)
            sudo zypper install -y "${CORE_PKGS[@]}"
            ;;
    esac

    # 2. Optional — ask for each one
    echo ""
    echo "🧩 Optional packages — answer Y/n for each one you want."
    echo "   (pass -y/--yes to take all, --no-optional to skip all)"
    for entry in "${OPTIONAL_PKGS[@]}"; do
        pkg="${entry%%|*}"
        desc="${entry#*|}"
        if ask_yes_no "  Install $pkg? ($desc)" "y"; then
            selected+=("$pkg")
            echo "    ➕ $pkg selected"
        fi
    done

    # 3. Install what was selected
    if [ ${#selected[@]} -eq 0 ]; then
        echo "ℹ️  No optional packages selected — skipping."
        echo "   You can install them later manually; run 'alltool requirement' to see what each command needs."
        return 0
    fi
    echo ""
    echo "📥 Installing selected optional packages: ${selected[*]}"
    case "$DISTRO" in
        debian)
            sudo apt install -y "${selected[@]}"
            ;;
        arch)
            sudo pacman -S --noconfirm "${selected[@]}"
            ;;
        fedora)
            sudo dnf install -y "${selected[@]}"
            ;;
        opensuse)
            sudo zypper install -y "${selected[@]}"
            ;;
    esac
}

install_packages


# Create temp directory
TMPDIR=$(mktemp -d)
REPO_PATH="$TMPDIR/AllTool-Linux"
echo "📂 Cloning repo to $REPO_PATH..."
git clone "$REPO_URL" "$REPO_PATH"
cd "$REPO_PATH"

# Check external commands (warn only — these are all optional now)
echo "🔍 Checking external commands..."
MISSING_CMDS=()
for cmd in mpv ffmpeg yt-dlp speedtest-cli inxi powerprofilesctl node ruby php java g++; do
    if ! command -v "$cmd" &> /dev/null; then
        MISSING_CMDS+=("$cmd")
    fi
done

if [ ${#MISSING_CMDS[@]} -gt 0 ]; then
    echo "⚠️  The following optional commands are not installed:"
    printf '  %s\n' "${MISSING_CMDS[@]}"
    echo "Some AllTool features will not work without them."
    echo "Run 'alltool requirement' to see what each command needs."
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
