"""Developer-facing API calls for AllTool.

Stable helpers that extensions and third-party tooling should use instead of
reaching into internals directly. Everything resolves its version from the
single source of truth — ``.confs.json`` (``version`` key) via
``Tools.version.get_version``.

Privileged execution
--------------------
:func:`RootEx` runs an extension-supplied action with root privileges. The user
is prompted for confirmation on **every** call — privileges are never cached.
When not already root, the action is re-launched under ``sudo`` in a throwaway
interpreter that executes as root, then the process exits.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .base import registry, ToolBase
from .version import get_config as _get_config, get_version as _get_version

REPO_ROOT = Path(__file__).resolve().parent.parent

# Stored privileged actions keyed by token, used for the sudo re-entry path.
_PRIV_ACTIONS: Dict[str, Callable] = {}
_PRIV_FILES: List[str] = []

# Guard against recursive privilege escalation via sudo re-entry.
_PRIV_ENTRY = "ALLTOOL_PRIV_ENTRY"


# ---------------------------------------------------------------------------
# Version / config (single source of truth: .confs.json)
# ---------------------------------------------------------------------------


def get_version() -> str:
    """Return the alltool version from ``.confs.json`` (user > repo > fallback)."""
    return _get_version()


def get_config() -> Dict[str, Any]:
    """Return the full parsed ``.confs.json`` dict."""
    return _get_config()


# ---------------------------------------------------------------------------
# Command registry helpers
# ---------------------------------------------------------------------------


def register_command(
    name: str,
    handler: Callable,
    aliases: Optional[List[str]] = None,
    help_text: str = "",
) -> None:
    """Register a command handler in the global alltool registry."""
    registry.register(name, handler, aliases=aliases, help_text=help_text)


def unregister_command(name: str) -> bool:
    """Remove a command from the registry. Returns True if it existed."""
    real_name = registry.aliases.get(name, name)
    existed = real_name in registry.commands
    if existed:
        del registry.commands[real_name]
    registry.aliases = {a: n for a, n in registry.aliases.items() if n != real_name}
    return existed


def list_commands() -> List[str]:
    """List all registered command names."""
    return sorted(registry.list_commands())


def get_command(name: str) -> Optional[Callable]:
    """Look up a registered command handler by name (alias-aware)."""
    return registry.get(name)


# ---------------------------------------------------------------------------
# Process / shell helpers
# ---------------------------------------------------------------------------


def run_cmd(
    cmd: List[str],
    capture: bool = True,
    check: bool = True,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Run an external command, mirroring :meth:`ToolBase.run_cmd`."""
    tool = ToolBase()
    return tool.run_cmd(cmd, capture=capture, check=check, timeout=timeout)


def get_output(cmd: List[str]) -> str:
    """Return stripped stdout of a command, or ``""`` on failure."""
    tool = ToolBase()
    return tool.get_output(cmd)


def has_command(cmd: str) -> bool:
    """Return True if an executable named *cmd* exists on PATH."""
    tool = ToolBase()
    return tool.has_command(cmd)


def confirm(message: str, default: bool = False) -> bool:
    """Ask the user a yes/no question. Returns their choice."""
    tool = ToolBase()
    return tool.confirm(message, default=default)


def is_root() -> bool:
    """Return True if the current process is running as root (euid == 0)."""
    try:
        return os.geteuid() == 0
    except AttributeError:  # pragma: no cover - non-Unix
        return False


# ---------------------------------------------------------------------------
# Privileged execution (prompted every time)
# ---------------------------------------------------------------------------


def _sanitize_env() -> Dict[str, str]:
    """Return a minimal, sanitized environment for the sudo child.

    Strips variables that can be abused for code injection (LD_PRELOAD,
    PYTHONPATH, etc.) so a malicious environment cannot hijack the re-entry
    interpreter.
    """
    keep = {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "TERM",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
    }
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["ALLTOOL_PRIV_ENTRY"] = "1"  # mark the re-entry process
    return env


def _write_action_file(action: Callable[[], Any]) -> str:
    """Persist an action reference to a mode-0600 temp file.

    Returns the temp-file path. The sudo child reads it to locate and run the
    action. The file is removed after use.
    """
    module_name = getattr(action, "__module__", None) or ""
    func_name = getattr(action, "__name__", None) or ""
    if not module_name or not func_name:
        raise ValueError("action must be a top-level function with a module and name")

    payload = json.dumps({"module": module_name, "name": func_name}).encode()
    fd, path = tempfile.mkstemp(prefix="alltool_priv_", suffix=".json", dir=str(Path(tempfile.gettempdir())))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    _PRIV_FILES.append(path)
    return path


