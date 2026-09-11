from .base import command, ToolBase
import os
import subprocess
import json

@command("refresh", help_text="Refresh script setup, update permissions, and add ~/bin to PATH")
def refresh(args: list):
    tool = ToolBase()
    tool.print_status("Refreshing alltool setup...")

    config = tool.config
    bin_dir = config.get("bin_dir", str(tool.home_dir / "bin"))

    subprocess.run(["chmod", "+x", bin_dir + "/alltool_runner"])

    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        config_file = os.path.expanduser("~/.zshrc")
    elif "bash" in shell:
        config_file = os.path.expanduser("~/.bashrc")
    else:
        config_file = os.path.expanduser("~/.profile")

    path_line = f'export PATH="{bin_dir}:$PATH"'
    already_set = False
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            if path_line in f.read():
                already_set = True

    if not already_set:
        with open(config_file, "a") as f:
            f.write(f"\n# Added by alltool\n{path_line}\n")
        tool.print_success(f"PATH updated in {config_file}")
    else:
        tool.print_status(f"PATH already set in {config_file}")

    print(f"Please run: source {config_file} or restart your terminal to apply changes.")
    tool.print_success("Refresh complete.")
    return 0

@command("sf", aliases=["ls"], help_text="Show files in current directory")
def show_files(args: list):
    subprocess.run(["ls", "-la"])
    return 0

@command("sif", aliases=["sysinfo"], help_text="Show detailed system information")
def system_info(args: list):
    if not ToolBase().has_command("inxi"):
        print("❌ inxi not installed. Install it for system info.")
        return 1
    subprocess.run(["inxi", "-F"])
    return 0

@command("up", aliases=["update-check"], help_text="Check for system updates")
def check_updates(args: list):
    tool = ToolBase()
    if tool.has_command("apt"):
        tool.print_status("Checking for updates (APT)...")
        subprocess.run(["sudo", "apt", "update"], stdout=subprocess.DEVNULL)
        output = tool.get_output(["apt", "list", "--upgradable"])
        lines = [line for line in output.splitlines() if "/" in line]
        if lines:
            tool.print_warning(f"{len(lines)} updates not installed.")
        else:
            tool.print_success("No updates available.")

    elif tool.has_command("checkupdates"):
        tool.print_status("Checking for updates (Pacman)...")
        output = tool.get_output(["checkupdates"])
        lines = [line for line in output.splitlines() if line.strip()]
        if lines:
            tool.print_warning(f"{len(lines)} updates not installed.")
        else:
            tool.print_success("No updates available.")

    elif tool.has_command("dnf"):
        tool.print_status("Checking for updates (DNF)...")
        output = tool.get_output(["dnf", "check-update"])
        lines = [line for line in output.splitlines() if line and not line.startswith("Last metadata")]
        if lines:
            tool.print_warning(f"{len(lines)} updates not installed.")
        else:
            tool.print_success("No updates available.")

    elif tool.has_command("zypper"):
        tool.print_status("Checking for updates (Zypper)...")
        output = tool.get_output(["zypper", "list-updates"])
        lines = [line for line in output.splitlines() if line.startswith("v ") or line.startswith("i ")]
        if lines:
            tool.print_warning(f"{len(lines)} updates not installed.")
        else:
            tool.print_success("No updates available.")

    else:
        tool.print_error("No supported package manager found.")
    return 0

@command("cl", aliases=["clear"], help_text="Clear terminal")
def clear_terminal(args: list):
    subprocess.run(["clear"])
    return 0

@command("requirement", aliases=["req"], help_text="Check if alltool dependencies are installed")
def check_requirements(args: list):
    tool = ToolBase()
    tool.print_status("Checking system requirements for alltool...")

    requirements = {
        "mpv": "Sound playback (multi-format)",
        "ffmpeg": "Video processing and conversion",
        "ffplay": "Video playback",
        "speedtest-cli": "Network speed test",
        "yt-dlp": "Download videos and audio from websites",
        "requests": "Python web requests library",
        "beautifulsoup4": "HTML parsing for web search",
        "mkfs.ntfs": "Format NTFS disks",
        "mkfs.ext4": "Format EXT4 disks",
        "mkfs.vfat": "Format VFAT disks",
        "touch": "Create files",
        "powerprofilesctl": "Power profile management",
        "systemctl": "System control operations",
        "xdg-screensaver": "Screen locking capability",
        "inxi": "System information display",
        "pkill": "Process management for logout functionality",
        "python3": "Python runtime (required)",
        "node": "JavaScript runtime",
        "perl": "Perl runtime",
        "ruby": "Ruby runtime",
        "php": "PHP runtime",
        "java": "Java runtime",
        "g++": "C/C++ compiler",
        "apt": "Debian/Ubuntu package manager",
        "pacman": "Arch Linux package manager",
        "dnf": "Fedora package manager",
        "zypper": "openSUSE package manager",
        "checkupdates": "Arch Linux update checker",
    }

    python_packages = ["requests", "beautifulsoup4"]
    builtin_modules = ["cmd", "subprocess", "os", "random", "string", "hashlib", "time", "json"]

    missing_count = 0
    for tool_name, desc in requirements.items():
        if tool_name in python_packages:
            try:
                __import__(tool_name.split("4")[0])
                status = "✅ Installed"
            except ImportError:
                status = "❌ Missing"
                missing_count += 1
        elif tool_name in builtin_modules:
            try:
                __import__(tool_name)
                status = "✅ Built-in"
            except ImportError:
                status = "❌ Missing"
                missing_count += 1
        else:
            result = subprocess.run(["which", tool_name], stdout=subprocess.DEVNULL)
            status = "✅ Installed" if result.returncode == 0 else "❌ Missing"
            if result.returncode != 0:
                missing_count += 1

        print(f"{tool_name:<16} {status} — {desc}")

    if missing_count > 0:
        print(f"\n⚠️ {missing_count} requirements are missing. Install them for full functionality.")
        print("💡 Installation commands:")
        print("   For Python packages: pip install requests beautifulsoup4")
        print("   For Arch Linux: sudo pacman -S mpv ffmpeg speedtest-cli yt-dlp inxi")
        print("   For Ubuntu/Debian: sudo apt install mpv ffmpeg speedtest-cli yt-dlp inxi")
        print("   For Fedora: sudo dnf install mpv ffmpeg speedtest-cli yt-dlp inxi")
        print("   For openSUSE: sudo zypper install mpv ffmpeg speedtest-cli yt-dlp inxi")
        print("   For power management: sudo apt install power-profiles-daemon (Ubuntu) or sudo pacman -S power-profiles-daemon (Arch)")
    else:
        print("\n✅ All requirements are installed!")
    return 0