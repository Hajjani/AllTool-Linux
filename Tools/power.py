from .base import command, ToolBase
import subprocess
import os
import json
from pathlib import Path

def _get_power_config():
    config_path = Path.home() / ".config" / "alltool" / ".confs.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                conf = json.load(f)
                return conf.get("power_management", {})
        except Exception:
            pass
    return {"backend": "powerprofilesctl", "profiles": ["power-saver", "balanced", "performance"]}

def _set_profile(backend, profile):
    if backend == "powerprofilesctl":
        subprocess.run(["powerprofilesctl", "set", profile], check=False)
    elif backend == "tlp":
        subprocess.run(["sudo", "tlp", profile], check=False)
    elif backend == "auto-cpufreq":
        subprocess.run(["auto-cpufreq", "--force", profile], check=False)
    elif backend == "cpupower":
        subprocess.run(["sudo", "cpupower", "frequency-set", "-g", profile], check=False)
    elif backend == "sysfs":
        for cpu in Path("/sys/devices/system/cpu").glob("cpu[0-9]*"):
            gov_file = cpu / "cpufreq" / "scaling_governor"
            if gov_file.exists():
                try:
                    gov_file.write_text(profile + "\n")
                except PermissionError:
                    subprocess.run(["sudo", "tee", str(gov_file)], input=profile.encode(), check=False)

def _get_current_profile(backend):
    if backend == "powerprofilesctl":
        result = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True)
        return result.stdout.strip()
    elif backend == "tlp":
        result = subprocess.run(["tlp-stat", "-p"], capture_output=True, text=True)
        return result.stdout.strip()
    elif backend == "auto-cpufreq":
        result = subprocess.run(["auto-cpufreq", "--status"], capture_output=True, text=True)
        return result.stdout.strip()
    elif backend == "cpupower":
        result = subprocess.run(["cpupower", "frequency-info", "-p"], capture_output=True, text=True)
        return result.stdout.strip()
    elif backend == "sysfs":
        gov_file = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        if gov_file.exists():
            return gov_file.read_text().strip()
    return "unknown"

@command("power", aliases=["pwr"], help_text="Manage power profiles and system control")
def power(args: list):
    if not args:
        print("Usage: alltool power [pws|pwn|pwp|pwst|pwo|pwr|pwl|pwsu|pwh|pwlo]")
        return 1

    tool = ToolBase()
    config = _get_power_config()
    backend = config.get("backend", "powerprofilesctl")
    profiles = config.get("profiles", [])

    if backend == "none":
        tool.print_error("No power management backend detected.")
        return 1

    subcommand = args[0]

    profile_map = {
        "pws": ("power-saver", "powersave", "battery"),
        "pwn": ("balanced", "ondemand", "ac"),
        "pwp": ("performance",),
    }

    if subcommand in profile_map:
        target_profiles = profile_map[subcommand]
        selected = next((p for p in target_profiles if p in profiles), target_profiles[0])
        _set_profile(backend, selected)
        tool.print_success(f"Power mode set to: {selected} (via {backend})")
        return 0

    if subcommand == "pwst":
        current = _get_current_profile(backend)
        print(f"Current power mode: {current} (via {backend})")
        return 0

    commands = {
        "pwo": (["sudo", "shutdown"], "Shutting down..."),
        "pwr": (["sudo", "reboot"], "Rebooting..."),
        "pwl": (["pkill", "-KILL", "-u", os.getlogin()], "Logging out..."),
        "pwsu": (["systemctl", "suspend"], "Suspending..."),
        "pwh": (["systemctl", "hibernate"], "Hibernating..."),
        "pwlo": (["xdg-screensaver", "lock"], "Locking screen..."),
    }

    if subcommand not in commands:
        print("Usage: alltool power [pws|pwn|pwp|pwst|pwo|pwr|pwl|pwsu|pwh|pwlo]")
        return 1

    cmd, msg = commands[subcommand]
    print(msg)
    if subcommand in ("pwo", "pwr"):
        subprocess.run(cmd)
    else:
        subprocess.run(cmd, check=False)

    tool.print_success("Done")
    return 0