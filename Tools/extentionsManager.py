"""AllTool extension manager.

Discovers extension modules offered in ``AllTool-Linux/extentions/`` (and
per-user extension directories), validates that every extension file that
exposes callable functions declares a module-level ``ALLTOOL_VER`` (``str`` —
the required alltool version), checks it against the single source of truth —
the ``"version"`` key of ``.confs.json`` (via ``Tools.version.get_version``) —
and registers the extension's functions as alltool commands.

Version semantics
-----------------
``ALLTOOL_VER`` may be an exact version (``"3.2.0"``) or a packaging specifier
(``">=3.2.0"``, ``"~=3.2"``). It is compared against :func:`get_version`, which
always resolves from ``.confs.json`` (user config > repo config > fallback).

Extensions that fail validation are skipped with a warning; they never silently
register commands.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, Dict, List, Optional

try:
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
except Exception:  # packaging is a hard project dependency
    SpecifierSet = None  # type: ignore[assignment]
    Version = None  # type: ignore[assignment]

from .base import registry
from .version import get_version

REPO_ROOT = Path(__file__).resolve().parent.parent

# Extension search order: repo-shipped extensions first, then per-user dirs.
EXTENSION_DIRS: List[Path] = [
    REPO_ROOT / "extentions",          # AllTool-Linux/extentions (ships with release)
    Path.home() / ".config" / "alltool" / "extentions",  # per-user installed extensions
    Path.home() / "extentions",        # legacy user extensions directory
]


def current_version() -> str:
    """Most optimal version read: single source of truth (.confs.json)."""
    return get_version()


def version_satisfies(required: str, current: str) -> bool:
    """Check ``required`` (exact or specifier) against ``current`` version."""
    if SpecifierSet is not None and Version is not None:
        try:
            return Version(current) in SpecifierSet(required)
        except Exception:
            pass
    return required == current


def _load_module(path: Path) -> Optional[ModuleType]:
    """Import an extension ``.py`` file as an isolated module."""
    mod_name = f"alltool.ext_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        print(f"❌ Failed to load extension {path}: {exc}")
        return None
    return mod


def _module_functions(mod: ModuleType) -> Dict[str, Callable]:
    """Top-level callables defined in the module (not imported names)."""
    funcs: Dict[str, Callable] = {}
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("_"):
            continue
        if getattr(obj, "__module__", None) not in (mod.__name__, "builtins"):
            continue
        funcs[name] = obj
    return funcs


def validate_extension(mod: ModuleType, path: Path) -> Optional[str]:
    """Return ``None`` when the extension is valid, else an error message.

    Every extension file that offers functions must declare ``ALLTOOL_VER``
    (a ``str`` giving the required alltool version). Data-only modules that
    expose no functions are exempt.
    """
    funcs = _module_functions(mod)
    if not funcs:
        return None
    ver = getattr(mod, "ALLTOOL_VER", None)
    if ver is None:
        return (
            f"extension {path.name} offers functions {list(funcs)} but declares "
            "no ALLTOOL_VER (required alltool version str)"
        )
    if not isinstance(ver, str):
        return (
            f"extension {path.name} ALLTOOL_VER must be a str, got "
            f"{type(ver).__name__}"
        )
    return None


def load_extensions(reg=None) -> Dict[str, dict]:
    """Discover, validate and register all extension commands.

    ``reg`` defaults to the global :data:`Tools.base.registry`. Returns a report
    keyed by extension path::

        {
            "/path/to/ext/foo.py": {
                "status": "ok" | "load_error" | "invalid" | "version_mismatch",
                "functions": [...registered command names...],
                "required": "ALLTOOL_VER value or None",
                "error": None or error message,
            },
            ...
        }
    """
    if reg is None:
        from .base import registry as _reg  # noqa: WPS439

        reg = _reg

    report: Dict[str, dict] = {}
    current = current_version()

    for ext_dir in EXTENSION_DIRS:
        if not ext_dir.is_dir():
            continue
        for path in sorted(ext_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            key = str(path)

            mod = _load_module(path)
            if mod is None:
                report[key] = {
                    "status": "load_error",
                    "functions": [],
                    "required": None,
                    "error": f"could not import {path}",
                }
                continue

            err = validate_extension(mod, path)
            if err:
                print(f"⚠️ {err}")
                report[key] = {
                    "status": "invalid",
                    "functions": list(_module_functions(mod)),
                    "required": getattr(mod, "ALLTOOL_VER", None),
                    "error": err,
                }
                continue

            required = getattr(mod, "ALLTOOL_VER", None)
            if required is not None and not version_satisfies(required, current):
                print(
                    f"⚠️ Extension {path.name} requires alltool {required}, "
                    f"running v{current} — skipped"
                )
                report[key] = {
                    "status": "version_mismatch",
                    "functions": list(_module_functions(mod)),
                    "required": required,
                    "error": f"requires {required}, running {current}",
                }
                continue

            registered: List[str] = []
            for name, func in _module_functions(mod).items():
                cmd_name = getattr(func, "alltool_cmd", None) or name
                help_text = getattr(func, "alltool_help", "") or ""
                reg.register(cmd_name, func, help_text=help_text)
                registered.append(cmd_name)

            report[key] = {
                "status": "ok",
                "functions": registered,
                "required": required,
                "error": None,
            }

    return report


def extension_commands() -> List[str]:
    """Command names currently provided by loaded extensions."""
    names: List[str] = []
    for info in load_extensions().values():
        if info["status"] == "ok":
            names.extend(info["functions"])
    return sorted(set(names))
