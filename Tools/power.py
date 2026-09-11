from .base import command, ToolBase
import subprocess
import os

@command("power", aliases=["pwr"], help_text="Manage power profiles and system control")
def power(args: list):
    if not args:
        print("Usage: alltool power [pws|pwn|pwp|pwst|pwo|pwr|pwl|pwsu|pwh|pwlo]")
        return 1

    tool = ToolBase()
    if not tool.has_command("powerprofilesctl"):
        tool.print_error("powerprofilesctl not found. Install power-profiles-daemon.")
        return 1

    subcommand = args[0]
    commands = {
        "pws": (["powerprofilesctl", "set", "power-saver"], "Power mode set to: power-saver"),
        "pwn": (["powerprofilesctl", "set", "balanced"], "Power mode set to: balanced"),
        "pwp": (None, "Performance mode"),
        "pwst": (["powerprofilesctl", "get"], None),
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

    if subcommand == "pwp":
        result = subprocess.run(["powerprofilesctl", "list"], capture_output=True, text=True)
        if "performance" in result.stdout:
            subprocess.run(["powerprofilesctl", "set", "performance"])
            tool.print_success("Power mode set to: performance")
        else:
            tool.print_warning("Performance mode not supported on this system.")
        return 0

    cmd, msg = commands[subcommand]
    if msg and subcommand != "pwst":
        print(msg)

    if subcommand == "pwst":
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"🔍 Current power mode: {result.stdout.strip()}")
    else:
        if subcommand in ("pwo", "pwr"):
            subprocess.run(cmd)
        else:
            subprocess.run(cmd, check=False)

    if subcommand not in ("pwst", "pwo", "pwr", "pwl"):
        tool.print_success(msg or "Done")
    return 0