from .base import command, ToolBase
import subprocess

def _check_speedtest(tool):
    if not tool.has_command("speedtest-cli"):
        tool.print_error("speedtest-cli is not installed.")
        print("   Install with: sudo apt install speedtest-cli  (Debian/Ubuntu)")
        print("               sudo pacman -S speedtest-cli  (Arch)")
        print("               sudo dnf install speedtest-cli  (Fedora)")
        return False
    return True

@command("netspeed", help_text="Measure network speed")
def netspeed(args: list):
    tool = ToolBase()
    if not _check_speedtest(tool):
        return 1
    tool.print_status("Measuring network speed...")
    subprocess.run(["speedtest-cli"])
    return 0

@command("sr", help_text="Search the web for information")
def search_web(args: list):
    if not args:
        print("Usage: alltool sr <search topic>")
        return 1

    topic = " ".join(args).strip()
    if not topic:
        print("❌ Empty search topic.")
        return 1

    tool = ToolBase()
    tool.print_status(f"Searching for: {topic}")

    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        url = "https://html.duckduckgo.com/html/"
        params = {"q": topic, "kl": "us-en"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        if "No results found." in response.text:
            print("❌ No results found.")
            return 0

        soup = BeautifulSoup(response.text, "html.parser")
        # DuckDuckGo changes markup often: try new (.result__body) then
        # legacy (.result) selectors so one layout change doesn't kill us.
        results = soup.find_all("div", class_="result__body") or soup.find_all("div", class_="result")

        if not results:
            print("❌ No results could be extracted.")
            return 1

        print("\n📚 Search Results:\n")
        shown = 0
        for i, result in enumerate(results[:10], 1):
            title = result.find("a", class_="result__a") or result.find("a", class_="result__title")
            snippet = result.find("a", class_="result__snippet") or result.find("div", class_="result__snippet")
            if title and snippet:
                print(f"{shown + 1}. {title.get_text(strip=True)}")
                print(f"   {snippet.get_text(strip=True)}\n")
                shown += 1
                if shown >= 5:
                    break
        if shown == 0:
            print("❌ No results could be extracted.")
            return 1
        return 0

    except ImportError:
        tool.print_error("Missing packages. Install with: pip install requests beautifulsoup4")
        return 1
    except Exception as e:
        tool.print_error(f"Error: {e}")
        return 1

@command("wea", aliases=["weather"], help_text="Get weather information for a city")
def weather(args: list):
    if not args:
        print("Usage: alltool wea <city>")
        return 1

    from urllib.parse import quote
    city = " ".join(args).strip()
    if not city:
        print("❌ Empty city name.")
        return 1
    tool = ToolBase()
    tool.print_status(f"Getting weather for: {city}")

    try:
        import requests
        url = f"https://wttr.in/{quote(city)}"
        params = {"format": "2"}
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code == 200 and resp.text.strip():
            print(f"   {resp.text.strip()}")
            return 0
        else:
            tool.print_error(f"Failed to get weather for '{city}'.")
            return 1
    except ImportError:
        tool.print_error("Python package 'requests' is missing. Install with: pip install requests")
        return 1
    except Exception as e:
        tool.print_error(f"Error: {e}")
        return 1