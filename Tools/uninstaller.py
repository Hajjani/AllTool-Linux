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
    # Allowlist: only delete inside HOME_DIR or the known ~/bin entry points.
    # Prevents a tampered installed_files list from deleting arbitrary paths.
    bin_dir = Path.home() / "bin"
    allowed_roots = [HOME_DIR.resolve(), bin_dir.resolve()]
    allowed_names = {"alltool", "AllTool.py", "AllTools.py", "Tools"}

    def _allowed(path: Path) -> bool:
        try:
            rp = path.resolve()
        except OSError:
            return False
        for root in allowed_roots:
            try:
                if rp == root or root in rp.parents:
                    return True
            except OSError:
                continue
        # Also allow the exact ~/bin entry points by name even if ~/bin moved.
        return rp.parent == bin_dir.resolve() and rp.name in allowed_names

    for file_path in installed_files:
        path = Path(file_path)
        if not _allowed(path):
            tool.print_warning(f"Skipped (outside allowed roots): {path}")
            unfound.append(str(path))
            continue
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

    # Remove ~/bin entry points installed by installer.sh (not in installed_files).
    for name in ("alltool", "AllTool.py", "AllTools.py"):
        p = bin_dir / name
        try:
            if p.is_file() or p.is_symlink():
                p.unlink()
                tool.print_success(f"Removed: {p}")
        except Exception as e:
            tool.print_warning(f"Could not remove {p}: {e}")
    tools_pkg = bin_dir / "Tools"
    try:
        if tools_pkg.is_dir():
            import shutil
            shutil.rmtree(tools_pkg)
            tool.print_success(f"Removed: {tools_pkg}")
    except Exception as e:
        tool.print_warning(f"Could not remove {tools_pkg}: {e}")

    tool.print_success("AllTool uninstalled successfully!")
    print("Note: pip package (if installed via 'pip install -e .') must be removed separately:")
    print("  pip3 uninstall -y alltool")
    return 0