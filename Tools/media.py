from .base import command, ToolBase
import os
import subprocess

@command("sound", help_text="Play audio file or playlist (wav, mp3, ogg, flac, aac, m4a)")
def sound(args: list):
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

@command("downloadvs", aliases=["dl"], help_text="Download video/audio from supported websites")
def downloadvs(args: list):
    if not args:
        print("Usage: alltool downloadvs <video_or_audio_url>")
        return 1

    tool = ToolBase()
    if not tool.has_command("yt-dlp"):
        tool.print_error("yt-dlp is not installed. Please install it.")
        return 1

    url = args[0]
    print(f"⬇️ Downloading from: {url}")
    subprocess.run(["yt-dlp", url])
    return 0