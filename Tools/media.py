from .base import command, ToolBase
import os
import subprocess

def _check_mpv(tool):
    if not tool.has_command("mpv"):
        tool.print_error("mpv is not installed.")
        print("   Install with: sudo apt install mpv  (Debian/Ubuntu)")
        print("               sudo pacman -S mpv  (Arch)")
        print("               sudo dnf install mpv  (Fedora)")
        return False
    return True

def _check_ffplay(tool):
    if not tool.has_command("ffplay"):
        tool.print_error("ffplay (from ffmpeg) is not installed.")
        print("   Install with: sudo apt install ffmpeg  (Debian/Ubuntu)")
        print("               sudo pacman -S ffmpeg  (Arch)")
        print("               sudo dnf install ffmpeg  (Fedora)")
        return False
    return True

@command("sound", help_text="Play audio file or playlist (wav, mp3, ogg, flac, aac, m4a)")
def sound(args: list):
    tool = ToolBase()
    if not _check_mpv(tool):
        return 1

    if not args:
        print("Usage: alltool sound <path_to_audio_file_or_playlist.txt>")
        return 1

    input_path = os.path.expanduser(args[0])
    if not os.path.exists(input_path):
        print(f"❌ Error: File '{input_path}' does not exist.")
        return 1

    supported_formats = [".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"]

    if input_path.lower().endswith(".txt"):
        print(f"📃 Playing playlist: {input_path}")
        with open(input_path, "r") as f:
            for line in f:
                audio_file = os.path.expanduser(line.strip())
                if not os.path.exists(audio_file):
                    print(f"⚠️ Skipping missing file: {audio_file}")
                    continue
                if not any(audio_file.lower().endswith(ext) for ext in supported_formats):
                    print(f"⚠️ Skipping unsupported format: {audio_file}")
                    continue
                print(f"🔊 Playing: {audio_file}")
                subprocess.run(["mpv", "--really-quiet", audio_file])
    else:
        if not any(input_path.lower().endswith(ext) for ext in supported_formats):
            print("❌ Error: Unsupported file format. Supported: wav, mp3, ogg, flac, aac, m4a")
            return 1
        print(f"🔊 Playing sound: {input_path}")
        subprocess.run(["mpv", "--really-quiet", input_path])
    return 0

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