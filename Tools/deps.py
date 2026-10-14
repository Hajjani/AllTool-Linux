"""Missing-dependency helper: hint + ask to install.

When a command needs an external program that is not installed, call
`ensure_command(tool, cmd, ...)` instead of only printing a hint. On a TTY
it asks whether to install right away via the distro package manager
(sudo); non-interactive shells only get the manual hint. Never raises.
"""

import os
import shutil
import subprocess
from typing import Dict, List, Optional

# Binary -> {distro-family: package} (package may differ from the binary).
PACKAGES: Dict[str, Dict[str, str]] = {
    "mpv": {"debian": "mpv", "arch": "mpv", "fedora": "mpv", "opensuse": "mpv"},
    "ffmpeg": {"debian": "ffmpeg", "arch": "ffmpeg", "fedora": "ffmpeg", "opensuse": "ffmpeg"},
    "ffplay": {"debian": "ffmpeg", "arch": "ffmpeg", "fedora": "ffmpeg", "opensuse": "ffmpeg"},
    "speedtest-cli": {"debian": "speedtest-cli", "arch": "speedtest-cli", "fedora": "speedtest-cli", "opensuse": "speedtest-cli"},
    "inxi": {"debian": "inxi", "arch": "inxi", "fedora": "inxi", "opensuse": "inxi"},
    "node": {"debian": "nodejs", "arch": "nodejs", "fedora": "nodejs", "opensuse": "nodejs"},
    "ruby": {"debian": "ruby", "arch": "ruby", "fedora": "ruby", "opensuse": "ruby"},
    "php": {"debian": "php", "arch": "php", "fedora": "php", "opensuse": "php"},
    "java": {"debian": "default-jre", "arch": "jre-openjdk", "fedora": "java-latest-openjdk", "opensuse": "java-latest-openjdk"},
    "g++": {"debian": "g++", "arch": "gcc", "fedora": "gcc-c++", "opensuse": "gcc-c++"},
    "perl": {"debian": "perl", "arch": "perl", "fedora": "perl", "opensuse": "perl"},
    "powerprofilesctl": {"debian": "power-profiles-daemon", "arch": "power-profiles-daemon", "fedora": "power-profiles-daemon", "opensuse": "power-profiles-daemon"},
    "tlp": {"debian": "tlp", "arch": "tlp", "fedora": "tlp", "opensuse": "tlp"},
    "cpupower": {"arch": "cpupower", "fedora": "cpupower", "opensuse": "cpupower"},
}

# Full custom install argv per binary (used when one package is not enough
# or the installer is not the system package manager).
CUSTOM_INSTALL: Dict[str, Dict[str, List[str]]] = {
    "cpupower": {
        "debian": ["sudo", "apt", "install", "-y", "linux-tools-common", "linux-tools-generic"],
    },
    "auto-cpufreq": {
        "debian": ["sudo", "apt", "install", "-y", "auto-cpufreq"],
        "arch": ["sudo", "pacman", "-S", "--noconfirm", "auto-cpufreq"],
        "fedora": ["pip", "install", "auto-cpufreq"],
        "opensuse": ["pip", "install", "auto-cpufreq"],
    },
}

# Distro-family -> install command prefix (sudo + manager + args).
INSTALL_PREFIX: Dict[str, List[str]] = {
    "debian": ["sudo", "apt", "install", "-y"],
    "arch": ["sudo", "pacman", "-S", "--noconfirm"],
    "fedora": ["sudo", "dnf", "install", "-y"],
    "opensuse": ["sudo", "zypper", "install", "-y"],
}


def get_distro() -> str:
    """Distro family: debian | arch | fedora | opensuse | unknown."""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    ident = line.strip().split("=", 1)[1].strip('"').lower()
                    if ident in ("debian", "ubuntu", "linuxmint", "pop"):
                        return "debian"
                    if ident in ("arch", "manjaro", "endeavouros"):
                        return "arch"
                    if ident in ("fedora", "rhel", "centos", "rocky", "almalinux"):
                        return "fedora"
                    if "opensuse" in ident or ident in ("sles", "sled"):
                        return "opensuse"
                    return "unknown"
    except OSError:
        pass
    return "unknown"


def is_available(cmd: str) -> bool:
    try:
        if shutil.which(cmd) is not None:
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(["which", cmd], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def install_cmd_for(cmd: str, distro: Optional[str] = None) -> Optional[List[str]]:
    """Full install argv for `cmd`, or None when unknown/distro unsupported."""
    distro = distro or get_distro()
    custom = CUSTOM_INSTALL.get(cmd, {}).get(distro)
    if custom:
        return list(custom)
    pkg = PACKAGES.get(cmd, {}).get(distro)
    prefix = INSTALL_PREFIX.get(distro)
    if not pkg or not prefix:
        return None
    return prefix + [pkg]


def hint_for(cmd: str, distro: Optional[str] = None) -> str:
    argv = install_cmd_for(cmd, distro)
    if argv:
        return " ".join(argv)
    return f"Install '{cmd}' using your package manager."


def ensure_command(tool, cmd: str, description: str = "", *, auto_install: bool = False) -> bool:
    """Make sure `cmd` exists; ask to install it when missing.

    Prints the manual install hint, then — on an interactive terminal —
    offers to run it via sudo now. Returns True when the command is
    available afterwards. Never raises.
    """
    try:
        if is_available(cmd) or (hasattr(tool, "has_command") and tool.has_command(cmd)):
            return True
    except Exception:
        pass
    what = f" (required for {description})" if description else ""
    try:
        tool.print_error(f"{cmd} is not installed{what}.")
    except Exception:
        print(f"❌ {cmd} is not installed{what}.")
    print(f"   Install with: {hint_for(cmd)}")

    argv = install_cmd_for(cmd)
    if argv is None:
        return False

    try:
        import sys

        interactive = sys.stdin.isatty()
    except Exception:
        interactive = False
    if not (auto_install or interactive):
        return False

    question = f"Install '{cmd}' now? ({' '.join(argv)})"
    try:
        if hasattr(tool, "confirm"):
            ok = tool.confirm(question, default=False) if not auto_install else True
        else:
            if auto_install:
                ok = True
            else:
                reply = input(question + " [y/N]: ").strip().lower()
                ok = reply in ("y", "yes")
    except (EOFError, OSError, KeyboardInterrupt):
        return False
    if not ok:
        return False

    print(f"📥 Installing '{cmd}'...")
    try:
        r = subprocess.run(argv, timeout=600)
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out.")
        return False
    except OSError as e:
        print(f"❌ Could not run installer: {e}")
        return False
    if r.returncode != 0:
        print(f"❌ Installation failed (exit {r.returncode}).")
        return False
    if is_available(cmd):
        print(f"✅ '{cmd}' installed.")
        return True
    print(f"⚠️  Installer finished but '{cmd}' is still not found.")
    return False
