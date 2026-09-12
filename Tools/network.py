from .base import command, ToolBase
import subprocess
import requests
from bs4 import BeautifulSoup

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

@command("sr", aliases=["search"], help_text="Search the web for information")
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
        results = soup.find_all("div", class_="result__body")

        if not results:
            print("❌ No results could be extracted.")
            return 0

        print("\n📚 Search Results:\n")
        for i, result in enumerate(results[:5], 1):
            title = result.find("a", class_="result__a")
            snippet = result.find("a", class_="result__snippet")
            if title and snippet:
                print(f"{i}. {title.text.strip()}")
                print(f"   {snippet.text.strip()}\n")

    except requests.RequestException as e:
        tool.print_error(f"Network error: {e}")
    except Exception as e:
        tool.print_error(f"Error: {e}")
    return 0

@command("wea", aliases=["weather"], help_text="Get weather information for a city")
def weather(args: list):
    if not args:
        print("Usage: alltool wea <city>")
        return 1

    city = " ".join(args)
    tool = ToolBase()
    tool.print_status(f"Getting weather for: {city}")

    try:
        url = f"https://wttr.in/{city}"
        params = {"format": "2"}
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code == 200:
            print(f"   {resp.text.strip()}")
        else:
            tool.print_error(f"Failed to get weather for '{city}'.")
    except requests.RequestException as e:
        tool.print_error(f"Network error: {e}")
    except Exception as e:
        tool.print_error(f"Error: {e}")
    return 0