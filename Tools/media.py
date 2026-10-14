from .base import command, ToolBase
from .deps import ensure_command
import json
import os
import socket
import subprocess
import time
from pathlib import Path

SUPPORTED_AUDIO = (".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a")

# Transport subcommands: alltool sound <st|pl|rp>
_TRANSPORT = ("st", "pl", "rp")


def _sock_path(tool) -> Path:
    try:
        base = Path(tool.home_dir) / "cache"
    except Exception:
        base = Path.home() / ".config" / "alltool" / "cache"
    return base / "mpv.sock"


def _ipc_send(sock_path: Path, command, timeout: float = 5):
    """Send one mpv IPC command, return the response dict (None on failure)."""
    try:
        payload = (json.dumps({"command": command}) + "\n").encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(str(sock_path))
            s.sendall(payload)
            buf = b""
            # mpv answers every command with exactly one {"error": ...} line.
            while b"\n" not in buf or b'"error"' not in buf:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 65536:
                    break
        for line in buf.decode(errors="replace").splitlines():
            try:
                resp = json.loads(line)
            except ValueError:
                continue
            if isinstance(resp, dict) and "error" in resp:
                return resp
    except (OSError, socket.timeout):
        pass
    return None


def _daemon_alive(tool) -> bool:
    return _ipc_send(_sock_path(tool), ["get_property", "mpv-version"]) is not None


