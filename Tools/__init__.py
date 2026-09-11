from .base import registry, command, ToolBase
from . import file_ops, system, media, network, power, script_runner, security, pomodoro, updater, uninstaller, help

__version__ = "2.0.0"

__all__ = [
    "registry",
    "command",
    "ToolBase",
    "main",
]

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: alltool <command> [args]")
        print("Available commands:", ", ".join(sorted(registry.list_commands())))
        return 1

    cmd_name = sys.argv[1]
    handler = registry.get(cmd_name)

    if not handler:
        print(f"❌ Unknown command: {cmd_name}")
        print("Use 'alltool help' to see available commands.")
        return 1

    try:
        return handler(sys.argv[2:])
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
        return 130
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())