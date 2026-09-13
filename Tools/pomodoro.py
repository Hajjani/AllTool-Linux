from .base import command, ToolBase
import os
import subprocess
import sys

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
        result = subprocess.run(["pgrep", "-f", "pomodoro_timer"], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    subprocess.run(["kill", pid])
            tool.print_success("Pomodoro timer stopped")
        else:
            tool.print_status("No Pomodoro timer running")
        return 0

    elif args[0] == "st":
        result = subprocess.run(["pgrep", "-f", "pomodoro_timer"], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
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
        script_path = "/tmp/pomodoro_timer.py"
        with open(script_path, "w") as f:
            f.write(pomodoro_script)
        subprocess.run(["chmod", "+x", script_path])

        with open(log_file, "w") as log:
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=log,
                stderr=log,
                preexec_fn=os.setsid,
            )

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