def _cleanup_action_files() -> None:
    """Remove any leftover privileged action temp files."""
    for path in list(_PRIV_FILES):
        try:
            os.unlink(path)
        except OSError:
            pass
        _PRIV_FILES.remove(path)


def _run_privileged_action(token_file: str) -> None:
    """Internal re-entry target executed by the sudo child as root.

    Reads the action reference from *token_file*, imports and calls it, then
    exits with an appropriate status code. Not part of the public API.
    """
    try:
        with open(token_file, "r") as f:
            data = json.load(f)
        module = importlib.import_module(data["module"])
        action = getattr(module, data["name"])
        if not callable(action):
            print("❌ Privileged action reference is not callable", file=sys.stderr)
            sys.exit(1)
        result = action()
        sys.exit(0 if result in (None, 0) else 1)
    except SystemExit as exc:
        sys.exit(exc.code if isinstance(exc.code, int) else 1)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Privileged action failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            os.unlink(token_file)
        except OSError:
            pass


def RootEx(action: Callable[[], Any], description: str) -> Any:
    """Execute *action* with root privileges, prompting the user each time.

    Parameters
    ----------
    action : callable
        Zero-argument callable (typically an extension function) to run as
        root. Must be a top-level function so the sudo child can re-import it.
    description : str
        Human-readable description shown to the user when asking for privilege.

    Returns
    -------
    The return value of *action* when run as root in-process, or the sudo
    re-launch return code when elevation was required. ``None`` when the user
    denies the privilege request or the action is not callable.

    Notes
    -----
    The user is asked for confirmation on **every** call. Privileges are never
    cached or remembered between calls. The sudo child runs with a sanitized
    environment (no LD_PRELOAD / PYTHONPATH / etc.).
    """
    if not callable(action):
        print("❌ RootEx: action must be callable.")
        return None
    if not isinstance(description, str) or not description.strip():
        print("❌ RootEx: description must be a non-empty string.")
        return None

    tool = ToolBase()
    token = f"{getattr(action, '__module__', '?')}.{getattr(action, '__name__', 'action')}"

    print(f"🔐 Root request: {description}")
    if not tool.confirm(f"Grant root privilege to run '{description}'?", default=False):
        print("❌ Root privilege denied.")
        _cleanup_action_files()
        return None

    # Already root: run directly.
    if is_root():
        try:
            return action()
        finally:
            _cleanup_action_files()

    # Not root: re-launch under sudo as a throwaway interpreter that runs the
    # action as root, then exit. No -E (environment is sanitized instead).
    action_file = _write_action_file(action)
    try:
        reentry = (
            "import sys; "
            "from Tools.APIcalls import _run_privileged_action; "
            "_run_privileged_action(sys.argv[1])"
        )
        env = _sanitize_env()
        cmd = ["sudo", sys.executable, "-c", reentry, action_file]
        print("🚀 Escalating to root via sudo ...")
        result = subprocess.run(cmd, env=env)
        return result.returncode
    finally:
        _cleanup_action_files()


# ---------------------------------------------------------------------------
# Path helpers (from .confs.json — single source of truth)
# ---------------------------------------------------------------------------


def config_value(key: str, default: Any = None) -> Any:
    """Read a single value from ``.confs.json`` by dotted key (e.g. ``home_dir``)."""
    cfg = get_config()
    cur: Any = cfg
    for part in str(key).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def home_dir() -> Path:
    """Acting home dir from ``.confs.json`` (falls back to OS home)."""
    return Path(str(config_value("home_dir", Path.home()))).expanduser()


def config_dir() -> Path:
    """Directory holding ``.confs.json`` for the current user."""
    return Path.home() / ".config" / "alltool"


def bin_dir() -> Path:
    """Directory where alltool entry points live."""
    return Path(str(config_value("bin_dir", home_dir() / "bin"))).expanduser()


def cache_dir() -> Path:
    """Cache directory from ``.confs.json``."""
    return Path(
        str(config_value("cache_dir", home_dir() / ".config" / "alltool" / "cache"))
    ).expanduser()


def logs_dir() -> Path:
    """Logs directory from ``.confs.json``."""
    return Path(
        str(config_value("logs_dir", home_dir() / ".config" / "alltool" / "logs"))
    ).expanduser()


def username() -> str:
    """Current OS username / configured identity."""
    try:
        from .identity import current_username

        return current_username() or ""
    except Exception:
        import getpass

        try:
            return getpass.getuser()
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# File / directory helpers
# ---------------------------------------------------------------------------


