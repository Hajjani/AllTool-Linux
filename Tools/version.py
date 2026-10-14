"""Single source of truth for AllTool version + config.

Canonical version lives in `.confs.json` (`"version"` key):

  - installed:  ~/.config/alltool/.confs.json
  - repo:       <repo-root>/.confs.json  (ships the release version)

Everything else (Python `__version__`, C fallbacks, packaging) reads from
here, so bumping the release = editing `.confs.json` only.

`FALLBACK_VERSION` is used only when no `.confs.json` is found (fresh
checkout without config, build sandbox, CI). Keep it in sync with
`.confs.json` when releasing.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

FALLBACK_VERSION = "3.2.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_CONF = REPO_ROOT / ".confs.json"
# Import-time snapshot (kept for compatibility). Runtime code should use
# user_conf_path() below — Path.home() can differ per process (sudo, tests).
USER_CONF = Path.home() / ".config" / "alltool" / ".confs.json"


def user_conf_path() -> Path:
    """Live config path for the current OS user (not import-time cached)."""
    try:
        return Path.home() / ".config" / "alltool" / ".confs.json"
    except Exception:
        import os as _os

        return Path(_os.environ.get("HOME", "/tmp")).expanduser() / ".config" / "alltool" / ".confs.json"

_version_cache: Optional[str] = None
_config_cache: Optional[Dict[str, Any]] = None


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


def get_config() -> Dict[str, Any]:
    """Full config dict from `.confs.json` (user > repo > minimal fallback)."""
    global _config_cache
    if _config_cache is not None:
        return dict(_config_cache)
    data = _read_json(user_conf_path())
    if data is None:
        data = _read_json(REPO_CONF)
    if data is None:
        data = {"version": FALLBACK_VERSION}
    _config_cache = data
    return dict(data)


def get_version() -> str:
    """Global accessor: version string from `.confs.json`."""
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    try:
        v = get_config().get("version", FALLBACK_VERSION)
    except (AttributeError, TypeError):
        v = FALLBACK_VERSION
    _version_cache = str(v) if v else FALLBACK_VERSION
    return _version_cache


def clear_cache() -> None:
    """Reset cached reads (mainly for tests)."""
    global _version_cache, _config_cache
    _version_cache = None
    _config_cache = None


# Packaging (`pyproject.toml` dynamic version) and legacy `__version__`
# imports need a plain string attribute. This is the *fallback* value;
# runtime code should call `get_version()` to honour `.confs.json`.
__version__ = FALLBACK_VERSION
