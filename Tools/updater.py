from .base import command, ToolBase
import shutil
import subprocess
from .bindings import load_config

BRANCH = "Stable"
BASE = "https://raw.githubusercontent.com/Hajjani/AllTool-Linux/refs/heads/Stable"
REMOTE_CONF_URL = f"{BASE}/.confs.json"
INSTALLER_URL = f"{BASE}/installer.sh"


@command("upa", aliases=["update"], help_text="Update AllTool to the latest stable version")
def updater(args: list):
    tool = ToolBase()

    if args:
        print("Usage: alltool upa")
        print("  Updates to the latest stable version (takes no arguments).")
        return 1

    try:
        import requests
    except ImportError:
        tool.print_error("Missing packages. Install with: pip install requests")
        return 1

    local_version = load_config().get("version")
    tool.print_status(f"Version detected: {local_version}")

    try:
        response = requests.get(REMOTE_CONF_URL, timeout=10)
        response.raise_for_status()
        remote_version = response.json().get("version")
    except Exception as e:
        tool.print_error(f"Failed to fetch remote version: {e}")
        return 1
    tool.print_status(f"Latest version ({BRANCH}): {remote_version}")

    if not remote_version:
        tool.print_error("Remote config has no version field.")
        return 1
    if local_version == remote_version:
        tool.print_success("Already up to date.")
        return 0

    if shutil.which("curl") is None:
        tool.print_error("curl is not installed (required for updates).")
        return 1
    if shutil.which("bash") is None:
        tool.print_error("bash is not installed (required for updates).")
        return 1

    tool.print_status(f"Updating to latest version ({BRANCH})...")
    try:
        curl = subprocess.run(
            ["curl", "-fsSL", INSTALLER_URL],
            capture_output=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        tool.print_error("Download timed out.")
        return 1
    except OSError as e:
        tool.print_error(f"Failed to run curl: {e}")
        return 1
    if curl.returncode != 0:
        tool.print_error(
            f"Download failed: {curl.stderr.decode(errors='replace').strip()}"
        )
        return 1

    try:
        result = subprocess.run(["bash"], input=curl.stdout, timeout=1800)
    except subprocess.TimeoutExpired:
        tool.print_error("Installer timed out.")
        return 1
    except OSError as e:
        tool.print_error(f"Failed to run installer: {e}")
        return 1
    if result.returncode != 0:
        tool.print_error(f"Installer failed with exit code {result.returncode}.")
        return result.returncode

    tool.print_success(f"Updated to version {remote_version}")
    return 0
