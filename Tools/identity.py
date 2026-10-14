"""Tool-owner identity: `.confs.json` is the source of the user name.

The config file owns the identity the tool acts as:

  - top-level `"username"`  -> OS login that owns `~/.config/alltool`
  - `"home_dir"` / `"bin_dir"` / `"cache_dir"` / `"logs_dir"` -> that user's folders

Stamped at install time (installer.sh / `make install-config`). At runtime,
if the current OS user no longer matches the stored one (user renamed,
home copied to another account, sudo -u, ...), the tool asks whether to
update `.confs.json` to the current user and rewrites the owned paths on
accept. Never raises — identity must never break the tool.
"""

import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import version as _v


def current_username() -> str:
    """Best-effort OS login name (never raises, may be empty)."""
    for probe in (
        lambda: getpass.getuser(),
        lambda: os.environ.get("USER", ""),
        lambda: os.environ.get("LOGNAME", ""),
        lambda: Path.home().name,
    ):
        try:
            name = (probe() or "").strip()
        except Exception:
            continue
        if name:
            return name
    return ""


def current_home() -> Path:
    try:
        return Path.home()
    except Exception:
        return Path(os.environ.get("HOME", "/tmp")).expanduser()


def user_conf_path() -> Path:
    """Live config path for the *current* OS user (not import-time cached)."""
    return current_home() / ".config" / "alltool" / ".confs.json"


def expand(p: Any, home: Optional[Path] = None) -> str:
    """Expand `~` against the given (or current) home; pass through otherwise."""
    if not isinstance(p, str) or not p:
        return ""
    if p.startswith("~"):
        base = home if home is not None else current_home()
        return str(base / p[2:] if p.startswith("~/") else base / p[1:])
    return os.path.expandvars(os.path.expanduser(p))


def expected_dirs(home: Optional[Path] = None) -> Dict[str, str]:
    base = home if home is not None else current_home()
    root = base / ".config" / "alltool"
    return {
        "home_dir": str(root),
        "bin_dir": str(root / "bin"),
        "cache_dir": str(root / "cache"),
        "logs_dir": str(root / "logs"),
    }


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if path.is_file():
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError):
        pass
    return None


def _write_json(path: Path, data: Dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def mismatch_reason(config: Dict[str, Any]) -> Optional[str]:
    """Why the stored identity doesn't fit the current OS user (None = OK)."""
    if not isinstance(config, dict):
        return "unreadable config"
    me = current_username()
    stored = str(config.get("username", "") or "").strip()
    if not stored:
        return "no username stored in .confs.json"
    if me and stored != me:
        return f"config belongs to '{stored}' but current user is '{me}'"
    # Paths pointing at another home are stale even if the name matches
    # (e.g. home copied between accounts).
    try:
        want = Path(expected_dirs()["home_dir"]).resolve()
        have = Path(expand(config.get("home_dir")) or str(want)).resolve()
        if have != want:
            return f"config home '{have}' does not match current home '{want}'"
    except Exception:
        pass
    return None


def build_corrected_config(
    config: Dict[str, Any],
    username: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return a copy of config re-owned by (username, home)."""
    me = username if username is not None else current_username()
    base = home if home is not None else current_home()
    fixed = dict(config)
    old_user = str(config.get("username", "") or "").strip()
    old_home: Optional[Path] = None
    try:
        raw = expand(config.get("home_dir"), base)
        old_home = Path(raw).resolve() if raw else None
    except Exception:
        old_home = None
    if me:
        fixed["username"] = me
    fixed.update(expected_dirs(base))
    # Rewrite absolute installed_files entries that still point at the old home.
    try:
        new_home = Path(str(base / ".config" / "alltool")).resolve()
        files = fixed.get("installed_files")
        if isinstance(files, list) and old_home is not None and old_home != new_home:
            fixed["installed_files"] = [
                str(new_home / Path(expand(e)).resolve().relative_to(old_home))
                if isinstance(e, str) and not e.startswith("~")
                and str(Path(expand(e)).resolve()).startswith(str(old_home) + os.sep)
                else e
                for e in files
            ]
    except Exception:
        pass
    # A new owner must not inherit the previous user's cached sudo creds.
    # Only an unchanged identity keeps them.
    try:
        sudo = fixed.get("sudo")
        if isinstance(sudo, dict) and sudo.get("cached") and me:
            if old_user != me:
                fixed["sudo"] = {"cached": False}
    except Exception:
        pass
    return fixed


def _ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    hint = "[Y/n]" if default_yes else "[y/N]"
    try:
        if not sys.stdin.isatty():
            return False
        reply = input(f"{prompt} {hint}: ").strip().lower()
    except (EOFError, OSError, KeyboardInterrupt):
        return False
    if not reply:
        return default_yes
    return reply in ("y", "yes")


def ensure_user_identity(
    config_path: Optional[Path] = None,
    *,
    interactive: bool = True,
    auto_fix: bool = False,
    ask: bool = True,
) -> Tuple[Dict[str, Any], bool]:
    """Load config, fix owner identity if stale. Returns (config, updated).

    - `auto_fix=True` rewrites without asking (install/tests).
    - otherwise asks on a TTY; non-TTY never prompts, just warns.
    - never raises.
    """
    try:
        path = Path(config_path) if config_path else user_conf_path()
        config = _read_json(path)
        if config is None:
            # Fall back to shipped template so callers always get full confs.
            config = _read_json(_v.REPO_CONF)
            if config is None:
                return {"version": _v.FALLBACK_VERSION}, False
            # Template (repo copy) has no installed home yet: stamp it in
            # memory only; the file gets written on first save/accept.
            if mismatch_reason(config) and (auto_fix or not ask):
                return build_corrected_config(config), False
            # Fall through to the prompt below using the template contents.
        reason = mismatch_reason(config)
        if reason is None:
            return config, False
        if auto_fix or not ask:
            if auto_fix and path == user_conf_path():
                fixed = build_corrected_config(config)
                if _write_json(path, fixed):
                    _v.clear_cache()
                    try:
                        from . import bindings as _b  # lazy: avoid import cycle

                        _b._config_cache = dict(fixed)
                    except Exception:
                        pass
                    return fixed, True
            return config, False
        if interactive:
            me = current_username() or "<unknown>"
            print(f"⚠️  {reason}.")
            if _ask_yes_no(f"   Update .confs.json to act as '{me}' in {current_home()}?", True):
                fixed = build_corrected_config(config)
                if _write_json(path, fixed):
                    _v.clear_cache()
                    try:
                        from . import bindings as _b  # lazy: avoid import cycle

                        _b._config_cache = dict(fixed)
                    except Exception:
                        pass
                    print(f"✅ Identity updated: now acting as '{me}'.")
                    return fixed, True
                print("❌ Could not write .confs.json — continuing with stored identity.")
                return config, False
            print("ℹ️  Keeping stored identity.")
            return config, False
        print(f"⚠️  {reason} (non-interactive: keeping stored identity).")
        return config, False
    except Exception:
        try:
            return _v.get_config(), False
        except Exception:
            return {"version": _v.FALLBACK_VERSION}, False
