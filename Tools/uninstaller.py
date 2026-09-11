from pathlib import Path

def uninstall(paths: list) -> None:
    unfounds = []
    while True:
        try:
            for raw_path in paths:
                path = Path(raw_path)
                if path.exists():
                    print("Starting AllTool uninstaller...")
                    path.unlink()
                    print(f"Uninstalled: {path}")
                    continue
                else:
                    unfounds.append(raw_path)
        except FileNotFoundError:
            print(f"Unfound: {len(unfounds)}")
            for unfound in unfounds:
                print(f"- {unfound}")
            print("Please try deleting the unfound paths")
