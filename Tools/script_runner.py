from .base import command, ToolBase
import os
import subprocess
from .bindings import AllToolCompiler, HOME_DIR

RUNTIME_CMDS = {
    ".py": "python3",
    ".sh": "bash",
    ".js": "node",
    ".pl": "perl",
    ".rb": "ruby",
    ".php": "php",
    ".jar": "java",
}

# Install hints live in Tools/deps.py (single source); _check_runtime below
# routes missing runtimes through deps.ensure_command (hint + ask to install).

def _check_runtime(tool, ext):
    cmd = RUNTIME_CMDS.get(ext)
    if not cmd:
        return True
    from .deps import ensure_command
    # Prints the install hint and offers to install when missing.
    return ensure_command(tool, cmd, f"{ext} files")

@command("run", aliases=["exec"], help_text="Auto-detect and run scripts. Compiles C/C++ with caching.")
def run_script(args: list):
    tool = ToolBase()
    if not args:
        print("Usage: alltool run <script> [-t] [-- script_args...]")
        print("  -t: Compile temporarily in /tmp (must appear before script path)")
        return 1

    # Only treat -t before the script path as a flag; anything after the
    # script path belongs to the script itself. Support `--` separator.
    temp_mode = False
    script_args = []
    seen_script = False
    for arg in args:
        if not seen_script and arg == "-t":
            temp_mode = True
            continue
        if not seen_script and arg == "--":
            seen_script = True  # next token is the script; keep separator semantics
            continue
        if not seen_script:
            seen_script = True
        script_args.append(arg)

    if not script_args:
        print("Usage: alltool run <script> [-t]")
        return 1

    script_path = os.path.expanduser(script_args[0])
    if not os.path.isfile(script_path):
        print(f"❌ File not found: {script_path}")
        return 1

    _, ext = os.path.splitext(script_path)

    script_extensions = {
        ".py": ["python3"],
        ".sh": ["bash"],
        ".js": ["node"],
        ".pl": ["perl"],
        ".rb": ["ruby"],
        ".php": ["php"],
        ".jar": ["java", "-jar"],
    }

    compiled_extensions = {".c", ".cc", ".cpp", ".cxx"}
    # NOTE: .rs/.go/.zig are detected by the C lib but the pure-Python
    # fallback only handles C/C++. They are intentionally NOT listed here;
    # with the C lib present they still work via AllToolCompiler.

    if ext in script_extensions:
        if not _check_runtime(tool, ext):
            return 1
        cmd = script_extensions[ext] + [script_path] + script_args[1:]
        print(f"🚀 Running {ext[1:].upper()} script...")
        try:
            return subprocess.run(cmd, timeout=300).returncode
        except subprocess.TimeoutExpired:
            tool.print_error("Execution timed out.")
            return 124

    elif ext in compiled_extensions or ext in {".rs", ".go", ".zig"}:
        compiler = AllToolCompiler()
        if ext not in compiled_extensions and compiler._lib is None:
            print(f"❌ '{ext}' requires the C compiler library (run `make build-c`).")
            return 1
        cache_dir = str(HOME_DIR / "cache") if not temp_mode else None
        result = compiler.compile_and_run(
            script_path,
            cache_dir=cache_dir,
            temp_mode=temp_mode,
            compiler_flags="-O2 -pipe"
        )

        if result.error_message:
            print(result.error_message)
        if result.exec_output:
            print(result.exec_output.rstrip())
        print(f"⏱️  Compile: {result.compile_time_ms:.2f}ms, Exec: {result.exec_time_ms:.2f}ms")
        return result.exit_code

    else:
        try:
            with open(script_path, "r") as f:
                first_line = f.readline().strip()
        except (OSError, UnicodeDecodeError) as e:
            print(f"❌ Cannot read script: {e}")
            return 1
        if first_line.startswith("#!"):
            if not os.access(script_path, os.X_OK):
                print(f"❌ File is not executable (shebang found but +x missing): {script_path}")
                print(f"   Run: chmod +x {script_path}")
                return 1
            print(f"🚀 Running via shebang: {first_line}")
            try:
                return subprocess.run([script_path] + script_args[1:], timeout=300).returncode
            except subprocess.TimeoutExpired:
                tool.print_error("Execution timed out.")
                return 124
            except PermissionError as e:
                print(f"❌ Cannot execute: {e}")
                return 1
        else:
            print("❌ Unknown script type. Please specify manually.")
            return 1