# AllTool-Linux — Agent Instructions

## Project Overview
A modular Python CLI tool with 20+ utilities for Linux system management, multimedia, networking, security, and productivity. Currently transitioning from a monolithic `AllTools.py` (1025 lines) to a modular package under `Tools/`.

## Repository Structure
```
AllTool-Linux/
├── AllTools.py           # Monolithic entrypoint (legacy, being phased out)
├── Tools/                # Modular tools package (target architecture)
│   ├── __init__.py       # Package exports, command registry
│   ├── uninstaller.py    # Only extracted tool so far
│   └── (more to come)
├── AllToolInstaller.py   # Separate installer script (ignore per user)
├── README.md
└── LICENSE
```

## Current Commands (from AllTools.py)
`create`, `format`, `refresh`, `help`, `sound`, `netspeed`, `requirement`, `video`, `downloadvs`, `power`, `sf`, `sif`, `up`, `run`, `psg`, `hs`, `sr`, `wea`, `pr`, `cl`, `upa`, `un`

## Modularization Plan

### 1. Package Structure
```
Tools/
├── __init__.py           # Command registry, base classes, shared utilities
├── base.py               # BaseTool class with common patterns
├── file_ops.py           # create, format
├── system.py             # refresh, sf, sif, up, cl
├── media.py              # sound, video, downloadvs
├── network.py            # netspeed, sr, wea
├── power.py              # power
├── script_runner.py      # run
├── security.py           # psg, hs
├── pomodoro.py           # pr
├── updater.py            # upa
├── uninstaller.py        # un (already exists, needs enhancement)
└── help.py               # help (multi-language)
```

### 2. Entry Point Strategy
- Keep `AllTools.py` as thin wrapper that imports from `Tools` and dispatches
- Or create new `alltool` entry point via `pyproject.toml` / `setup.py`
- Each tool module exposes a `register(subparsers)` function for argparse subcommands

### 3. Shared Patterns to Extract
- `get_output()`, `has_command()`, `detect_and_run()` → `Tools/utils.py`
- Multi-language help texts → `Tools/help.py` or JSON files
- Common CLI patterns (confirmation prompts, error handling) → `Tools/base.py`

### 4. Dependencies
- External: `requests`, `beautifulsoup4`, `packaging`, `mpv`, `ffmpeg`, `yt-dlp`, `speedtest-cli`, `inxi`, `powerprofilesctl`
- Stdlib: `cmd`, `subprocess`, `os`, `hashlib`, `json`, `signal`, `pathlib`

## Developer Commands
```bash
# Run from source (current)
python3 AllTools.py <command> [args]

# After modularization (target)
python3 -m Tools <command> [args]
# or via installed entry point: alltool <command> [args]
```

## Testing
No test suite exists. When adding tests:
- Use `pytest` with fixtures for subprocess-based commands
- Mock external commands (`mpv`, `yt-dlp`, `powerprofilesctl`, etc.)
- Integration tests require Linux environment with dependencies installed

## Key Constraints & Gotchas
- **LOCAL_PATH inconsistency**: `AllTools.py` uses `~/bin/AllTool.py` (singular) but file is `AllTools.py` (plural)
- **Uninstaller mismatch**: `Tools/uninstaller.py` expects `paths: list` but `AllTools.py:24` calls `uninstall(LOCAL_PATH)` with single string
- **No version in source**: `__version__` regex in updater expects version string that doesn't exist in current files
- **Hardcoded paths**: `/tmp/pomodoro_timer.py`, `~/.alltool_pomodoro.log`, `~/bin/`
- **Sudo usage**: Multiple commands use `sudo` without password handling

## Style Conventions
- Emoji-heavy CLI output (🔍, ✅, ❌, ⚠️, 🚀, etc.)
- Multi-language help texts (en, fr, ar, de) embedded in source
- Interactive confirmations for destructive operations (`format`, `un`)
- Subcommands use short aliases (`pws`, `pwn`, `pwp` for power modes)

## References
- `README.md`: Full feature documentation
- `AllTools.py:167-1025`: Complete command implementations
- `Tools/uninstaller.py`: First extracted module (incomplete)