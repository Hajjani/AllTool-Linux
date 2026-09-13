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
from . import file_ops, system, media, network, power, script_runner, security, pomodoro, updater, uninstaller, help, search  # noqa: F401,E402

__version__ = "2.0.0"

__all__ = [
    "registry",
    "command",
    "ToolBase",
    "main",
]


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("Usage: alltool <command> [args]")
        print("Available commands:", ", ".join(sorted(registry.list_commands())))
        return 1

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
