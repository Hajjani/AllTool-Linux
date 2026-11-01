#!/bin/bash
set -e

REPO_URL="https://github.com/Hajjani/AllTool-Linux.git"
INSTALL_DIR="$HOME/bin"
SCRIPT_NAME="AllTool.py"
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
            echo ""
            echo "  Without flags you pick optional packages by number:"
            echo "    1. mpv    2. ffmpeg  ..."
            echo "    > 1,2,5   (or a range like 1-3, 'all', 'none')"
            exit 0
            ;;
    esac
done

case "$DISTRO" in
    debian)
        CORE_PKGS=(make git gcc pkg-config python3 python3-pip python3-requests python3-bs4 python3-packaging)
        OPTIONAL_PKGS=(
            "mpv|audio/video playback (sound command)"
            "ffmpeg|video processing (video command)"
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

# Optional packages picker. Appends the chosen package names to the
# array named by $1 (pass the array *name*, e.g. select_optional_packages selected).
# Users answer with numbers separated by commas: "1,2,5" / ranges "1-3" /
# "all" / "none". Honors -y/--yes (all) and --no-optional / non-TTY (none).
select_optional_packages() {
    local _out_name="$1"
    local entry pkg desc
    if [[ "$INSTALL_ALL_OPTIONAL" == "true" ]]; then
        echo ""
        echo "➕ Installing all ${#OPTIONAL_PKGS[@]} optional packages (-y/--yes given)."
        for entry in "${OPTIONAL_PKGS[@]}"; do
            eval "${_out_name}+=(\"\${entry%%|*}\")"
        done
        return 0
    fi
    if [[ "$SKIP_OPTIONAL" == "true" ]] || [[ ! -t 0 ]]; then
        echo ""
        echo "ℹ️  Skipping optional packages (non-interactive or --no-optional)."
        echo "   Run 'alltool requirement' to see what each command needs."
        return 0
    fi
    echo ""
    echo "🧩 Optional packages — pick what to install:"
    local idx=1
    for entry in "${OPTIONAL_PKGS[@]}"; do
        pkg="${entry%%|*}"
        desc="${entry#*|}"
        printf "  %2d. %-22s (%s)\n" "$idx" "$pkg" "$desc"
        idx=$((idx + 1))
    done
    local total=${#OPTIONAL_PKGS[@]}
    echo ""
    echo "   Enter numbers separated by commas (e.g. 1,2,5), a range (e.g. 1-3), 'all', or 'none'."
    local choice token tokens picked valid n lo hi already p
    while true; do
        read -r -p "> " choice || choice=""
        choice="$(printf '%s' "$choice" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
        [ -z "$choice" ] && choice="none"
        if [[ "$choice" == "all" || "$choice" == "a" ]]; then
            for entry in "${OPTIONAL_PKGS[@]}"; do
                eval "${_out_name}+=(\"\${entry%%|*}\")"
            done
            eval "echo \"➕ Selected all \${#${_out_name}[@]} packages.\""
            break
        fi
        if [[ "$choice" == "none" || "$choice" == "no" || "$choice" == "n" ]]; then
            break
        fi
        picked=()
        valid=true
        IFS=',' read -ra tokens <<< "$choice"
        for token in "${tokens[@]}"; do
            if [[ "$token" =~ ^[0-9]+$ ]]; then
                lo=$token; hi=$token
            elif [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
                lo=${BASH_REMATCH[1]}; hi=${BASH_REMATCH[2]}
                # allow reversed ranges like 5-2
                if [ "$lo" -gt "$hi" ]; then
                    n=$lo; lo=$hi; hi=$n
                fi
            else
                valid=false
                break
            fi
            # strip leading zeros (avoid octal interpretation)
            lo=$((10#$lo)); hi=$((10#$hi))
            if [ "$lo" -lt 1 ] || [ "$hi" -gt "$total" ]; then
                valid=false
                break
            fi
            n=$lo
            while [ "$n" -le "$hi" ]; do
                already=false
                for p in "${picked[@]}"; do
                    if [ "$p" -eq "$n" ]; then already=true; break; fi
                done
                if [[ "$already" == "false" ]]; then
                    picked+=("$n")
                fi
                n=$((n + 1))
            done
        done
        if [[ "$valid" == "true" ]] && [ ${#picked[@]} -gt 0 ]; then
            for n in "${picked[@]}"; do
                entry="${OPTIONAL_PKGS[$((n - 1))]}"
                eval "${_out_name}+=(\"\${entry%%|*}\")"
            done
            eval "echo \"➕ Selected: \${${_out_name}[*]}\""
            break
        fi
        echo "❌ Invalid choice '$choice'. Use numbers 1-$total separated by commas (e.g. 1,2,5), 'all', or 'none'."
    done
}

# Install system packages: core automatically, optional by user choice.
# Install the given packages with the detected distro's package manager.
install_with_pkgmgr() {
    [ $# -eq 0 ] && return 0
    case "$DISTRO" in
        debian)
            sudo apt install -y "$@"
            ;;
        arch)
            sudo pacman -S --noconfirm "$@"
            ;;
        fedora)
            sudo dnf install -y "$@"
            ;;
        opensuse)
            sudo zypper install -y "$@"
            ;;
    esac
}

# Map an external command to the package that provides it for this distro.
pkg_for_command() {
    case "$1" in
        mpv)              echo "mpv" ;;
        ffmpeg)           echo "ffmpeg" ;;
        speedtest-cli)    echo "speedtest-cli" ;;
        inxi)             echo "inxi" ;;
        powerprofilesctl) echo "power-profiles-daemon" ;;
        node)             echo "nodejs" ;;
        ruby)             echo "ruby" ;;
        php)              echo "php" ;;
        java)
            case "$DISTRO" in
                debian)           echo "default-jre" ;;
                arch)             echo "jre-openjdk" ;;
                fedora|opensuse)  echo "java-latest-openjdk" ;;
                *)                echo "java" ;;
            esac
            ;;
        g++)
            case "$DISTRO" in
                debian)           echo "g++" ;;
                arch)             echo "gcc" ;;
                fedora|opensuse)  echo "gcc-c++" ;;
                *)                echo "g++" ;;
            esac
            ;;
        *) echo "$1" ;;
    esac
}

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
        debian) sudo apt update ;;
    esac
    install_with_pkgmgr "${CORE_PKGS[@]}"

    # 2. Optional — numbered multi-select ("1,2,5" / "all" / "none")
    select_optional_packages selected

    # 3. Install what was selected
    if [ ${#selected[@]} -eq 0 ]; then
        echo "ℹ️  No optional packages selected — skipping."
        echo "   You can install them later manually; run 'alltool requirement' to see what each command needs."
        return 0
    fi
    echo ""
    echo "📥 Installing selected optional packages: ${selected[*]}"
    install_with_pkgmgr "${selected[@]}"
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
for cmd in mpv ffmpeg speedtest-cli inxi powerprofilesctl node ruby php java g++; do
    if ! command -v "$cmd" &> /dev/null; then
        MISSING_CMDS+=("$cmd")
    fi
done

if [ ${#MISSING_CMDS[@]} -gt 0 ]; then
    echo "⚠️  The following optional commands are not installed:"
    printf '  %s\n' "${MISSING_CMDS[@]}"
    echo "Some AllTool features will not work without them."
    echo "Run 'alltool requirement' to see what each command needs."

    # Offer to install them on the spot, reusing the numbered picker above.
    # -y installs everything, --no-optional / non-TTY skips (same policy as
    # the optional-package stage).
    if [[ "$INSTALL_ALL_OPTIONAL" != "true" ]] && { [[ "$SKIP_OPTIONAL" == "true" ]] || [[ ! -t 0 ]]; }; then
        echo "ℹ️  Skipping on-the-spot install of missing commands (non-interactive or --no-optional)."
    else
        echo ""
        echo "🧩 Missing commands — install now? (pick by number, 'all', or 'none')"
        local_saved_optional=("${OPTIONAL_PKGS[@]}")
        entries=()
        for cmd in "${MISSING_CMDS[@]}"; do
            _pkg="$(pkg_for_command "$cmd")"
            entries+=("$_pkg|required by command: $cmd")
        done
        OPTIONAL_PKGS=("${entries[@]}")
        missing_selected=()
        select_optional_packages missing_selected
        OPTIONAL_PKGS=("${local_saved_optional[@]}")

        if [ ${#missing_selected[@]} -gt 0 ]; then
            echo ""
            echo "📥 Installing missing commands now: ${missing_selected[*]}"
            install_with_pkgmgr "${missing_selected[@]}"
        else
            echo "ℹ️  None chosen — missing commands were not installed."
            echo "   Run 'alltool requirement' to see what each command needs."
        fi
    fi
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
    # Serialize profiles as JSON via python to avoid bash @Q quoting (not valid JSON).
    PROFILES_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${POWER_PROFILES[@]}")
    POWER_MGMT_ESCAPED=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$POWER_MGMT")
    python3 << EOF
import json
conf_file = "$CONF_FILE"
with open(conf_file, 'r') as f:
    conf = json.load(f)

conf["power_management"] = {
    "backend": $POWER_MGMT_ESCAPED,
    "profiles": $PROFILES_JSON,
}

with open(conf_file, 'w') as f:
    json.dump(conf, f, indent=2)

print("Updated .confs.json with power management config")
EOF
fi

# Stamp owner identity into .confs.json (username + acting folders).
# `.confs.json` is the source the tool reads the user name from.
CONF_FILE="$REPO_PATH/.confs.json"
if [ -f "$CONF_FILE" ]; then
    INSTALL_USER="$(whoami 2>/dev/null || id -un 2>/dev/null || echo "")"
    INSTALL_HOME="$HOME"
    python3 << EOF || true
import json
conf_file = "$CONF_FILE"
try:
    with open(conf_file, 'r') as f:
        conf = json.load(f)
    user = """$INSTALL_USER""".strip()
    home = """$INSTALL_HOME""".strip() or __import__("os").path.expanduser("~")
    if user:
        conf["username"] = user
    if home:
        conf["home_dir"] = f"{home}/.config/alltool"
        conf["bin_dir"] = f"{home}/.config/alltool/bin"
        conf["cache_dir"] = f"{home}/.config/alltool/cache"
        conf["logs_dir"] = f"{home}/.config/alltool/logs"
    # A fresh install must not inherit the template's cached sudo creds.
    # Cached sudo credentials live only in `.confs.json` (single source of
    # truth); write the full v2-shaped record, empty and uncached.
    if isinstance(conf.get("sudo"), dict) or conf.get("sudo") is None:
        conf["sudo"] = {
            "cached": False, "scheme": "", "username": "", "iterations": 0,
            "salt": "", "nonce": "", "record_key": "",
            "encrypted_password": "", "auth_tag": "",
        }
    with open(conf_file, 'w') as f:
        json.dump(conf, f, indent=2)
    print(f"Stamped .confs.json identity: username='{conf.get('username')}' home='{home}'")
except Exception as e:
    print(f"Warning: could not stamp identity: {e}")
EOF
fi

# User-space install (no root needed: libs go to ~/.config/alltool/bin,
# which is where the app loads them from — NOT /usr/local like `make install`)
echo "🔨 Running make install-user..."
make install-user

# Cached sudo credentials live in ~/.config/alltool/.confs.json (single
# source of truth). This install must: keep a record that already belongs
# to this user (reinstall/upgrade), clear one owned by someone else
# (username-change resilience), and keep the v2 schema complete so the C
# side can parse it without falling back.
USER_CONFIG="$HOME/.config/alltool/.confs.json"
if [ -f "$USER_CONFIG" ]; then
    INSTALL_USER="$(whoami 2>/dev/null || id -un 2>/dev/null || echo "")"
    python3 << EOF || true
import json
user_config = "$USER_CONFIG"
me = """$INSTALL_USER""".strip()
try:
    with open(user_config) as f:
        conf = json.load(f)
except Exception as e:
    raise SystemExit(f"Warning: could not read user config: {e}")
sudo = conf.get("sudo")
if not isinstance(sudo, dict):
    sudo = conf["sudo"] = {}

# complete v2 schema
for key in ("cached", "scheme", "username", "iterations", "salt",
            "nonce", "record_key", "encrypted_password", "auth_tag"):
    sudo.setdefault(key, False if key == "cached" else (0 if key == "iterations" else ""))

if sudo == {"cached": False} or all(not str(sudo[k]) for k in ("salt", "record_key")):
    pass  # nothing cached — fresh record, nothing to do
elif me and str(sudo.get("username", "")) not in ("", me):
    sudo["cached"] = False
    print(f"Cleared cached sudo credentials owned by '{sudo.get('username')}' (this install runs as '{me}').")

with open(user_config, "w") as f:
    json.dump(conf, f, indent=2)
print("Sudo record in .confs.json OK (cached=%s)." % json.dumps(sudo.get("cached")))
EOF
fi

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
