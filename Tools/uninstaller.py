from .base import command, ToolBase
from pathlib import Path
import json
from .bindings import HOME_DIR, load_config, get_installed_files

@command("un", aliases=["uninstall"], help_text="Uninstall AllTool and all associated files")
def uninstall(args: list):
    tool = ToolBase()

    print("⚠️  Welcome to AllTool Uninstaller")
    print("This will remove AllTool and all its components.")
    if not tool.confirm("Are you sure you want to uninstall AllTool? This action cannot be undone."):
        print("Uninstall cancelled.")
        return 0

    # Clear cached sudo credentials first (same as Makefile uninstall's
    # `alltool_runner sudo-clear`), via C lib when built, else JSON fallback.
    try:
        tool.sudo.clear_cache(str(HOME_DIR / ".confs.json"))
    except Exception:
        pass

    try:
        installed_files = get_installed_files()
    except Exception:
        installed_files = []
    config_path = HOME_DIR / ".confs.json"

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            installed_files = config.get("installed_files", installed_files)
        except (OSError, ValueError):
            pass

    unfound = []
    for file_path in installed_files:
        path = Path(file_path)
        if path.exists():
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    import shutil
                    shutil.rmtree(path)
                tool.print_success(f"Removed: {path}")
            except Exception as e:
                tool.print_error(f"Failed to remove {path}: {e}")
                unfound.append(str(path))
        else:
            unfound.append(str(path))

    if unfound:
        tool.print_warning(f"{len(unfound)} paths not found:")
        for u in unfound:
            print(f"  - {u}")

    try:
        if HOME_DIR.exists():
            import shutil
            shutil.rmtree(HOME_DIR)
            tool.print_success(f"Removed config directory: {HOME_DIR}")
    except Exception as e:
        tool.print_error(f"Failed to remove config directory: {e}")

    tool.print_success("AllTool uninstalled successfully!")
    return 0