#!/usr/bin/env python3
import cmd
import sys
import subprocess
import os
import subprocess
import random
import string
import hashlib
import time
import requests, re
import json
import signal
from packaging import version
from Tools.uninstaller import uninstall
LOCAL_PATH = "~/bin/AllTool.py"


def uncon():
    confirm = input(
        "Are you sure you want to uninstall AllTool? This action cannot be undone. (yes/no):"
    )
    if confirm.lower() == "yes" or confirm.lower() == "y" or confirm.lower() == "":
        uninstall(LOCAL_PATH)
    elif confirm.lower() == "no" or confirm.lower() == "n":
        sun()
    else:
        con()


def con():
    print("❌ Invalid input. Please enter 'yes' or 'no'.")
    confirm = input(
        "Are you sure you want to uninstall AllTool? This action cannot be undone. (yes/no):"
    )
    if confirm.lower() == "yes" or confirm.lower() == "y" or confirm.lower() == "":
        uninstall(LOCAL_PATH)
    elif confirm.lower() == "no" or confirm.lower() == "n":
        sun()
    else:
        con()


def sun():
    print("Uninstalling AllTool cancelled")


def get_output(cmd):
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def has_command(cmd):
    return (
        subprocess.run(
            ["which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        == 0
    )


def check_updates():
    if has_command("apt"):
        print("🔍 Checking for updates (APT)...")
        subprocess.run(["sudo", "apt", "update"], stdout=subprocess.DEVNULL)
        output = get_output(["apt", "list", "--upgradable"])
        lines = [line for line in output.splitlines() if "/" in line]
        if lines:
            print(f"⚠️ {len(lines)} updates not installed.")
        else:
            print("✅ No updates available.")

    elif has_command("checkupdates"):
        print("🔍 Checking for updates (Pacman)...")
        output = get_output(["checkupdates"])
        lines = [line for line in output.splitlines() if line.strip()]
        if lines:
            print(f"⚠️ {len(lines)} updates not installed.")
        else:
            print("✅ No updates available.")

    elif has_command("dnf"):
        print("🔍 Checking for updates (DNF)...")
        output = get_output(["dnf", "check-update"])
        lines = [
            line
            for line in output.splitlines()
            if line and not line.startswith("Last metadata")
        ]
        if lines:
            print(f"⚠️ {len(lines)} updates not installed.")
        else:
            print("✅ No updates available.")

    elif has_command("zypper"):
        print("🔍 Checking for updates (Zypper)...")
        output = get_output(["zypper", "list-updates"])
        lines = [
            line
            for line in output.splitlines()
            if line.startswith("v ") or line.startswith("i ")
        ]
        if lines:
            print(f"⚠️ {len(lines)} updates not installed.")
        else:
            print("✅ No updates available.")

    else:
        print("❌ No supported package manager found.")


def detect_and_run(script_path):
    if not os.path.isfile(script_path):
        print(f"❌ File not found: {script_path}")
        return

    _, ext = os.path.splitext(script_path)

    # Extension-based detection
    if ext == ".py":
        print("🚀 Running Python script...")
        subprocess.run(["python", script_path])
    elif ext == ".sh":
        print("🚀 Running Shell script...")
        subprocess.run(["bash", script_path])
    elif ext == ".js":
        print("🚀 Running JavaScript script...")
        subprocess.run(["node", script_path])
    elif ext == ".pl":
        print("🚀 Running Perl script...")
        subprocess.run(["perl", script_path])
    elif ext == ".rb":
        print("🚀 Running Ruby script...")
        subprocess.run(["ruby", script_path])
    elif ext == ".php":
        print("🚀 Running PHP script...")
        subprocess.run(["php", script_path])
    elif ext == ".jar":
        print("🚀 Running Java JAR...")
        subprocess.run(["java", "-jar", script_path])
    elif ext == ".cpp" or ext == ".cc" or ext == ".c":
        print("🚀 Compiling and running C/C++ code...")
        output_exe = "/tmp/temp_executable"
        subprocess.run(["g++", script_path, "-o", output_exe])
        subprocess.run([output_exe])
    else:
        # Fallback: check shebang
        with open(script_path, "r") as f:
            first_line = f.readline().strip()
        if first_line.startswith("#!"):
            print(f"🚀 Running via shebang: {first_line}")
            subprocess.run([script_path])
        else:
            print("❌ Unknown script type. Please specify manually.")


def main():
    if len(sys.argv) < 2:
        print("Usage: alltool <command> [args]")
        print(
            "Available commands: create, format, refresh, help, netspeed, sound, video, downloadvs, requirement, power, sf, sif, up, run, psg, hs, sr, wea, pr"
        )
        return

    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) < 3:
            print("Usage: alltool create <filename>")
            return
        filepath = sys.argv[2]
        folder = os.path.dirname(filepath)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        subprocess.run(["touch", filepath])

    elif command == "format":
        if len(sys.argv) < 4:
            print("Usage: alltool format <disk> <type>")
            return
        disk = sys.argv[2]
        fs_type = sys.argv[3].lower()

        formatters = {"ntfs": "mkfs.ntfs", "ext4": "mkfs.ext4", "vfat": "mkfs.vfat"}

        if fs_type not in formatters:
            print(f"Unsupported format type: {fs_type}")
            print(f"Supported types: {', '.join(formatters.keys())}")
            return

        print(f"⚠️ Warning: Make sure '{disk}' is a valid device like /dev/sdb1")
        confirm = input(
            f"Are you sure you want to format {disk} as {fs_type}? This will erase all data! (yes/no): "
        )
        if confirm.lower() != "yes":
            print("Aborted.")
            return

        print(f"Formatting {disk} as {fs_type}...")
        subprocess.run(["sudo", formatters[fs_type], disk])
    elif command == "refresh":
        print("🔄 Refreshing alltool setup...")

        # Make script executable
        script_path = os.path.expanduser("~/bin/AllTools.py")
        subprocess.run(["chmod", "+x", script_path])

        # Detect shell config file
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            config_file = os.path.expanduser("~/.zshrc")
        elif "bash" in shell:
            config_file = os.path.expanduser("~/.bashrc")
        else:
            config_file = os.path.expanduser("~/.profile")

        # Check if PATH is already set
        path_line = 'export PATH="$HOME/bin:$PATH"'
        already_set = False
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                for line in f:
                    if path_line in line:
                        already_set = True
                        break

        # Append if missing
        if not already_set:
            with open(config_file, "a") as f:
                f.write(f"\n# Added by alltool\n{path_line}\n")
            print(f"✅ PATH updated in {config_file}")
        else:
            print(f"ℹ️ PATH already set in {config_file}")

        print("Please run: source ~/.zshrc or restart your terminal to apply changes.")
        print("Refresh complete.")

    elif command == "help":
        lang = sys.argv[2] if len(sys.argv) > 2 else "en"

        help_texts = {
            "en": """
Usage: alltool <command> [args]
Available commands:
  create <filename>         Create a file, auto-create folders if needed
  format <disk> <type>     Format disk (types: ntfs, ext4, vfat)
  refresh                  Refresh permissions and show PATH setup
  help [lang]             Show help in en, fr, ar, de
  sound <file|playlist.txt> Play audio file or playlist (wav, mp3, ogg, flac, aac, m4a)
  netspeed                Test internet connection speed
  video <path>           Play video files
  downloadvs <url>       Download video or audio from supported websites
  power                  Manage power profiles and system control
    - pws: power-saver mode    - pwn: balanced mode      - pwp: performance mode
    - pwst: power status       - pwo: shutdown           - pwr: reboot
    - pwl: logout             - pwsu: suspend           - pwh: hibernate
    - pwlo: lock screen
  requirement            Check if alltool dependencies are installed
  sf                    Show files in current directory
  sif                   Show detailed system information
  up                    Check for system updates
  run <script>          Auto-detect and run scripts (py, sh, js, pl, rb, php, jar, cpp)
  psg <length> [options] Generate secure password
    Options: nose (no lowercase), nos (no uppercase), not (no digits), nol (no special)
  hs <file> <type>      Calculate file hash (md5, sha1, sha256, sha512, blake2b, blake2s)
  sr <topic>            Search the web for information using AI
  wea <city>            Get weather information for a city
  pr                   Manage poromodor sessions
   - needed sessions
   - stop : Stop running Pomodoro timer
   - st : Show Pomodoro timer status and recent activity
  upa                  Updating AllTool
   - st : update to the latest stable version of AllTool
   - pv : update to the latest preview version of AllTool
  cl                    Clear terminal
""",
            "fr": """
Utilisation : alltool <commande> [arguments]
Commandes disponibles :
  create <fichier>        Crée un fichier, crée les dossiers si nécessaire
  format <disque> <type>  Formate le disque (types : ntfs, ext4, vfat)
  refresh                 Actualise les permissions et affiche le PATH
  help [langue]          Affiche l'aide en en, fr, ar, de
  sound <fichier|playlist.txt> Joue un fichier audio ou une playlist
  netspeed               Test de vitesse internet
  video <chemin>         Lecture de fichiers vidéo
  downloadvs <url>       Télécharge une vidéo ou un audio via yt-dlp
  power                  Gestion de l'alimentation et contrôle système
    - pws: mode économie      - pwn: mode équilibré     - pwp: mode performance
    - pwst: état              - pwo: arrêt              - pwr: redémarrage
    - pwl: déconnexion       - pwsu: mise en veille    - pwh: hibernation
    - pwlo: verrouillage
  requirement            Vérifie les dépendances installées
  sf                    Affiche les fichiers du répertoire
  sif                   Affiche les informations système détaillées
  up                    Vérifie les mises à jour système
  run <script>          Détecte et exécute les scripts automatiquement
  psg <longueur> [options] Génère un mot de passe sécurisé
    Options: nose (pas de min.), nos (pas de maj.), not (pas de chiffres), nol (pas de spéciaux)
  hs <fichier> <type>    Calcule le hash d'un fichier
  sr <sujet>            Recherche des informations sur le web en utilisent AI
  wea <ville>           Obtient les informations météo pour une ville
  pr
   - Sessions nécessaires
   - stop : Arrêter le minuteur Pomodoro en cours
   - st : Afficher le statut du minuteur Pomodoro et l'activité récente
  upa
   - st : mise à jour AllTool au dernier stable version
   - pv : mise à jour AllTool au dernier version preview
  cl                     effacer le terminal
""",
            "ar": """
الاستخدام: alltool <الأمر> [المعطيات]
الأوامر المتاحة:
  create <اسم الملف>        إنشاء ملف، وإنشاء المجلدات تلقائيًا إذا لزم الأمر
  format <القرص> <النوع>     تهيئة القرص (الأنواع: ntfs، ext4، vfat)
  refresh                    تحديث الصلاحيات وعرض إعداد PATH
  help [اللغة]               عرض المساعدة باللغات: en، fr، ar، de
  sound <ملف|playlist.txt>     تشغيل ملف صوتي أو قائمة تشغيل
  netspeed                   اختبار سرعة الإنترنت
  video <المسار>             تشغيل ملفات الفيديو
  downloadvs <الرابط>        تحميل فيديو أو صوت من المواقع المدعومة
  power                     إدارة الطاقة والتحكم بالنظام
    - pws: وضع توفير الطاقة    - pwn: وضع متوازن    - pwp: وضع الأداء
    - pwst: حالة الطاقة        - pwo: إيقاف         - pwr: إعادة تشغيل
    - pwl: تسجيل خروج         - pwsu: تعليق        - pwh: سبات
    - pwlo: قفل الشاشة
  requirement               التحقق من المتطلبات المثبتة
  sf                       عرض الملفات في المجلد الحالي
  sif                      عرض معلومات النظام المفصلة
  up                       التحقق من تحديثات النظام
  run <المسار>              تشغيل السكربتات تلقائيًا
  psg <الطول> [الخيارات]     توليد كلمة مرور آمنة
    الخيارات: nose (بدون صغيرة)، nos (بدون كبيرة)، not (بدون أرقام)، nol (بدون رموز)
  hs <الملف> <النوع>         حساب التجزئة للملف
  sr <الموضوع>            البحث في الويب عن معلومات باستخدام AI
  wea <المدينة>             الحصول على معلومات الطقس للمدينة
  pr
   - عدد الجلسات المرغوب بها
   - stop : إيقاف مؤقت بومودورو قيد التشغيل
   - st : عرض حالة مؤقت بومودورو والنشاط الأخير
  upa         تحديث AllTool
    - st : تحديث AllTool إلى أحدث إصدار مستقر
    - pv : تحديث AllTool إلى أحدث إصدار تجريبي
  cl                مسح الطرفية
""",
            "de": """
Verwendung: alltool <Befehl> [Argumente]
Verfügbare Befehle:
  create <Dateiname>        Datei erstellen, Ordner bei Bedarf automatisch
  format <Datenträger> <Typ> Datenträger formatieren (Typen: ntfs, ext4, vfat)
  refresh                   Berechtigungen aktualisieren und PATH anzeigen
  help [Sprache]           Hilfe anzeigen in en, fr, ar, de
  sound <Datei|playlist.txt> Audio oder Playlist abspielen
  netspeed                 Internet-Geschwindigkeit testen
  video <Pfad>            Videodateien abspielen
  downloadvs <URL>         Video oder Audio herunterladen
  power                    Energieverwaltung und Systemsteuerung
    - pws: Energiesparmodus    - pwn: Ausgewogen    - pwp: Leistung
    - pwst: Energiestatus      - pwo: Herunterfahren - pwr: Neustart
    - pwl: Abmelden           - pwsu: Bereitschaft  - pwh: Ruhezustand
    - pwlo: Bildschirm sperren
  requirement              Überprüft installierte Abhängigkeiten
  sf                      Zeigt Dateien im aktuellen Verzeichnis
  sif                     Zeigt detaillierte Systeminformationen
  up                      Prüft auf Systemaktualisierungen
  run <Pfad>              Führt Skripte automatisch aus
  psg <Länge> [Optionen]  Generiert sicheres Passwort
    Optionen: nose (keine Kleinbuchstaben), nos (keine Großbuchstaben),
    not (keine Zahlen), nol (keine Sonderzeichen)
  hs <Datei> <Typ>        Berechnet Dateihash
  sr <Thema>              Suche nach Informationen im Web unter Verwendung von KI
  wea <Stadt>             Holt Wetterinformationen für eine Stadt
  pr
   - Anzahl der Pomodoro-Sitzungen
   - stop : Laufenden Pomodoro-Timer stoppen
   - st : Pomodoro-Timer Status und letzte Aktivität anzeigen
  upa
   - st : Aktualisiere AllTool auf die neueste stabile Version
   - pv : Aktualisiere AllTool auf die neueste Vorschauversion
  cl                     Terminal löschen
""",
        }

        print(help_texts.get(lang, help_texts["en"]))
    elif command == "sound":
        if len(sys.argv) < 3:
            print("Usage: alltool sound <path_to_audio_file_or_playlist.txt>")
            return
        input_path = os.path.expanduser(sys.argv[2])

        if not os.path.exists(input_path):
            print(f"❌ Error: File '{input_path}' does not exist.")
            return

        supported_formats = [".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"]

        # Check if it's a playlist
        if input_path.lower().endswith(".txt"):
            print(f"📃 Playing playlist: {input_path}")
            with open(input_path, "r") as f:
                for line in f:
                    audio_file = os.path.expanduser(line.strip())
                    if not os.path.exists(audio_file):
                        print(f"⚠️ Skipping missing file: {audio_file}")
                        continue
                    if not any(
                        audio_file.lower().endswith(ext) for ext in supported_formats
                    ):
                        print(f"⚠️ Skipping unsupported format: {audio_file}")
                        continue
                    print(f"🔊 Playing: {audio_file}")
                    subprocess.run(["mpv", "--really-quiet", audio_file])
        else:
            if not any(input_path.lower().endswith(ext) for ext in supported_formats):
                print(
                    "❌ Error: Unsupported file format. Supported formats: wav, mp3, ogg, flac, aac, m4a"
                )
                return
            print(f"🔊 Playing sound: {input_path}")
            subprocess.run(["mpv", "--really-quiet", input_path])
    elif command == "netspeed":
        print("Measuring network speed...")
        subprocess.run(["speedtest-cli"])
    elif command == "requirement":
        print("🔍 Checking system requirements for alltool...")

        requirements = {
            # Audio/Video tools
            "mpv": "Sound playback (multi-format)",
            "ffmpeg": "Video processing and conversion",
            "ffplay": "Video playback",
            # Network tools
            "speedtest-cli": "Network speed test",
            "yt-dlp": "Download videos and audio from websites",
            "requests": "Python web requests library",
            "beautifulsoup4": "HTML parsing for web search",
            # Disk tools
            "mkfs.ntfs": "Format NTFS disks",
            "mkfs.ext4": "Format EXT4 disks",
            "mkfs.vfat": "Format VFAT disks",
            # System tools
            "touch": "Create files",
            "powerprofilesctl": "Power profile management",
            "systemctl": "System control operations",
            "xdg-screensaver": "Screen locking capability",
            "inxi": "System information display",
            "pkill": "Process management for logout functionality",
            # Programming languages
            "python3": "Python runtime (required)",
            "node": "JavaScript runtime",
            "perl": "Perl runtime",
            "ruby": "Ruby runtime",
            "php": "PHP runtime",
            "java": "Java runtime",
            "g++": "C/C++ compiler",
            # Package managers (for update checking)
            "apt": "Debian/Ubuntu package manager",
            "pacman": "Arch Linux package manager",
            "dnf": "Fedora package manager",
            "zypper": "openSUSE package manager",
            "checkupdates": "Arch Linux update checker",
            # Python standard library modules (built-in)
            "cmd": "Command line interface framework",
            "subprocess": "Process execution",
            "os": "Operating system interface",
            "random": "Random number generation",
            "string": "String manipulation",
            "hashlib": "Hash functions (md5, sha1, sha256, sha512, blake2b, blake2s)",
            "time": "Time-related functions",
            "json": "JSON data handling",
        }

        missing_count = 0
        python_packages = ["requests", "beautifulsoup4"]
        builtin_modules = [
            "cmd",
            "subprocess",
            "os",
            "random",
            "string",
            "hashlib",
            "time",
            "json",
        ]

        for tool, desc in requirements.items():
            if tool in python_packages:
                try:
                    __import__(tool.split("4")[0])
                    status = "✅ Installed"
                except ImportError:
                    status = "❌ Missing"
                    missing_count += 1
            elif tool in builtin_modules:
                try:
                    __import__(tool)
                    status = "✅ Built-in"
                except ImportError:
                    status = "❌ Missing"
                    missing_count += 1
            else:
                result = subprocess.run(["which", tool], stdout=subprocess.DEVNULL)
                status = "✅ Installed" if result.returncode == 0 else "❌ Missing"
                if result.returncode != 0:
                    missing_count += 1

            print(f"{tool:<16} {status} — {desc}")

        if missing_count > 0:
            print(
                f"\n⚠️ {missing_count} requirements are missing. Install them for full functionality."
            )
            print("💡 Installation commands:")
            print("   For Python packages: pip install requests beautifulsoup4")
            print(
                "   For Arch Linux: sudo pacman -S mpv ffmpeg speedtest-cli yt-dlp inxi"
            )
            print(
                "   For Ubuntu/Debian: sudo apt install mpv ffmpeg speedtest-cli yt-dlp inxi"
            )
            print(
                "   For Fedora: sudo dnf install mpv ffmpeg speedtest-cli yt-dlp inxi"
            )
            print(
                "   For openSUSE: sudo zypper install mpv ffmpeg speedtest-cli yt-dlp inxi"
            )
            print(
                "   For power management: sudo apt install power-profiles-daemon (Ubuntu) or sudo pacman -S power-profiles-daemon (Arch)"
            )
        else:
            print("\n✅ All requirements are installed!")
    elif command == "video":
        if len(sys.argv) < 3:
            print("Usage: alltool video <path_to_video>")
            return
        video_path = os.path.expanduser(sys.argv[2])
        if not os.path.exists(video_path):
            print(f"❌ Error: File '{video_path}' does not exist.")
            return
        print(f"🎬 Playing video: {video_path}")
        subprocess.run(["ffplay", "-autoexit", video_path])
    elif command == "downloadvs":
        if len(sys.argv) < 3:
            print("Usage: alltool downloadvs <video_or_audio_url>")
            return
        url = sys.argv[2]

        # Check if yt-dlp is installed
        result = subprocess.run(["which", "yt-dlp"], stdout=subprocess.DEVNULL)
        if result.returncode != 0:
            print(
                "❌ yt-dlp is not installed. Please install it with: sudo pacman -S yt-dlp"
            )
            return

        print(f"⬇️ Downloading from: {url}")
        subprocess.run(["yt-dlp", url])
    elif command == "power":
        if len(sys.argv) < 3:
            print(
                "Usage: alltool power [pws | pwn | pwp | pwst | pwo | pwr | pwl | pwsu | pwh | pwlo]"
            )
            return

        subcommand = sys.argv[2]

        # Check if powerprofilesctl is available
        if (
            subprocess.run(
                ["which", "powerprofilesctl"], stdout=subprocess.DEVNULL
            ).returncode
            != 0
        ):
            print(
                "❌ Error: powerprofilesctl not found. Please install power-profiles-daemon."
            )
            return

        if subcommand == "pws":
            subprocess.run(["powerprofilesctl", "set", "power-saver"])
            print("✅ Power mode set to: power-saver")
        elif subcommand == "pwn":
            subprocess.run(["powerprofilesctl", "set", "balanced"])
            print("✅ Power mode set to: balanced")
        elif subcommand == "pwp":
            result = subprocess.run(
                ["powerprofilesctl", "list"], capture_output=True, text=True
            )
            if "performance" in result.stdout:
                subprocess.run(["powerprofilesctl", "set", "performance"])
                print("🚀 Power mode set to: performance")
            else:
                print("⚠️ Performance mode is not supported on this system.")
        elif subcommand == "pwst":
            result = subprocess.run(
                ["powerprofilesctl", "get"], capture_output=True, text=True
            )
            print(f"🔍 Current power mode: {result.stdout.strip()}")
        elif subcommand == "pwo":
            print("Shutting down the system...")
            subprocess.run(["sudo", "shutdown"])
        elif subcommand == "pwr":
            print("Rebooting the system...")
            subprocess.run(["sudo", "reboot"])
        elif subcommand == "pwl":
            print("Logging out...")
            subprocess.run(["pkill", "-KILL", "-u", os.getlogin()])
        elif subcommand == "pwsu":
            print("Suspending the system...")
            subprocess.run(["systemctl", "suspend"])
        elif subcommand == "pwh":
            print("Hibernating the system...")
            subprocess.run(["systemctl", "hibernate"])
        elif subcommand == "pwlo":
            print("Locking the screen...")
            subprocess.run(["xdg-screensaver", "lock"])
        else:
            print(
                "Usage: alltool power [pws | pwn | pwp | pwst | pwo | pwr | pwl | pwsu | pwh | pwlo]"
            )
    elif command == "sf":
        subprocess.run(["ls"])
    elif command == "sif":
        subprocess.run(["inxi", "-F"])
    elif command == "up":
        check_updates()
    elif command == "run":
        if len(sys.argv) < 3:
            print("Usage: alltool run <script_path>")
            return
        script_path = os.path.expanduser(sys.argv[2])
        detect_and_run(script_path)

    elif command == "psg":
        if len(sys.argv) < 3:
            print(
                "Usage: alltool psg <length> [nose: no lowercase] [nos: no uppercase] [not: no digits] [nol: no speciales]"
            )
            sys.exit(1)

        try:
            length = int(sys.argv[2])
        except ValueError:
            print("❌ Error: Length must be a number.")
            sys.exit(1)

        import string, random

        use_special = "nol" not in sys.argv
        use_digits = "not" not in sys.argv
        use_upper = "nos" not in sys.argv
        use_lower = "nose" not in sys.argv

        chars = ""
        if use_lower:
            chars += string.ascii_lowercase
        if use_upper:
            chars += string.ascii_uppercase
        if use_digits:
            chars += string.digits
        if use_special:
            chars += string.punctuation

        if not chars:
            print(
                "❌ Error: No character types selected. Use at least one character set."
            )
            sys.exit(1)

        password = "".join(random.choice(chars) for _ in range(length))
        print(f"✅ Generated password: {password}")
    elif command == "hs":
        if len(sys.argv) != 4:
            print(
                "❌ Usage: alltool hs <filename> <hash type: md5; sha1; sha256; sha512; blake2b; blake2s>"
            )
            return

        file_path = sys.argv[2]
        hash_type = sys.argv[3].lower()

        if not os.path.isfile(file_path):
            print(f"❌ File not found: {file_path}")
            return

        hash_map = {
            "md5": hashlib.md5,
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
            "blake2b": hashlib.blake2b,
            "blake2s": hashlib.blake2s,
        }

        if hash_type not in hash_map:
            print(f"❌ Unsupported hash type: {hash_type}")
            print("✅ Supported types: md5, sha1, sha256, sha512, blake2b, blake2s")
            return

        with open(file_path, "rb") as f:
            data = f.read()
            hash_obj = hash_map[hash_type]()
            hash_obj.update(data)
            print(
                f"🔐 {hash_type.upper()} hash of '{file_path}':\n{hash_obj.hexdigest()}"
            )
    elif command == "sr":
        if len(sys.argv) < 3:
            print("❌ Usage: alltool sr <search topic>")
            return
        topic = " ".join(sys.argv[2:]).strip()
        if not topic:
            print("❌ Empty search topic.")
            return

        print(f"🔍 Searching for: {topic}")

        try:
            # Using a different endpoint that's more reliable
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            # Using DuckDuckGo's HTML API
            url = f"https://html.duckduckgo.com/html/"
            params = {"q": topic, "kl": "us-en"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            if "No results found." in response.text:
                print("❌ No results found for your query.")
                return

            # Extract first few results
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("div", class_="result__body")

            if not results:
                print("❌ No results could be extracted.")
                return

            print("\n📚 Search Results:\n")
            for i, result in enumerate(results[:5], 1):
                title = result.find("a", class_="result__a")
                snippet = result.find("a", class_="result__snippet")

                if title and snippet:
                    print(f"{i}. {title.text.strip()}")
                    print(f"   {snippet.text.strip()}\n")

        except requests.RequestException as e:
            print(f"❌ Network error: {e}")
            print("💡 Try checking your internet connection or try again later.")
        except Exception as e:
            print(f"❌ Error: {e}")
            print("💡 Please try rephrasing your search query.")
    elif command == "wea":
        # Weather CLI
        if len(sys.argv) < 3:
            print("❌ Please provide a city name. Usage: alltool wea [city]")
            return
        city = " ".join(sys.argv[2:])
        print(f"🌦️  Getting weather for: {city}")
        try:
            url = f"https://wttr.in/{city}"
            params = {"format": "2"}
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                print(f"   {resp.text.strip()}")
            else:
                print(f"❌ Failed to get weather data for '{city}'.")
        except requests.RequestException as e:
            print(f"❌ Network error: {e}")
            print("💡 Try checking your internet connection or try again later.")
        except Exception as e:
            print(f"❌ Error: {e}")
            print("💡 Please try rephrasing your city or check for typos.")
    elif command == "pr":
        if len(sys.argv) < 3:
            print("Usage: alltool pr <number_of_sessions>")
            print("       alltool pr stop")
            print("       alltool pr st")
            return

        if sys.argv[2] == "stop":
            # Stop Pomodoro timer
            try:
                # Find and kill the Pomodoro process
                result = subprocess.run(
                    ["pgrep", "-f", "pomodoro_timer"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        if pid:
                            subprocess.run(["kill", pid])
                    print("✅ Pomodoro timer stopped")
                else:
                    print("ℹ️ No Pomodoro timer running")
            except Exception as e:
                print(f"❌ Error stopping timer: {e}")
            return

        elif sys.argv[2] == "st":
            # Show Pomodoro timer status
            try:
                # Check if Pomodoro process is running
                result = subprocess.run(
                    ["pgrep", "-f", "pomodoro_timer"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    pids = result.stdout.strip().split("\n")
                    print("🍅 Pomodoro timer is running")
                    print(f"📊 Process IDs: {', '.join([pid for pid in pids if pid])}")

                    # Show log file content if it exists
                    log_file = os.path.expanduser("~/.alltool_pomodoro.log")
                    if os.path.exists(log_file):
                        print(f"\n📄 Recent activity from {log_file}:")
                        print("-" * 50)
                        try:
                            with open(log_file, "r") as f:
                                lines = f.readlines()
                                # Show last 10 lines
                                for line in lines[-10:]:
                                    print(line.strip())
                        except Exception as e:
                            print(f"❌ Error reading log file: {e}")
                    else:
                        print("ℹ️ No log file found")
                else:
                    print("ℹ️ No Pomodoro timer running")
                    print("💡 Use 'alltool pr <sessions>' to start a timer")
            except Exception as e:
                print(f"❌ Error checking timer status: {e}")
            return

        try:
            sessions = int(sys.argv[2])
            if sessions <= 0:
                print("❌ Error: Sessions must be greater than 0")
                return

            # Create Pomodoro timer script
            pomodoro_script = f"""#!/usr/bin/env python3
def signal_handler(sig, frame):
    print("\\n⏹️ Pomodoro timer stopped by user")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

sessions = {sessions}
print(f"🍅 Starting Pomodoro Timer for {{sessions}} sessions")
print("=" * 50)

for session in range(1, sessions + 1):
    print(f"\\n📚 Session {{session}}/{{sessions}} - Work Time (25 minutes)")
    print("⏰ Starting work session...")

    # Work session countdown
    for minutes in range(25, 0, -1):
        for seconds in range(60, 0, -1):
            print(f"\\r⏳ {{minutes:02d}}:{{seconds:02d}} remaining", end="", flush=True)
            time.sleep(1)

    print(f"\\n✅ Session {{session}} completed!")

    # Break logic
    if session < sessions:
        if session % 4 == 0:
            print(f"\\n☕ Long Break Time (15 minutes)")
            print("⏰ Starting long break...")
            for minutes in range(15, 0, -1):
                for seconds in range(60, 0, -1):
                    print(f"\\r⏳ {{minutes:02d}}:{{seconds:02d}} remaining", end="", flush=True)
                    time.sleep(1)
            print(f"\\n✅ Long break completed!")
        else:
            print(f"\\n☕ Short Break Time (5 minutes)")
            print("⏰ Starting short break...")
            for minutes in range(5, 0, -1):
                for seconds in range(60, 0, -1):
                    print(f"\\r⏳ {{minutes:02d}}:{{seconds:02d}} remaining", end="", flush=True)
                    time.sleep(1)
            print(f"\\n✅ Short break completed!")

print(f"\\n🎉 All {{sessions}} Pomodoro sessions completed!")
print("🏆 Great job! You've finished your work session.")
"""
            script_path = "/tmp/pomodoro_timer.py"
            with open(script_path, "w") as f:
                f.write(pomodoro_script)
            subprocess.run(["chmod", "+x", script_path])
            log_file = os.path.expanduser("~/.alltool_pomodoro.log")
            with open(log_file, "w") as log:
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    stdout=log,
                    stderr=log,
                    preexec_fn=os.setsid,
                )

            print("✅ Pomodoro timer started in background")
            print(f"📄 Progress is logged to {log_file}")
            print("💡 Use 'alltool pr stop' to stop the timer")
            print("💡 Use 'tail -f ~/.alltool_pomodoro.log' to watch progress")

        except ValueError:
            print("❌ Error: Sessions must be a number")
            return
        except Exception as e:
            print(f"❌ Error starting Pomodoro timer: {e}")
            return
    elif command == "cl":
        subprocess.run(["clear"])
    elif command == "upa":
        avup = ["st", "pv"]
        if len(sys.argv) > 2:
            subc = sys.argv[2]
            if subc not in avup:
                print(f"❌ Command {subc} not found.")
                print(
                    "availbe commands: st: download latest AllTool stable version, pv: download latest AllTool preview version."
                )
            elif subc == "st":
                githubst = "https://raw.githubusercontent.com/Iinitialb/AllTool-Linux/refs/heads/Stable/AllToolInstaller.py"

                def get_remote_version_and_code():
                    response = requests.get(githubst)
                    if response.status_code == 200:
                        code = response.text
                        match = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', code)
                        return match.group(1) if match else None, code
                    return None, None

                def get_local_version():
                    try:
                        with open(LOCAL_PATH, "r", encoding="utf-8") as f:
                            code = f.read()
                        match = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', code)
                        return match.group(1) if match else None
                    except FileNotFoundError:
                        return None

                def update_script():
                    remote_version, remote_code = get_remote_version_and_code()
                    local_version = get_local_version()

                    if remote_version and (
                        local_version is None
                        or version.parse(remote_version) > version.parse(local_version)
                    ):
                        with open(LOCAL_PATH, "w", encoding="utf-8") as f:
                            f.write(remote_code)
                        print(
                            f"✅ Updated AllTool.py from {local_version} to {remote_version}"
                        )
                    else:
                        print("✅ Already up to date.")

                update_script()
            elif subc == "pv":
                githubpr = "https://raw.githubusercontent.com/Iinitialb/AllTool-Linux/refs/heads/Preview/AllTools.py"

                def get_remote_version_and_code1():
                    response = requests.get(githubpr)
                    if response.status_code == 200:
                        code = response.text
                        match = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', code)
                        return match.group(1) if match else None, code
                    return None, None

                def get_local_version1():
                    try:
                        with open(LOCAL_PATH, "r", encoding="utf-8") as f:
                            code = f.read()
                        match = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', code)
                        return match.group(1) if match else None
                    except FileNotFoundError:
                        return None

                def update_script1():
                    remote_version, remote_code = get_remote_version_and_code1()
                    local_version = get_local_version1()

                    if remote_version and (
                        local_version is None
                        or version.parse(remote_version) > version.parse(local_version)
                    ):
                        with open(LOCAL_PATH, "w", encoding="utf-8") as f:
                            f.write(remote_code)
                        print(
                            f"✅ Updated AllTool.py from {local_version} to {remote_version}"
                        )
                    else:
                        print("✅ Already up to date.")

                update_script1()
        else:
            print(
                "Usage: alltool upa [updating version, st: updating to the latest stable version] or pv: updating to the latest preview version"
            )
    elif command == "un":
        print("Welcome, AllTool uninstaller")
        uncon()
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'alltool help [language]' to see available commands.")


main()
