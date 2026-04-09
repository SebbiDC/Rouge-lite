"""
HORDE SURVIVOR — Server Diagnostic
====================================
Run this from the Rouge lite folder:
    python check_server.py

It checks every important Flask endpoint and prints a clear pass/fail.
"""

import urllib.request
import urllib.error
import json
import sys
import socket

# ── Config ────────────────────────────────────────────────────────────────────
SERVER = "http://127.0.0.1:5000"   # checks locally on the machine running the server

PASS = "  [OK]  "
FAIL = "  [FAIL]"
WARN = "  [WARN]"

results = []

def check(label, ok, detail=""):
    tag = PASS if ok else FAIL
    line = f"{tag} {label}"
    if detail:
        line += f"  →  {detail}"
    print(line)
    results.append(ok)

def get(path, token=None):
    try:
        req = urllib.request.Request(SERVER + path)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body
    except Exception as ex:
        return None, str(ex)

def post(path, data, token=None):
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(SERVER + path, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body
    except Exception as ex:
        return None, str(ex)

# ═══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 55)
print("  HORDE SURVIVOR — SERVER DIAGNOSTIC")
print("=" * 55)
print(f"  Target: {SERVER}")
print()

# ── 1. Basic connectivity ─────────────────────────────────────────────────────
print("── Connectivity ───────────────────────────────────────")
try:
    sock = socket.create_connection(("127.0.0.1", 5000), timeout=3)
    sock.close()
    check("Port 5000 is open and accepting connections", True)
except Exception as e:
    check("Port 5000 is open and accepting connections", False,
          "Server not running? Start it with: python app.py")
    print()
    print("  Cannot reach server — stopping here.")
    print("  Make sure 'python app.py' is running first.")
    print()
    sys.exit(1)

# ── 2. Pages ──────────────────────────────────────────────────────────────────
print()
print("── Pages ──────────────────────────────────────────────")
for path, name in [("/", "Home page"), ("/game", "Download page"),
                   ("/leaderboard", "Leaderboard page"), ("/admin", "Admin page")]:
    try:
        req = urllib.request.Request(SERVER + path)
        with urllib.request.urlopen(req, timeout=5) as r:
            check(name, r.status == 200, f"HTTP {r.status}")
    except Exception as e:
        check(name, False, str(e))

# ── 3. Version / download API ─────────────────────────────────────────────────
print()
print("── Version & Download API ─────────────────────────────")
status, data = get("/api/version")
if status == 200 and isinstance(data, dict):
    check("/api/version", True, f"v{data.get('version','?')}  |  "
          f"windows={data.get('windows_file','none')}  "
          f"linux={data.get('linux_file','none')}")
    # Check download links actually exist
    for key, label in [("windows_url", "Windows download"), ("linux_url", "Linux download")]:
        url = data.get(key, "")
        if not url or not data.get(key.replace("_url","_file")):
            print(f"  {WARN} {label}  →  no file uploaded yet")
        else:
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=5) as r:
                    check(label, r.status == 200, url.split("/")[-1])
            except urllib.error.HTTPError as e:
                check(label, e.code == 200, f"HTTP {e.code} — upload a build via /admin")
            except Exception as ex:
                check(label, False, str(ex))
else:
    check("/api/version", False, str(data))

# ── 4. Auth ───────────────────────────────────────────────────────────────────
print()
print("── Auth API ───────────────────────────────────────────")
TEST_USER = "_diag_test_user_"
TEST_PASS = "diagpass123"

status, data = post("/api/register", {"username": TEST_USER, "password": TEST_PASS})
if status == 201:
    check("Register new account", True)
elif status == 409:
    check("Register new account", True, "user already exists (that's fine)")
else:
    check("Register new account", False, str(data))

status, data = post("/api/login", {"username": TEST_USER, "password": TEST_PASS})
token = None
if status == 200 and data.get("token"):
    token = data["token"]
    check("Login", True, f"token received")
else:
    check("Login", False, str(data))

# ── 5. Score submission ───────────────────────────────────────────────────────
print()
print("── Score API ──────────────────────────────────────────")
if token:
    status, data = post("/api/score", {
        "score": 999, "wave": 3, "level": 2,
        "kills": 50, "boss_kills": 1, "weapon": "pistol", "supercoins": 10
    }, token=token)
    check("Submit score", status == 200 and data.get("ok"), str(data))

    status, data = get("/api/leaderboard")
    check("Leaderboard API", status == 200 and "scores" in data,
          f"{data.get('total',0)} scores in DB")
else:
    print(f"  {WARN} Skipping score tests — login failed")

# ── 6. Admin API ──────────────────────────────────────────────────────────────
print()
print("── Admin API ──────────────────────────────────────────")
ADMIN_TOKEN = "changeme_admin_secret"
try:
    req = urllib.request.Request(SERVER + "/api/admin/stats",
                                  headers={"X-Admin-Token": ADMIN_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        d = json.loads(r.read().decode())
        check("Admin stats (default token)", r.status == 200,
              f"{d.get('total_players',0)} players, {d.get('total_scores',0)} scores")
except urllib.error.HTTPError as e:
    if e.code == 403:
        print(f"  {WARN} Admin stats  →  token changed from default (good!)")
    else:
        check("Admin stats", False, f"HTTP {e.code}")
except Exception as ex:
    check("Admin stats", False, str(ex))

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 55)
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"  ALL {total} CHECKS PASSED ✓")
else:
    print(f"  {passed}/{total} checks passed  —  fix the [FAIL] items above")
print("=" * 55)
print()
