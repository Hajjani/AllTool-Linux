"""Search installed AllTool commands by name, alias, or keyword.

Usage:
    alltool search <command|keyword> [lang]
    alltool search --list
    alltool find <command|keyword>      (alias)
    alltool lookup <command|keyword>    (alias)

Examples:
    alltool search power      # full usage for the `power` command
    alltool search psg        # exact match wins over keyword matches
    alltool search password   # keyword search across descriptions/options
    alltool search video fr   # show results with French descriptions
"""
import difflib

from .base import command, registry
from .bindings import load_help

_LANGS = ("en", "fr", "ar", "de")


def _resolve_lang(args: list) -> tuple:
    """Split trailing lang code off args. Returns (query_parts, lang)."""
    if args and args[-1].lower() in _LANGS and len(args) > 1:
        return args[:-1], args[-1].lower()
    return args, "en"


def _describe(cmd_name: str, info: dict, lang: str) -> str:
    lang_map = info.get("lang")
    if isinstance(lang_map, dict) and lang in lang_map:
        return lang_map[lang]
    return info.get("description", "")


def _searchable_text(cmd_name: str, info: dict, lang: str) -> str:
    parts = [cmd_name, info.get("description", ""), info.get("usage", "")]
    parts += info.get("aliases", []) or []
    parts += info.get("examples", []) or []
    sub = info.get("subcommands", {}) or {}
    parts += list(sub.keys()) + list(sub.values())
    opts = info.get("options", {}) or {}
    parts += list(opts.keys())
    for v in opts.values():
        parts += v if isinstance(v, list) else [str(v)]
    lang_map = info.get("lang", {}) or {}
    if isinstance(lang_map, dict):
        parts += [str(v) for v in lang_map.values()]
    # Registry aliases may be newer than .help.json — include them too.
    for alias, real in registry.aliases.items():
        if real == cmd_name:
            parts.append(alias)
    return "\n".join(parts).lower()


def _print_detail(cmd_name: str, info: dict, lang: str):
    print(f"🔍 {cmd_name} — {_describe(cmd_name, info, lang)}")
    if info.get("usage"):
        print(f"   Usage: {info['usage']}")
    # Merge aliases from .help.json and the live registry.
    aliases = set(info.get("aliases", []) or [])
    for alias, real in registry.aliases.items():
        if real == cmd_name:
            aliases.add(alias)
    if aliases:
        print(f"   Aliases: {', '.join(sorted(aliases))}")
    if "subcommands" in info:
        print("   Subcommands:")
        for sub, sub_desc in info["subcommands"].items():
            print(f"     {sub:<12} {sub_desc}")
    if "options" in info:
        print("   Options:")
        for opt, opt_desc in info["options"].items():
            desc = ", ".join(opt_desc) if isinstance(opt_desc, list) else opt_desc
            print(f"     {opt:<12} {desc}")
    if info.get("examples"):
        print("   Examples:")
        for ex in info["examples"]:
            print(f"     $ {ex}")


@command("search", aliases=["find", "lookup"], help_text="Search commands usage by name or keyword")
def search_cmd(args: list):
    data = load_help("en")
    commands = data.get("commands", {})

    # Fall back to the live registry if .help.json is missing entries
    # (e.g. installed copy out of date): every registered command is searchable.
    for name in registry.list_commands():
        if name not in commands:
            commands[name] = {
                "description": registry.get_help(name) or name,
                "usage": f"alltool {name}",
                "aliases": [a for a, real in registry.aliases.items() if real == name],
            }

    if not args or args[0] in ("-h", "--help"):
        print("Usage: alltool search <command|keyword> [lang]")
        print("       alltool search --list")
        print(f"Languages: {', '.join(_LANGS)} (append, e.g. 'alltool search power fr')")
        print(f"Available commands: {', '.join(sorted(commands))}")
        return 0 if args and args[0] in ("-h", "--help") else 1

    if args[0] in ("--list", "-l", "list"):
        # `search --list fr` works; plain `search --list` defaults to en.
        lang = args[1].lower() if len(args) > 1 and args[1].lower() in _LANGS else "en"
        for cmd_name in sorted(commands):
            print(f"  {cmd_name:<15} {_describe(cmd_name, commands[cmd_name], lang)}")
        return 0

    query_parts, lang = _resolve_lang(args)
    query = " ".join(query_parts).strip().lower()
    if not query:
        print("❌ Empty search query.")
        print("Usage: alltool search <command|keyword> [lang]")
        return 1

    # Resolve aliases through the registry (e.g. `search sysinfo` -> `sif`).
    real = registry.aliases.get(query, query)
    if real in commands:
        _print_detail(real, commands[real], lang)
        return 0

    scored = []
    for cmd_name, info in commands.items():
        text = _searchable_text(cmd_name, info, lang)
        if query == cmd_name.lower():
            scored.append((100, cmd_name))
        elif cmd_name.lower().startswith(query):
            scored.append((75, cmd_name))
        elif query in cmd_name.lower():
            scored.append((60, cmd_name))
        elif query in text:
            scored.append((40, cmd_name))

    scored.sort(key=lambda item: (-item[0], item[1]))

    if len(scored) == 1:
        _print_detail(scored[0][1], commands[scored[0][1]], lang)
        return 0

    if scored:
        print(f"🔍 {len(scored)} match(es) for '{query}':\n")
        for _, cmd_name in scored:
            print(f"  {cmd_name:<15} {_describe(cmd_name, commands[cmd_name], lang)}")
        print("\n💡 Run 'alltool search <command>' for full usage of one command.")
        return 0

    print(f"❌ No command matches '{query}'.")
    suggestions = difflib.get_close_matches(query, list(commands.keys()), n=3, cutoff=0.6)
    if suggestions:
        print(f"💡 Did you mean: {', '.join(suggestions)}?")
    else:
        print(f"Available commands: {', '.join(sorted(commands))}")
    return 1
