import subprocess
import os
import sys
from typing import List, Optional, Callable
from pathlib import Path
from .bindings import load_config, AllToolSudo, HOME_DIR

class ToolBase:
    def __init__(self):
        self.config = load_config()
        self.sudo = AllToolSudo()
        self.home_dir = HOME_DIR

    def run_cmd(self, cmd: List[str], capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=capture, text=True, check=check)

    def get_output(self, cmd: List[str]) -> str:
        try:
            result = self.run_cmd(cmd, capture=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    def has_command(self, cmd: str) -> bool:
        return self.run_cmd(["which", cmd], capture=True).returncode == 0

    def confirm(self, message: str, default: bool = False) -> bool:
        suffix = " [Y/n]: " if default else " [y/N]: "
        while True:
            response = input(message + suffix).strip().lower()
            if not response:
                return default
            if response in ("y", "yes"):
                return True
            if response in ("n", "no"):
                return False
            print("❌ Please enter 'yes' or 'no'.")

    def sudo_run(self, cmd: List[str], cache: bool = False) -> subprocess.CompletedProcess:
        if cache:
            creds = self.sudo.load_credentials(str(self.home_dir / ".confs.json"))
            if creds and creds["cached"]:
                return self._run_with_cached_sudo(cmd, creds)

        full_cmd = ["sudo"] + cmd
        return self.run_cmd(full_cmd)

    def _run_with_cached_sudo(self, cmd: List[str], creds: dict) -> subprocess.CompletedProcess:
        import shlex
        sudo_cmd = " ".join(shlex.quote(str(c)) for c in cmd)
        ret, stdout = self.sudo.run_with_creds(
            creds["username"],
            creds["encrypted_password"],
            sudo_cmd
        )
        result = subprocess.CompletedProcess(cmd, ret)
        result.stdout = stdout
        return result

    def print_status(self, msg: str, icon: str = "ℹ️"):
        print(f"{icon} {msg}")

    def print_success(self, msg: str):
        self.print_status(msg, "✅")

    def print_error(self, msg: str):
        self.print_status(msg, "❌")

    def print_warning(self, msg: str):
        self.print_status(msg, "⚠️")

    def expand_path(self, path: str) -> str:
        return os.path.expanduser(path)


class CommandRegistry:
    def __init__(self):
        self.commands = {}
        self.aliases = {}

    def register(self, name: str, handler: Callable, aliases: List[str] = None, help_text: str = ""):
        self.commands[name] = {"handler": handler, "help": help_text}
        if aliases:
            for alias in aliases:
                self.aliases[alias] = name

    def get(self, name: str) -> Optional[Callable]:
        real_name = self.aliases.get(name, name)
        return self.commands.get(real_name, {}).get("handler")

    def get_help(self, name: str) -> str:
        real_name = self.aliases.get(name, name)
        return self.commands.get(real_name, {}).get("help", "")

    def list_commands(self) -> List[str]:
        return list(self.commands.keys())


registry = CommandRegistry()


def command(name: str, aliases: List[str] = None, help_text: str = ""):
    def decorator(func: Callable):
        registry.register(name, func, aliases, help_text)
        return func
    return decorator