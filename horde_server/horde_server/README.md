# HORDE SURVIVOR — Flask Server Setup Guide
==========================================

## Project Layout

```
horde_server/
├── app.py              ← Flask backend (all API routes + HTML pages)
├── horde_client.py     ← Drop-in client module for the game
├── requirements.txt
├── README.md           ← this file
├── templates/
│   ├── base.html       ← shared nav, styles, toast system
│   ├── index.html      ← landing page + mini leaderboard
│   ├── leaderboard.html← full paginated leaderboard with podium
│   └── admin.html      ← protected admin dashboard
└── instance/
    └── horde.db        ← SQLite database (auto-created on first run)
```

---

## 1 — Install Dependencies

```bash
cd horde_server
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

---

## 2 — Configure Environment Variables

Create a `.env` file (optional but recommended for production):

```env
SECRET_KEY=your_very_long_random_string_here
ADMIN_TOKEN=your_secret_admin_password
```

Or export them before running:

```bash
# Windows PowerShell:
$env:ADMIN_TOKEN = "my_secret_admin_password"

# Mac/Linux:
export ADMIN_TOKEN="my_secret_admin_password"
```

> ⚠️ The default ADMIN_TOKEN is `changeme_admin_secret` — change this before deploying!

---

## 3 — Run the Server

### Development (local testing):
```bash
python app.py
```
Server runs at http://localhost:5000

### Production (with Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Production (with Waitress on Windows):
```bash
pip install waitress
python -c "from waitress import serve; from app import app; serve(app, host='0.0.0.0', port=5000)"
```

---

## 4 — Connect the Game Client

### Step 1: Copy `horde_client.py` next to `horde_survivor_v3.py`

### Step 2: Add these lines to the TOP of `horde_survivor_v3.py` (after imports):

```python
from horde_client import HordeClient

# Change this to your server's IP/domain:
client = HordeClient("http://localhost:5000")
```

### Step 3: Add online login to `title_screen()` or `weapon_select_screen()`

Add a login prompt before the game starts. Example — in `title_screen(save)`,
inside the key event loop, add:

```python
if ev.key == pygame.K_o:   # press O for online
    # Simple username/password prompt (you can use a proper pygame text input)
    # For now this shows a quick example:
    pass  # see full integration example below
```

### Step 4: Submit score on death

In `game_loop()`, in the `state=="dead"` handling block, before calling `death_screen()`:

```python
# Submit score to server (async, won't block game)
client.submit_score(
    wave=wm.wave,
    level=player.level,
    kills=kills,
    boss_kills=boss_kills,
    score=score,
    weapon=starting_weapon,
    supercoins=save.get("supercoins", 0),
)
```

### Step 5: Sync save on game start

In `game_loop()`, right after `apply_meta_to_player(player, save)`:

```python
# Pull server save and merge (async safe: do it before the run)
if client.logged_in:
    save = client.pull_save(save)
    apply_meta_to_player(player, save)   # re-apply after merge
```

### Step 6: Push save on death

In `death_screen()`, after `write_save(save)`:

```python
if client.logged_in:
    client.push_save(save)   # async upload, won't block
```

---

## 5 — Full Login Integration Example

For a minimal but functional in-game login flow, add this to `weapon_select_screen()`:

```python
# Inside the keyboard event loop:
if ev.key == pygame.K_o and not client.logged_in:
    # Collect username
    username = simple_text_input(screen, clock, "ENTER USERNAME")
    password = simple_text_input(screen, clock, "ENTER PASSWORD", hide=True)
    if username and password:
        result = client.login(username, password)
        if result.get("ok"):
            toast_msg = f"Logged in as {client.username}!"
        else:
            toast_msg = result.get("error", "Login failed")
```

You can add `simple_text_input()` as a helper:

```python
def simple_text_input(screen, clock, prompt, hide=False):
    """Simple blocking text input for pygame."""
    text = ""
    while True:
        screen.fill(BG)
        dtxt(screen, prompt, font_med, WHITE, W//2, H//2-40)
        display = "•" * len(text) if hide else text
        dtxt(screen, display + "_", font_big, PLAYER_C, W//2, H//2+10)
        pygame.display.flip(); clock.tick(60)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN: return text
                if ev.key == pygame.K_ESCAPE: return ""
                if ev.key == pygame.K_BACKSPACE: text = text[:-1]
                elif ev.unicode.isprintable(): text += ev.unicode
```

---

## 6 — Admin Panel

1. Open **http://YOUR_SERVER_IP:5000/admin**
2. Enter your `ADMIN_TOKEN` (from env var or default `changeme_admin_secret`)
3. Token is stored in browser `sessionStorage` — closes with the tab

**Admin capabilities:**
- View server stats (players, runs, top score, banned count)
- Browse all players, search by username
- Ban / unban players
- Delete individual score entries
- View weapon popularity chart
- Reset all cloud saves (danger zone)

---

## 7 — API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/register` | — | Create account |
| POST | `/api/login` | — | Login, returns token |
| POST | `/api/score` | Bearer | Submit run score |
| GET | `/api/leaderboard` | — | Top scores (paginated) |
| GET | `/api/profile/<username>` | — | Player stats |
| GET | `/api/sync/<username>` | Bearer | Pull cloud save |
| POST | `/api/sync/<username>` | Bearer | Push cloud save |
| GET | `/api/admin/stats` | X-Admin-Token | Server stats |
| GET | `/api/admin/players` | X-Admin-Token | All players |
| DELETE | `/api/admin/score/<id>` | X-Admin-Token | Delete score |
| POST | `/api/admin/ban/<username>` | X-Admin-Token | Toggle ban |
| POST | `/api/admin/reset_saves` | X-Admin-Token | Wipe cloud saves |

**Example: Submit a score with curl**
```bash
# Login first
TOKEN=$(curl -s -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"pass1234"}' | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Submit score
curl -X POST http://localhost:5000/api/score \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wave":8,"level":12,"kills":340,"boss_kills":2,"score":14500,"weapon":"lightning"}'
```

---

## 8 — Deploying to a VPS / Cloud Server

### Nginx reverse proxy (recommended):

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Systemd service (`/etc/systemd/system/horde.service`):

```ini
[Unit]
Description=Horde Survivor Game Server
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/horde_server
Environment="ADMIN_TOKEN=your_secret_token"
Environment="SECRET_KEY=your_secret_key"
ExecStart=/path/to/horde_server/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable horde
sudo systemctl start horde
```

---

## 9 — Security Notes

- **Change `ADMIN_TOKEN`** before any public deployment
- The SQLite database (`instance/horde.db`) is created automatically — back it up!
- Passwords are SHA-256 hashed (not bcrypt — upgrade if storing real user data at scale)
- Basic anti-cheat: server rejects supercoins > 999,999
- Score trimming: only top 10 scores per player are kept
- Tokens expire after 30 days