def _ensure_daemon(tool) -> bool:
    """Start the background mpv player (mpv --idle + IPC) when needed."""
    sock = _sock_path(tool)
    if _daemon_alive(tool):
        return True
    try:
        sock.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    try:
        if sock.exists():
            sock.unlink()  # stale socket from a dead player
    except OSError:
        pass
    try:
        subprocess.Popen(
            ["mpv", "--idle=yes", "--force-window=no", "--no-video",
             f"--input-ipc-server={sock}", "--really-quiet"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    deadline = time.time() + 5
    while time.time() < deadline:
        if _daemon_alive(tool):
            return True
        time.sleep(0.1)
    return False


def _play_files(tool, files) -> int:
    if not _ensure_daemon(tool):
        tool.print_error("Could not start the background player.")
        return 1
    queued = 0
    for i, audio_file in enumerate(files):
        resp = _ipc_send(_sock_path(tool),
                         ["loadfile", audio_file, "replace" if i == 0 else "append-play"])
        if resp is None or resp.get("error") != "success":
            print(f"⚠️ Skipping (player rejected it): {audio_file}")
            continue
        queued += 1
        if i == 0:
            print(f"🔊 Playing: {audio_file}")
        else:
            print(f"➕ Queued: {audio_file}")
    return 0 if queued else 1


def _sound_stop(tool) -> int:
    # NOTE: mpv's `stop` clears the playlist, which would make `pl` unable
    # to resume. Pausing keeps the song + position so `pl` resumes it.
    if not _daemon_alive(tool):
        print("ℹ️ Nothing is playing (player is not running).")
        return 0
    resp = _ipc_send(_sock_path(tool), ["set_property", "pause", True])
    if resp is None or resp.get("error") != "success":
        tool.print_error("Could not stop playback.")
        return 1
    print("⏹️ Stopped. Resume with: alltool sound pl")
    return 0


def _sound_play(tool) -> int:
    """Resume paused playback, or restart the stopped entry."""
    if not _daemon_alive(tool):
        print("ℹ️ Nothing to play — pass an audio file first: alltool sound <file>")
        return 0
    sock = _sock_path(tool)
    paused = _ipc_send(sock, ["get_property", "pause"])
    if paused and paused.get("data") is True:
        resp = _ipc_send(sock, ["set_property", "pause", False])
        if resp and resp.get("error") == "success":
            print("▶️ Resumed.")
            return 0
        tool.print_error("Could not resume playback.")
        return 1
    idle = _ipc_send(sock, ["get_property", "idle-active"])
    count = _ipc_send(sock, ["get_property", "playlist-count"])
    try:
        n = int(count.get("data", 0)) if count else 0
    except (TypeError, ValueError):
        n = 0
    if idle and idle.get("data") is True and n > 0:
        resp = _ipc_send(sock, ["playlist-play-index", "current"])
        if resp and resp.get("error") == "success":
            print("▶️ Playing.")
            return 0
        tool.print_error("Could not start playback.")
        return 1
    if idle and idle.get("data") is True:
        print("ℹ️ Nothing to play — pass an audio file first: alltool sound <file>")
        return 0
    print("▶️ Already playing.")
    return 0


def _sound_repeat(tool, mode: str) -> int:
    if not _daemon_alive(tool):
        print("ℹ️ Nothing is playing (player is not running).")
        return 0
    sock = _sock_path(tool)
    if mode in ("on", "off"):
        want = "inf" if mode == "on" else "no"
        resp = _ipc_send(sock, ["set_property", "loop-file", want])
        if not resp or resp.get("error") != "success":
            tool.print_error("Could not change repeat mode.")
            return 1
    elif mode:
        tool.print_error(f"Unknown repeat mode '{mode}'. Use: alltool sound rp [on|off]")
        return 1
    else:
        resp = _ipc_send(sock, ["cycle-values", "loop-file", "inf", "no"])
        if not resp or resp.get("error") != "success":
            tool.print_error("Could not toggle repeat.")
            return 1
    state = _ipc_send(sock, ["get_property", "loop-file"])
    looping = bool(state and state.get("data") not in (None, "no", "0", 0, False))
    print(f"🔁 Repeat {'on' if looping else 'off'}.")
    return 0


def _sound_volume(tool, spec: str) -> int:
    """Set player volume natively: `alltool sound 23%`."""
    try:
        level = int(spec[:-1])
    except (TypeError, ValueError):
        level = -1
    if level < 0 or level > 150:
        tool.print_error(f"Invalid volume '{spec}'. Use 0%..100% (up to 150% boost).")
        return 1
    # Volume lives on the same background player, so it applies to the
    # current song and persists for the next ones.
    if not _ensure_daemon(tool):
        tool.print_error("Could not start the background player.")
        return 1
    sock = _sock_path(tool)
    resp = _ipc_send(sock, ["set_property", "volume", level])
    if resp is None or resp.get("error") != "success":
        tool.print_error("Could not set volume.")
        return 1
    state = _ipc_send(sock, ["get_property", "volume"])
    try:
        actual = int(float(state.get("data"))) if state else level
    except (TypeError, ValueError):
        actual = level
    print(f"🔉 Volume: {actual}%.")
    return 0


def _collect_files(tool, input_path: str):
    """Expand a file or .txt playlist into a list of playable paths."""
    files = []

    def _ok(p: str) -> bool:
        if not any(p.lower().endswith(ext) for ext in SUPPORTED_AUDIO):
            print(f"⚠️ Skipping unsupported format: {p}")
            return False
        return True

    if input_path.lower().endswith(".txt"):
        print(f"📃 Playing playlist: {input_path}")
        try:
            with open(input_path, "r") as f:
                lines = f.readlines()
        except OSError as e:
            print(f"❌ Error: Cannot read playlist: {e}")
            return []
        for line in lines:
            audio_file = os.path.expanduser(line.strip())
            if not audio_file:
                continue
            if not os.path.exists(audio_file):
                print(f"⚠️ Skipping missing file: {audio_file}")
                continue
            if _ok(audio_file):
                files.append(audio_file)
    else:
        if _ok(input_path):
            files.append(input_path)
    return files


@command("sound", help_text="Play audio and control playback: st (stop), pl (play/resume), rp [on|off] (repeat), N% (volume)")
def sound(args: list):
    tool = ToolBase()
    if not ensure_command(tool, "mpv", "sound command"):
        return 1

    if not args:
        print("Usage:")
        print("  alltool sound <audio_file|playlist.txt>  Play now (wav, mp3, ogg, flac, aac, m4a)")
        print("  alltool sound st                         Stop the current song")
        print("  alltool sound pl                         Play / resume the current song")
        print("  alltool sound rp [on|off]                Repeat the current song (toggle by default)")
        print("  alltool sound <N%>                       Set volume, e.g. alltool sound 23%")
        return 1

    first = os.path.expanduser(args[0])
    # An existing file always wins over a subcommand name (e.g. a file named "st").
    if os.path.exists(first) and os.path.isfile(first):
        files = _collect_files(tool, first)
        if not files:
            print("❌ Error: Nothing playable found.")
            return 1
        return _play_files(tool, files)

    sub = args[0].lower()
    if sub == "st":
        return _sound_stop(tool)
    if sub == "pl":
        return _sound_play(tool)
    if sub == "rp":
        return _sound_repeat(tool, args[1].lower() if len(args) > 1 else "")
    if len(sub) > 1 and sub.endswith("%") and sub[:-1].isdigit():
        return _sound_volume(tool, sub)

    if not os.path.exists(first):
        print(f"❌ Error: File '{first}' does not exist.")
        return 1
    print("❌ Error: Unsupported file format. Supported: wav, mp3, ogg, flac, aac, m4a")
    return 1


def _check_ffplay(tool):
    return ensure_command(tool, "ffplay", "video command")


@command("video", help_text="Play video files with ffplay")
def video(args: list):
    tool = ToolBase()
    if not _check_ffplay(tool):
        return 1

    if not args:
        print("Usage: alltool video <path_to_video>")
        return 1

    video_path = os.path.expanduser(args[0])
    if not os.path.exists(video_path):
        print(f"❌ Error: File '{video_path}' does not exist.")
        return 1

    print(f"🎬 Playing video: {video_path}")
    subprocess.run(["ffplay", "-autoexit", video_path])
    return 0
