from .base import command, ToolBase
from .bindings import load_help, HOME_DIR

@command("help", help_text="Show help in en, fr, ar, de")
def help_cmd(args: list):
    lang = args[0] if args else "en"
    data = load_help(lang)

    print(f"Usage: alltool <command> [args]")
    print(f"Available commands ({lang}):")
    print()

    for cmd_name, info in sorted(data.get("commands", {}).items()):
        desc = info.get("description", "")
        usage = info.get("usage", "")
        print(f"  {cmd_name:<15} {desc}")
        if usage:
            print(f"    Usage: {usage}")
        if "subcommands" in info:
            for sub, sub_desc in info["subcommands"].items():
                print(f"    {sub:<12} {sub_desc}")
        if "options" in info:
            for opt, opt_desc in info["options"].items():
                print(f"    {opt:<12} {opt_desc}")
        print()

    if lang != "en":
        print(f"Run 'alltool help en' for English help.")

    return 0