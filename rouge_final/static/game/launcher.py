"""
Horde Survivor — Auto-Updating Launcher
=========================================
Drop this file next to your game build.
Run it instead of the game directly.

  python launcher.py

It will:
  1. Check /api/version on the server
  2. If a newer version exists → download the new build automatically
  3. Launch the game

Configure SERVER_URL below (or set the HORDE_SERVER env var).
"""

import os
import sys
import json
import platform
import subprocess
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
SERVER_URL   = os.environ.get("HORDE_SERVER", "http://YOUR_SERVER_IP:5000")
VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".local_version")

# ── Helpers ───────────────────────────────────────────────────────────────────

def read_local_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE) as f:
            return f.read().strip()
    return None

def write_local_version(ver):
    with open(VERSION_FILE, "w") as f:
        f.write(ver)

def fetch_server_version():
    url = SERVER_URL.rstrip("/") + "/api/version"
    req = urllib.request.Request(url, headers={"User-Agent": "HordeLauncher/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode())

def download_file(url, dest):
    print(f"  Downloading {os.path.basename(dest)} …")
    def reporthook(count, block, total):
        if total > 0:
            pct = min(100, count * block * 100 // total)
            print(f"\r  {pct}%", end="", flush=True)
    urllib.request.urlretrieve(url, dest, reporthook=reporthook)
    print()

def detect_platform():
    s = platform.system().lower()
    if s == "windows": return "windows"
    if s == "linux":   return "linux"
    return "unknown"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  HORDE SURVIVOR LAUNCHER")
    print("=" * 50)

    local_ver = read_local_version()
    print(f"  Local version : {local_ver or 'none'}")

    # 1. Check server
    try:
        v = fetch_server_version()
        server_ver = v["version"]
        print(f"  Server version: {server_ver}")
    except Exception as e:
        print(f"  [WARN] Could not reach server ({e}). Launching with existing build.")
        return launch_game()

    # 2. Force-update check
    if v.get("force_update") and local_ver != server_ver:
        print("\n  !! MANDATORY UPDATE REQUIRED !!")
        print("  You must update before playing.\n")

    # 3. Download if newer
    if local_ver != server_ver:
        plat = detect_platform()
        if plat == "windows":
            url  = v.get("windows_url")
            dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), v.get("windows_file", "game.apk"))
        elif plat == "linux":
            url  = v.get("linux_url")
            dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), v.get("linux_file", "game.tar.gz"))
        else:
            print(f"  [WARN] Unknown platform '{plat}', skipping download.")
            url = dest = None

        if url:
            print(f"\n  Update available: {local_ver} → {server_ver}")
            print(f"  Release notes: {v.get('notes', '')}\n")
            try:
                download_file(url, dest)
                write_local_version(server_ver)
                print(f"  Updated to v{server_ver} successfully!\n")
            except Exception as e:
                print(f"  [WARN] Download failed: {e}. Running existing build.\n")
        else:
            write_local_version(server_ver)
    else:
        print("  Already up to date.")

    # 4. Launch
    launch_game()


def launch_game():
    plat = detect_platform()
    base = os.path.dirname(os.path.abspath(__file__))

    candidates = []
    if plat == "windows":
        candidates = [
            os.path.join(base, "rouge.lite.exe"),
            os.path.join(base, "rouge.lite.apk"),
            os.path.join(base, "game.exe"),
        ]
    elif plat == "linux":
        candidates = [
            os.path.join(base, "rouge.lite"),
            os.path.join(base, "game"),
        ]

    for path in candidates:
        if os.path.exists(path):
            print(f"\n  Launching: {os.path.basename(path)}\n")
            os.chmod(path, 0o755)
            subprocess.Popen([path])
            return

    # Fallback — open the download page in the browser
    print("\n  No local game binary found.")
    print(f"  Opening download page: {SERVER_URL}/game\n")
    import webbrowser
    webbrowser.open(SERVER_URL + "/game")


if __name__ == "__main__":
    main()
