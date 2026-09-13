from .base import command, ToolBase
from .bindings import HOME_DIR
import os
import subprocess
import sys
import tempfile

_TIMER_NAME = "alltool_pomodoro_timer.py"


def _timer_path():
    # Per-user unique path (no /tmp race between users/instances).
    d = HOME_DIR / "cache"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return str(d / _TIMER_NAME)


def _pid_file():
    return str(HOME_DIR / "cache" / "pomodoro.pid")


def _pids():
    # Exact match on our timer path; avoids matching `pgrep -f` itself or
    # unrelated commands containing the substring.
    tp = _timer_path()
    try:
        result = subprocess.run(["pgrep", "-f", f"^{sys.executable}.*{tp}$"],
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [p.strip() for p in result.stdout.splitlines() if p.strip().isdigit()]

@command("pr", aliases=["pomodoro"], help_text="Manage Pomodoro sessions")
def pomodoro(args: list):
    if not args:
        print("Usage: alltool pr <sessions|stop|st>")
        print("  <number>: Start N Pomodoro sessions")
        print("  stop: Stop running timer")
        print("  st: Show status and recent activity")
        return 1

    tool = ToolBase()
    log_file = os.path.expanduser("~/.alltool_pomodoro.log")

    if args[0] == "stop":
        pids = _pids()
        # Fall back to PID file if pgrep finds nothing (e.g. pgrep missing).
        if not pids:
            try:
                with open(_pid_file()) as f:
                    pid = f.read().strip()
                    if pid.isdigit():
                        pids = [pid]
            except OSError:
                pass
        if pids:
            for pid in pids:
                try:
                    subprocess.run(["kill", pid], timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            try:
                os.unlink(_pid_file())
            except OSError:
                pass
            tool.print_success("Pomodoro timer stopped")
        else:
            tool.print_status("No Pomodoro timer running")
        return 0

    elif args[0] == "st":
        pids = _pids()
        if pids:
            tool.print_status("Pomodoro timer is running")
            print(f"📊 Process IDs: {', '.join([pid for pid in pids if pid])}")
            if os.path.exists(log_file):
                print(f"\n📄 Recent activity from {log_file}:")
                print("-" * 50)
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        print(line.strip())
            else:
                tool.print_status("No log file found")
        else:
            tool.print_status("No Pomodoro timer running")
            print("💡 Use 'alltool pr <sessions>' to start a timer")
        return 0

    try:
        sessions = int(args[0])
        if sessions <= 0:
            tool.print_error("Sessions must be greater than 0")
            return 1
        if sessions > 100:
            tool.print_error("Sessions too large (max 100).")
            return 1
        if _pids():
            tool.print_warning("A Pomodoro timer is already running. Stop it first ('alltool pr stop').")
            return 1

        pomodoro_script = f"""#!/usr/bin/env python3
import sys, time, signal, os

def signal_handler(sig, frame):
    print("\\n⏹️ Pomodoro timer stopped by user")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

log_file = os.path.expanduser("~/.alltool_pomodoro.log")

def log(msg):
    with open(log_file, "a") as f:
        f.write(msg + "\\n")

sessions = {sessions}
print(f"🍅 Starting Pomodoro Timer for {{sessions}} sessions")
print("=" * 50)
log(f"Started {{sessions}} sessions")

for session in range(1, sessions + 1):
    print(f"\\n📚 Session {{session}}/{{sessions}} - Work Time (25 minutes)")
    print("⏰ Starting work session...")
    log(f"Session {{session}} started")

    for minutes in range(25, 0, -1):
        for seconds in range(60, 0, -1):
            print(f"\\r⏳ {{minutes:02d}}:{{seconds:02d}} remaining", end="", flush=True)
            time.sleep(1)

    print(f"\\n✅ Session {{session}} completed!")
    log(f"Session {{session}} completed")

    if session < sessions:
        if session % 4 == 0:
            print(f"\\n☕ Long Break Time (15 minutes)")
            print("⏰ Starting long break...")
            log(f"Long break started")
            for minutes in range(15, 0, -1):
                for seconds in range(60, 0, -1):
                    print(f"\\r⏳ {{minutes:02d}}:{{seconds:02d}} remaining", end="", flush=True)
                    time.sleep(1)
            print(f"\\n✅ Long break completed!")
            log(f"Long break completed")
        else:
            print(f"\\n☕ Short Break Time (5 minutes)")
            print("⏰ Starting short break...")
            log(f"Short break started")
            for minutes in range(5, 0, -1):
                for seconds in range(60, 0, -1):
                    print(f"\\r⏳ {{minutes:02d}}:{{seconds:02d}} remaining", end="", flush=True)
                    time.sleep(1)
            print(f"\\n✅ Short break completed!")
            log(f"Short break completed")

print(f"\\n🎉 All {{sessions}} Pomodoro sessions completed!")
print("🏆 Great job! You've finished your work session.")
log("All sessions completed")
"""
        script_path = _timer_path()
        with open(script_path, "w") as f:
            f.write(pomodoro_script)
        subprocess.run(["chmod", "+x", script_path], timeout=10)

        # Append to log (don't truncate history) and track PID for reliable stop.
        log_handle = open(log_file, "a")
        try:
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
            )
        except Exception:
            log_handle.close()
            raise
        # Popen keeps its own dup; we can close ours.
        log_handle.close()
        try:
            with open(_pid_file(), "w") as f:
                f.write(str(process.pid))
        except OSError:
            pass

        tool.print_success("Pomodoro timer started in background")
        print(f"📄 Progress logged to {log_file}")
        print("💡 Use 'alltool pr stop' to stop the timer")
        print("💡 Use 'tail -f ~/.alltool_pomodoro.log' to watch progress")

    except ValueError:
        tool.print_error("Sessions must be a number")
        return 1
    except Exception as e:
        tool.print_error(f"Error starting Pomodoro timer: {e}")
        return 1

    return 0