from .base import command, ToolBase
import os
import subprocess
from .bindings import AllToolCompiler, HOME_DIR

@command("run", aliases=["exec"], help_text="Auto-detect and run scripts. Compiles C/C++ with caching.")
def run_script(args: list):
    if not args:
        print("Usage: alltool run <script> [-t]")
        print("  -t: Compile temporarily in /tmp")
        return 1

    temp_mode = False
    script_args = []
    for arg in args:
        if arg == "-t":
            temp_mode = True
        else:
            script_args.append(arg)

    if not script_args:
        print("Usage: alltool run <script> [-t]")
        return 1

    script_path = os.path.expanduser(script_args[0])
    if not os.path.exists(script_path):
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

    compiled_extensions = {".c", ".cc", ".cpp", ".cxx", ".rs", ".go", ".zig"}

    if ext in script_extensions:
        cmd = script_extensions[ext] + [script_path] + script_args[1:]
        print(f"🚀 Running {ext[1:].upper()} script...")
        return subprocess.run(cmd).returncode

    elif ext in compiled_extensions:
        compiler = AllToolCompiler()
        cache_dir = str(HOME_DIR / "cache") if not temp_mode else "/tmp"
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
        with open(script_path, "r") as f:
            first_line = f.readline().strip()
        if first_line.startswith("#!"):
            print(f"🚀 Running via shebang: {first_line}")
            return subprocess.run([script_path] + script_args[1:]).returncode
        else:
            print("❌ Unknown script type. Please specify manually.")
            return 1