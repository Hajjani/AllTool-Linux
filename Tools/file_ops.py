from .base import command, ToolBase
import os
import subprocess

@command("create", help_text="Create a file, auto-create folders if needed")
def create(args: list):
    if not args:
        print("Usage: alltool create <filename>")
        return 1
    filepath = os.path.expanduser(args[0])
    folder = os.path.dirname(filepath)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    subprocess.run(["touch", filepath])
    print(f"✅ Created: {filepath}")
    return 0

@command("format", aliases=["fmt"], help_text="Format disk (types: ntfs, ext4, vfat)")
def format_disk(args: list):
    if len(args) < 2:
        print("Usage: alltool format <disk> <type>")
        print("Supported types: ntfs, ext4, vfat")
        return 1

    disk = args[0]
    fs_type = args[1].lower()
    formatters = {"ntfs": "mkfs.ntfs", "ext4": "mkfs.ext4", "vfat": "mkfs.vfat"}

    if fs_type not in formatters:
        print(f"❌ Unsupported format type: {fs_type}")
        print(f"Supported types: {', '.join(formatters.keys())}")
        return 1

    tool = ToolBase()
    print(f"⚠️ Warning: Make sure '{disk}' is a valid device like /dev/sdb1")
    if not tool.confirm(f"Are you sure you want to format {disk} as {fs_type}? This will erase all data!"):
        print("Aborted.")
        return 0

    print(f"Formatting {disk} as {fs_type}...")
    try:
        subprocess.run(["sudo", formatters[fs_type], disk], check=True)
        tool.print_success(f"Formatted {disk} as {fs_type}")
    except subprocess.CalledProcessError as e:
        tool.print_error(f"Format failed: {e}")
        return 1
    return 0