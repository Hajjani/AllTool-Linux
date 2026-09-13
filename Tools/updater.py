from .base import command, ToolBase
import re
from pathlib import Path
from .bindings import HOME_DIR, load_config, save_config

# Installed user-facing script (installer.sh: INSTALL_DIR="$HOME/bin",
# SCRIPT_NAME="AllTools.py"). Must NEVER point inside HOME_DIR/"bin"
# (~/.config/alltool/bin) — that holds the compiled C libs + alltool_runner
# binary, which writing Python code over would corrupt.
LOCAL_PATH = str(Path.home() / "bin" / "AllTools.py")

ProtectedDir = HOME_DIR / "bin"


@command("upa", aliases=["update"], help_text="Update AllTool to stable (st) or preview (pv) version")
def updater(args: list):
    tool = ToolBase()
    config = load_config()
    try:
        Path(LOCAL_PATH).resolve().relative_to(ProtectedDir.resolve())
        tool.print_error(f"Refusing to update inside C libs dir: {LOCAL_PATH}")
        return 1
    except ValueError:
        pass  # target is outside the protected dir — safe to proceed

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

    try:
        import requests
        from packaging import version
    except ImportError:
        tool.print_error("Missing packages. Install with: pip install requests packaging")
        return 1

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
        except (FileNotFoundError, OSError):
            return None

    def update_script():
        remote_version, remote_code = get_remote_version_and_code(github_url)
        local_version = get_local_version()

        if remote_version and (local_version is None or version.parse(remote_version) > version.parse(local_version)):
            try:
                Path(LOCAL_PATH).parent.mkdir(parents=True, exist_ok=True)
                with open(LOCAL_PATH, "w", encoding="utf-8") as f:
                    f.write(remote_code)
                try:
                    Path(LOCAL_PATH).chmod(0o755)
                except OSError:
                    pass
            except OSError as e:
                tool.print_error(f"Failed to write {LOCAL_PATH}: {e}")
                return
            tool.print_success(f"Updated {LOCAL_PATH} from {local_version} to {remote_version}")
            config["version"] = remote_version
            save_config(config)
        else:
            tool.print_success("Already up to date.")

    update_script()
    return 0