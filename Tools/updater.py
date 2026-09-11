from .base import command, ToolBase
import re
import requests
from packaging import version
from .bindings import HOME_DIR, load_config, save_config

@command("upa", aliases=["update"], help_text="Update AllTool to stable (st) or preview (pv) version")
def updater(args: list):
    tool = ToolBase()
    config = load_config()
    LOCAL_PATH = str(HOME_DIR / "bin" / "alltool_runner")

    avup = ["st", "pv"]
    if not args:
        print("Usage: alltool upa [st|pv]")
        print("  st: Update to latest stable version")
        print("  pv: Update to latest preview version")
        return 1

    subc = args[0]
    if subc not in avup:
        tool.print_error(f"Command {subc} not found.")
        print("Available: st (stable), pv (preview)")
        return 1

    if subc == "st":
        github_url = "https://raw.githubusercontent.com/Iinitialb/AllTool-Linux/refs/heads/Stable/AllToolInstaller.py"
    else:
        github_url = "https://raw.githubusercontent.com/Iinitialb/AllTool-Linux/refs/heads/Preview/AllTools.py"

    def get_remote_version_and_code(url):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                code = response.text
                match = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', code)
                return match.group(1) if match else None, code
        except Exception as e:
            tool.print_error(f"Failed to fetch remote version: {e}")
        return None, None

    def get_local_version():
        try:
            with open(LOCAL_PATH, "r", encoding="utf-8") as f:
                code = f.read()
            match = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', code)
            return match.group(1) if match else None
        except FileNotFoundError:
            return None

    def update_script():
        remote_version, remote_code = get_remote_version_and_code(github_url)
        local_version = get_local_version()

        if remote_version and (local_version is None or version.parse(remote_version) > version.parse(local_version)):
            with open(LOCAL_PATH, "w", encoding="utf-8") as f:
                f.write(remote_code)
            tool.print_success(f"Updated from {local_version} to {remote_version}")
            config["version"] = remote_version
            save_config(config)
        else:
            tool.print_success("Already up to date.")

    update_script()
    return 0