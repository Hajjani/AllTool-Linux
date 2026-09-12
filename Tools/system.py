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

def _check_inxi(tool):
    if not tool.has_command("inxi"):
        tool.print_error("inxi is not installed.")
        print("   Install with: sudo apt install inxi  (Debian/Ubuntu)")
        print("               sudo pacman -S inxi  (Arch)")
        print("               sudo dnf install inxi  (Fedora)")
        return False
    return True

@command("sif", aliases=["sysinfo"], help_text="Show detailed system information")
def system_info(args: list):
    tool = ToolBase()
    if not _check_inxi(tool):
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

    # Detect distro for package hints
    distro = "unknown"
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    distro = line.strip().split("=")[1].strip('"')
                    break

    install_hints = {
        "debian": {
            "mpv": "sudo apt install mpv",
            "ffmpeg": "sudo apt install ffmpeg",
            "ffplay": "sudo apt install ffmpeg",
            "speedtest-cli": "sudo apt install speedtest-cli",
            "inxi": "sudo apt install inxi",
            "powerprofilesctl": "sudo apt install power-profiles-daemon",
            "node": "sudo apt install nodejs",
            "perl": "sudo apt install perl",
            "ruby": "sudo apt install ruby",
            "php": "sudo apt install php",
            "java": "sudo apt install default-jre",
            "g++": "sudo apt install g++",
        },
        "ubuntu": {
            "mpv": "sudo apt install mpv",
            "ffmpeg": "sudo apt install ffmpeg",
            "ffplay": "sudo apt install ffmpeg",
            "speedtest-cli": "sudo apt install speedtest-cli",
            "inxi": "sudo apt install inxi",
            "powerprofilesctl": "sudo apt install power-profiles-daemon",
            "node": "sudo apt install nodejs",
            "perl": "sudo apt install perl",
            "ruby": "sudo apt install ruby",
            "php": "sudo apt install php",
            "java": "sudo apt install default-jre",
            "g++": "sudo apt install g++",
        },
        "arch": {
            "mpv": "sudo pacman -S mpv",
            "ffmpeg": "sudo pacman -S ffmpeg",
            "ffplay": "sudo pacman -S ffmpeg",
            "speedtest-cli": "sudo pacman -S speedtest-cli",
            "inxi": "sudo pacman -S inxi",
            "powerprofilesctl": "sudo pacman -S power-profiles-daemon",
            "node": "sudo pacman -S nodejs",
            "perl": "sudo pacman -S perl",
            "ruby": "sudo pacman -S ruby",
            "php": "sudo pacman -S php",
            "java": "sudo pacman -S jre-openjdk",
            "g++": "sudo pacman -S gcc",
        },
        "fedora": {
            "mpv": "sudo dnf install mpv",
            "ffmpeg": "sudo dnf install ffmpeg",
            "ffplay": "sudo dnf install ffmpeg",
            "speedtest-cli": "sudo dnf install speedtest-cli",
            "inxi": "sudo dnf install inxi",
            "powerprofilesctl": "sudo dnf install power-profiles-daemon",
            "node": "sudo dnf install nodejs",
            "perl": "sudo dnf install perl",
            "ruby": "sudo dnf install ruby",
            "php": "sudo dnf install php",
            "java": "sudo dnf install java-latest-openjdk",
            "g++": "sudo dnf install gcc-c++",
        },
        "opensuse": {
            "mpv": "sudo zypper install mpv",
            "ffmpeg": "sudo zypper install ffmpeg",
            "ffplay": "sudo zypper install ffmpeg",
            "speedtest-cli": "sudo zypper install speedtest-cli",
            "inxi": "sudo zypper install inxi",
            "powerprofilesctl": "sudo zypper install power-profiles-daemon",
            "node": "sudo zypper install nodejs",
            "perl": "sudo zypper install perl",
            "ruby": "sudo zypper install ruby",
            "php": "sudo zypper install php",
            "java": "sudo zypper install java-latest-openjdk",
            "g++": "sudo zypper install gcc-c++",
        },
    }

    hints = install_hints.get(distro, {})

    requirements = {
        "mpv": "Sound playback (sound command)",
        "ffmpeg": "Video processing and conversion",
        "ffplay": "Video playback (video command)",
        "speedtest-cli": "Network speed test (netspeed command)",
        "requests": "Python web requests library (sr, wea commands)",
        "beautifulsoup4": "HTML parsing for web search (sr command)",
        "mkfs.ntfs": "Format NTFS disks (format command)",
        "mkfs.ext4": "Format EXT4 disks (format command)",
        "mkfs.vfat": "Format VFAT disks (format command)",
        "touch": "Create files (create command)",
        "powerprofilesctl": "Power profile management (power command)",
        "systemctl": "System control operations (power command)",
        "xdg-screensaver": "Screen locking capability (power pwlo command)",
        "inxi": "System information display (sif command)",
        "pkill": "Process management for logout (power pwl command)",
        "python3": "Python runtime (required)",
        "node": "JavaScript runtime (run .js files)",
        "perl": "Perl runtime (run .pl files)",
        "ruby": "Ruby runtime (run .rb files)",
        "php": "PHP runtime (run .php files)",
        "java": "Java runtime (run .jar files)",
        "g++": "C/C++ compiler (run .cpp/.c files)",
        "apt": "Debian/Ubuntu package manager (up command)",
        "pacman": "Arch Linux package manager (up command)",
        "dnf": "Fedora package manager (up command)",
        "zypper": "openSUSE package manager (up command)",
        "checkupdates": "Arch Linux update checker (up command)",
    }

    python_packages = ["requests", "beautifulsoup4"]
    builtin_modules = ["cmd", "subprocess", "os", "random", "string", "hashlib", "time", "json"]

    missing_count = 0
    for tool_name, desc in requirements.items():
        if tool_name in python_packages:
            try:
                __import__(tool_name.split("4")[0])
                status = "✅ Installed"
                hint = ""
            except ImportError:
                status = "❌ Missing"
                missing_count += 1
                hint = "  → pip install " + tool_name
        elif tool_name in builtin_modules:
            try:
                __import__(tool_name)
                status = "✅ Built-in"
                hint = ""
            except ImportError:
                status = "❌ Missing"
                missing_count += 1
                hint = ""
        else:
            result = subprocess.run(["which", tool_name], stdout=subprocess.DEVNULL)
            if result.returncode == 0:
                status = "✅ Installed"
                hint = ""
            else:
                status = "❌ Missing"
                missing_count += 1
                hint = "  → " + hints.get(tool_name, "Check your package manager") if tool_name in hints else ""

        print(f"{tool_name:<16} {status} — {desc}{hint}")

    if missing_count > 0:
        print(f"\n⚠️ {missing_count} requirements are missing. Install them for full functionality.")
        print("💡 Run the suggested commands above, or use the installer with --full flag.")
    else:
        print("\n✅ All requirements are installed!")
    return 0