def expand_path(path: str) -> str:
    """Expand ``~`` and environment variables in a path string."""
    return os.path.expandvars(os.path.expanduser(path))


def ensure_dir(path: str | Path, mode: int = 0o700) -> Path:
    """Create *path* as a directory (parents included) with safe perms.

    Returns the resolved :class:`Path`. Raises :exc:`OSError` on failure.
    """
    p = Path(expand_path(str(path))).resolve()
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(p, mode)
    except OSError:
        pass
    return p


def read_file(path: str | Path, binary: bool = False) -> Any:
    """Read and return file contents (text by default). Returns ``None`` if missing."""
    p = Path(expand_path(str(path)))
    if not p.is_file():
        return None
    try:
        if binary:
            with open(p, "rb") as f:
                return f.read()
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def write_file(path: str | Path, content: str | bytes, binary: bool = False, mode: int = 0o600) -> bool:
    """Write *content* to *path* with mode ``0600`` by default (sensitive-safe).

    Returns True on success, False on failure.
    """
    p = Path(expand_path(str(path))).resolve()
    try:
        ensure_dir(p.parent)
        if binary:
            data = content if isinstance(content, bytes) else content.encode()
            with open(p, "wb") as f:
                f.write(data)
        else:
            data = content if isinstance(content, str) else content.decode()
            with open(p, "w", encoding="utf-8") as f:
                f.write(data)
        os.chmod(p, mode)
        return True
    except OSError:
        return False


def secure_temp(content: str | bytes = "", prefix: str = "alltool_", suffix: str = ".tmp") -> str:
    """Create a mode-0600 temp file, write *content*, and return its path.

    Caller is responsible for removing the file when done.
    """
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=str(tempfile.gettempdir()))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content.encode() if isinstance(content, str) else content)
        os.chmod(path, 0o600)
        return path
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Version / extension helpers
# ---------------------------------------------------------------------------


def version_matches(required: str, current: Optional[str] = None) -> bool:
    """Check whether *required* (exact or PEP 440 specifier) satisfies *current*.

    *current* defaults to the running alltool version from ``.confs.json``.
    """
    cur = current if current is not None else get_version()
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version

        return Version(cur) in SpecifierSet(required)
    except Exception:
        return required == cur


def extension_required_ver(module) -> Optional[str]:
    """Return the ``ALLTOOL_VER`` string declared on a module, or ``None``."""
    return getattr(module, "ALLTOOL_VER", None)


def extension_valid(module) -> bool:
    """True if a module declaring functions also declares a str ``ALLTOOL_VER``."""
    funcs = [n for n in dir(module) if not n.startswith("_") and callable(getattr(module, n))]
    if not funcs:
        return True
    ver = extension_required_ver(module)
    return isinstance(ver, str) and bool(ver.strip())


# ---------------------------------------------------------------------------
# Sudo / privilege helpers
# ---------------------------------------------------------------------------


def sudo_available() -> bool:
    """Return True if the ``sudo`` binary exists on PATH."""
    return has_command("sudo")


def require_root() -> bool:
    """Return True if already root; otherwise prompt to escalate this process.

    Unlike :func:`RootEx`, this is a boolean check: it does not run an action.
    Useful for gates that need to know whether root is available before acting.
    """
    if is_root():
        return True
    print("⚠️  This operation requires root privileges.")
    return confirm("Escalate to root now?", default=False)


# ---------------------------------------------------------------------------
# Standardized output
# ---------------------------------------------------------------------------


def status(msg: str, icon: str = "ℹ️") -> None:
    """Print a standardized status line."""
    print(f"{icon} {msg}")


def success(msg: str) -> None:
    status(msg, "✅")


def error(msg: str) -> None:
    status(msg, "❌")


def warning(msg: str) -> None:
    status(msg, "⚠️")


def prompt_secret(message: str) -> str:
    """Read a secret from the terminal without echoing it."""
    try:
        import getpass

        return getpass.getpass(message)
    except Exception:
        return input(message + ": ")


__all__ = [
    "get_version",
    "get_config",
    "config_value",
    "register_command",
    "unregister_command",
    "list_commands",
    "get_command",
    "run_cmd",
    "get_output",
    "has_command",
    "confirm",
    "prompt_secret",
    "is_root",
    "require_root",
    "RootEx",
    "home_dir",
    "config_dir",
    "bin_dir",
    "cache_dir",
    "logs_dir",
    "username",
    "expand_path",
    "ensure_dir",
    "read_file",
    "write_file",
    "secure_temp",
    "version_matches",
    "extension_required_ver",
    "extension_valid",
    "sudo_available",
    "status",
    "success",
    "error",
    "warning",
]

