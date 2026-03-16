"""
horde_client.py  —  Drop-in network client for Horde Survivor v3
================================================================
Usage in horde_survivor_v3.py:
  1. Place this file in the same folder as horde_survivor_v3.py
  2. Add at the top of horde_survivor_v3.py:
        from horde_client import HordeClient
        client = HordeClient("http://YOUR_SERVER_IP:5000")
  3. After player dies (in death_screen or game_loop), call:
        client.submit_score(wave, level, kills, boss_kills, score, weapon)
  4. On title screen login / register, call:
        client.login(username, password)   # or client.register(...)
  5. On game start, call:
        merged_save = client.pull_save(save)   # merge server save into local
  6. On death, call:
        client.push_save(save)                 # upload to server
  7. client.username and client.logged_in for UI state
"""

import json, threading, urllib.request, urllib.error, urllib.parse, os

DEFAULT_SERVER = "http://localhost:5000"
TOKEN_FILE = "horde_token.json"

class HordeClient:
    def __init__(self, server_url: str = DEFAULT_SERVER):
        self.server_url = server_url.rstrip("/")
        self.username   = None
        self.token      = None
        self.logged_in  = False
        self.last_error = ""
        self._load_token()

    # ── Persistence ──────────────────────────────────────────────────────────
    def _load_token(self):
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE) as f:
                    d = json.load(f)
                    self.token    = d.get("token")
                    self.username = d.get("username")
                    self.logged_in= bool(self.token)
            except Exception:
                pass

    def _save_token(self):
        with open(TOKEN_FILE, "w") as f:
            json.dump({"token": self.token, "username": self.username}, f)

    def logout(self):
        self.token = self.username = None
        self.logged_in = False
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)

    # ── HTTP helpers ──────────────────────────────────────────────────────────
    def _request(self, method: str, path: str, data=None, timeout=8) -> dict:
        url = self.server_url + path
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = json.dumps(data).encode() if data is not None else None
        req  = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode())
            except Exception:
                return {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": str(e)}

    # ── Auth ─────────────────────────────────────────────────────────────────
    def register(self, username: str, password: str) -> dict:
        """Register a new account. Returns {"ok": True} or {"error": "..."}."""
        return self._request("POST", "/api/register", {"username": username, "password": password})

    def login(self, username: str, password: str) -> dict:
        """Login. On success stores token and returns {"ok": True, "token": ...}."""
        d = self._request("POST", "/api/login", {"username": username, "password": password})
        if d.get("ok"):
            self.token     = d["token"]
            self.username  = d["username"]
            self.logged_in = True
            self._save_token()
        else:
            self.last_error = d.get("error", "Unknown error")
        return d

    # ── Score submission ──────────────────────────────────────────────────────
    def submit_score(self, wave: int, level: int, kills: int,
                     boss_kills: int, score: int, weapon: str,
                     supercoins: int = 0, async_: bool = True) -> dict | None:
        """
        Submit a run score to the server.
        If async_=True (default), fires in a background thread and returns None.
        If async_=False, blocks and returns the response dict.
        """
        if not self.logged_in:
            return {"error": "Not logged in"}

        payload = {
            "wave": wave, "level": level, "kills": kills,
            "boss_kills": boss_kills, "score": score,
            "weapon": weapon, "supercoins": supercoins,
        }

        if async_:
            t = threading.Thread(target=self._request,
                                 args=("POST", "/api/score", payload),
                                 daemon=True)
            t.start()
            return None
        else:
            return self._request("POST", "/api/score", payload)

    # ── Save sync ─────────────────────────────────────────────────────────────
    def pull_save(self, local_save: dict) -> dict:
        """
        Download server save and merge with local save.
        Server wins on supercoins (takes max), meta upgrades (takes max per key),
        and discovery data (union).
        Returns the merged save dict.
        """
        if not self.logged_in:
            return local_save

        d = self._request("GET", f"/api/sync/{self.username}")
        server_save = d.get("save", {})
        if not isinstance(server_save, dict):
            return local_save

        merged = dict(local_save)

        # SuperCoins: take maximum
        merged["supercoins"] = max(
            local_save.get("supercoins", 0),
            server_save.get("supercoins", 0)
        )

        # Meta upgrades: per-key max
        local_meta  = local_save.get("meta_upgrades", {})
        server_meta = server_save.get("meta_upgrades", {})
        merged_meta = dict(local_meta)
        for k, v in server_meta.items():
            merged_meta[k] = max(merged_meta.get(k, 0), v)
        merged["meta_upgrades"] = merged_meta

        # Super tier unlocked: union
        local_unl  = local_save.get("super_tier_unlocked", {})
        server_unl = server_save.get("super_tier_unlocked", {})
        merged["super_tier_unlocked"] = {**local_unl, **server_unl}

        # Super tier levels: per-key max
        local_stl  = local_save.get("super_tier_levels", {})
        server_stl = server_save.get("super_tier_levels", {})
        merged_stl = dict(local_stl)
        for k, v in server_stl.items():
            merged_stl[k] = max(merged_stl.get(k, 0), v)
        merged["super_tier_levels"] = merged_stl

        # Discovery indexes: union
        for key in ("seen_structures", "seen_events"):
            local_list  = local_save.get(key, [])
            server_list = server_save.get(key, [])
            merged[key] = list(set(local_list) | set(server_list))

        # Stats: take maximum
        for key in ("total_runs", "total_kills", "best_wave"):
            merged[key] = max(
                local_save.get(key, 0),
                server_save.get(key, 0)
            )

        return merged

    def push_save(self, save: dict, async_: bool = True):
        """Upload local save to server."""
        if not self.logged_in:
            return

        def _push():
            self._request("POST", f"/api/sync/{self.username}", {"save": save})

        if async_:
            threading.Thread(target=_push, daemon=True).start()
        else:
            _push()

    # ── Leaderboard fetch ─────────────────────────────────────────────────────
    def get_leaderboard(self, page: int = 1) -> list[dict]:
        """Returns list of top score dicts (non-blocking convenience wrapper)."""
        d = self._request("GET", f"/api/leaderboard?page={page}")
        return d.get("scores", [])

    # ── Online leaderboard widget for pygame ─────────────────────────────────
    def fetch_top_scores_async(self, callback):
        """
        Fetch top scores in background thread.
        Calls callback(scores_list) when done.
        callback receives a list of score dicts or [] on failure.
        """
        def _fetch():
            scores = self.get_leaderboard(1)
            callback(scores)
        threading.Thread(target=_fetch, daemon=True).start()
