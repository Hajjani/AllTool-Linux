"""AllTool modular package — command registry + dispatcher.

AllTools.py (repo root, thin wrapper) is the user-facing center of action;
it delegates here. Other centers (`./alltool`, `python -m Tools`, installed
`alltool` console_script) all call this same `main()`.

C components (Tools/c_src/*, built via Makefile `install-user`/`install-c`)
are used through Tools/bindings.py with pure-Python fallbacks, so commands
work even before `make build-c`.
"""
import sys

from .base import registry, command, ToolBase
from .version import FALLBACK_VERSION, get_config, get_version
from . import file_ops, system, media, network, power, script_runner, security, pomodoro, updater, uninstaller, help  # noqa: F401,E402

# Global version — resolved from `.confs.json` (user > repo > fallback).
# Bump releases by editing `.confs.json` only (see Tools/version.py).
__version__ = get_version()

__all__ = [
    "registry",
    "command",
    "ToolBase",
    "get_version",
    "get_config",
    "FALLBACK_VERSION",
    "main",
]


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("Usage: alltool <command> [args]")
        print("Available commands:", ", ".join(sorted(registry.list_commands())))
        return 1

    # Global version flag — always resolved from `.confs.json`.
    if argv[0] in ("-v", "--version", "version"):
        print(f"alltool v{get_version()}")
        return 0

    # Identity check: `.confs.json` owns the user name + acting folder.
    # If it no longer matches the OS user, ask to update it (never fatal).
    try:
        from .identity import ensure_user_identity

        ensure_user_identity()
    except Exception:
        pass

    cmd_name = argv[0]
    handler = registry.get(cmd_name)

    if not handler:
        print(f"❌ Unknown command: {cmd_name}")
        print("Use 'alltool help' to see available commands.")
        return 1

    try:
        return handler(argv[1:])
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
        return 130
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
