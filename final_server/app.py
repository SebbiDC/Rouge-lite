"""
HORDE SURVIVOR — Flask Backend v2
===================================
Routes:
  Public:
    GET  /                          -> landing page
    GET  /leaderboard               -> full leaderboard page
    GET  /game                      -> browser game page
    GET  /game/play                 -> serves pygbag index.html
    GET  /game/play/<path>          -> serves pygbag WASM assets
    GET  /api/leaderboard           -> JSON top scores
    GET  /api/leaderboard/stream    -> SSE live updates
    POST /api/score                 -> submit a run score
    POST /api/register              -> create account
    POST /api/login                 -> login, get token
    GET  /api/profile/<username>    -> player stats
    GET  /api/sync/<username>       -> pull server save
    POST /api/sync/<username>       -> push local save

  Admin (requires X-Admin-Token header):
    GET  /admin
    GET  /api/admin/stats
    GET  /api/admin/players
    DELETE /api/admin/score/<id>
    POST /api/admin/ban/<username>
    POST /api/admin/reset_saves
"""

import os, json, hashlib, secrets, time, queue, threading
from functools import wraps

from flask import (Flask, request, jsonify, render_template,
                   send_from_directory, g, Response, stream_with_context)
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# ─── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__, instance_relative_config=True)
CORS(app)

os.makedirs(app.instance_path, exist_ok=True)

app.config.update(
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32)),
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(app.instance_path, "horde.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS = False,
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "changeme_admin_secret"),
    MAX_SCORES_PER_PLAYER = 10,
    LEADERBOARD_PAGE_SIZE = 50,
)

db = SQLAlchemy(app)

# ─── SSE broadcaster ──────────────────────────────────────────────────────────
_sse_listeners = []
_sse_lock = threading.Lock()

def _sse_broadcast(event, data):
    msg = "event: {}\ndata: {}\n\n".format(event, data)
    dead = []
    with _sse_lock:
        for q in _sse_listeners:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_listeners.remove(q)

# ─── Models ───────────────────────────────────────────────────────────────────
class Player(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)
    token         = db.Column(db.String(64), unique=True)
    token_expiry  = db.Column(db.Float, default=0)
    banned        = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.Float, default=time.time)
    cloud_save    = db.Column(db.Text, default="{}")
    scores        = db.relationship("Score", backref="player", lazy=True,
                                    cascade="all, delete-orphan")

    def to_dict(self):
        best = db.session.query(Score).filter_by(player_id=self.id)\
                 .order_by(Score.score.desc()).first()
        return {
            "username":   self.username,
            "banned":     self.banned,
            "created_at": self.created_at,
            "best_wave":  best.wave  if best else 0,
            "best_score": best.score if best else 0,
            "total_runs": len(self.scores),
        }

class Score(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    player_id    = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    username     = db.Column(db.String(32), nullable=False)
    score        = db.Column(db.Integer, nullable=False)
    wave         = db.Column(db.Integer, default=0)
    level        = db.Column(db.Integer, default=1)
    kills        = db.Column(db.Integer, default=0)
    boss_kills   = db.Column(db.Integer, default=0)
    weapon       = db.Column(db.String(20), default="unknown")
    supercoins   = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.Float, default=time.time)
    version      = db.Column(db.String(8), default="v3")

    def to_dict(self):
        return {
            "id":           self.id,
            "username":     self.username,
            "score":        self.score,
            "wave":         self.wave,
            "level":        self.level,
            "kills":        self.kills,
            "boss_kills":   self.boss_kills,
            "weapon":       self.weapon,
            "supercoins":   self.supercoins,
            "submitted_at": self.submitted_at,
            "version":      self.version,
        }

# ─── Helpers ──────────────────────────────────────────────────────────────────
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing token"}), 401
        token = auth.split(" ", 1)[1]
        player = Player.query.filter_by(token=token).first()
        if not player or player.token_expiry < time.time():
            return jsonify({"error": "Invalid or expired token"}), 401
        if player.banned:
            return jsonify({"error": "Account banned"}), 403
        g.player = player
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Admin-Token", "")
        if token != app.config["ADMIN_TOKEN"]:
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return decorated

def _trim_scores(player_id):
    limit = app.config["MAX_SCORES_PER_PLAYER"]
    rows  = Score.query.filter_by(player_id=player_id)\
                 .order_by(Score.score.desc()).all()
    for old in rows[limit:]:
        db.session.delete(old)

# ─── Auth ─────────────────────────────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def register():
    data     = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()[:32]
    password = data.get("password", "")
    if len(username) < 2:
        return jsonify({"error": "Username too short (min 2)"}), 400
    if len(password) < 4:
        return jsonify({"error": "Password too short (min 4)"}), 400
    if Player.query.filter_by(username=username).first():
        return jsonify({"error": "Username taken"}), 409
    p = Player(username=username, password_hash=hash_pw(password))
    db.session.add(p)
    db.session.commit()
    return jsonify({"ok": True, "username": username}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password", "")
    p = Player.query.filter_by(username=username).first()
    if not p or p.password_hash != hash_pw(password):
        return jsonify({"error": "Invalid credentials"}), 401
    if p.banned:
        return jsonify({"error": "Account banned"}), 403
    p.token        = secrets.token_hex(32)
    p.token_expiry = time.time() + 60 * 60 * 24 * 30
    db.session.commit()
    return jsonify({"ok": True, "token": p.token, "username": p.username})

# ─── Scores ───────────────────────────────────────────────────────────────────
@app.route("/api/score", methods=["POST"])
@require_auth
def submit_score():
    data = request.get_json(force=True) or {}
    try:
        score_val  = int(data.get("score",     0))
        wave       = int(data.get("wave",       0))
        level      = int(data.get("level",      1))
        kills      = int(data.get("kills",      0))
        boss_kills = int(data.get("boss_kills", 0))
        weapon     = str(data.get("weapon", "unknown"))[:20]
        supercoins = int(data.get("supercoins", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid data types"}), 400

    s = Score(
        player_id  = g.player.id,
        username   = g.player.username,
        score      = score_val,
        wave       = wave,
        level      = level,
        kills      = kills,
        boss_kills = boss_kills,
        weapon     = weapon,
        supercoins = supercoins,
    )
    db.session.add(s)
    _trim_scores(g.player.id)
    db.session.commit()

    rank = db.session.query(Score)\
             .filter(Score.score > score_val)\
             .distinct(Score.player_id).count() + 1

    _sse_broadcast("score", json.dumps({
        "username": g.player.username,
        "score":    score_val,
        "wave":     wave,
        "weapon":   weapon,
        "rank":     rank,
    }))

    return jsonify({"ok": True, "score_id": s.id, "rank": rank})

@app.route("/api/leaderboard", methods=["GET"])
def api_leaderboard():
    page     = max(1, int(request.args.get("page", 1)))
    per_page = app.config["LEADERBOARD_PAGE_SIZE"]
    weapon   = request.args.get("weapon")
    offset   = (page - 1) * per_page

    from sqlalchemy import func
    sub = db.session.query(
        Score.username,
        func.max(Score.score).label("best_score")
    ).group_by(Score.username).subquery()

    q = db.session.query(Score).join(
        sub,
        (Score.username == sub.c.username) & (Score.score == sub.c.best_score)
    )
    if weapon:
        q = q.filter(Score.weapon == weapon)

    total = q.count()
    rows  = q.order_by(Score.score.desc()).offset(offset).limit(per_page).all()

    return jsonify({
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "scores":   [r.to_dict() for r in rows],
    })

# ─── SSE live stream ──────────────────────────────────────────────────────────
@app.route("/api/leaderboard/stream", methods=["GET"])
def leaderboard_stream():
    q = queue.Queue(maxsize=20)
    with _sse_lock:
        _sse_listeners.append(q)

    def generate():
        yield "event: connected\ndata: ok\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    yield "event: ping\ndata: keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if q in _sse_listeners:
                    _sse_listeners.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        }
    )

@app.route("/api/profile/<username>", methods=["GET"])
def api_profile(username):
    p = Player.query.filter_by(username=username).first_or_404()
    if p.banned:
        return jsonify({"error": "Player not found"}), 404
    scores = Score.query.filter_by(player_id=p.id)\
                  .order_by(Score.score.desc()).limit(10).all()
    return jsonify({
        "player":        p.to_dict(),
        "recent_scores": [s.to_dict() for s in scores],
    })

# ─── Cloud save sync ──────────────────────────────────────────────────────────
@app.route("/api/sync/<username>", methods=["GET"])
@require_auth
def sync_pull(username):
    if g.player.username != username:
        return jsonify({"error": "Forbidden"}), 403
    try:
        data = json.loads(g.player.cloud_save or "{}")
    except Exception:
        data = {}
    return jsonify({"save": data})

@app.route("/api/sync/<username>", methods=["POST"])
@require_auth
def sync_push(username):
    if g.player.username != username:
        return jsonify({"error": "Forbidden"}), 403
    data      = request.get_json(force=True) or {}
    save_data = data.get("save", {})
    if not isinstance(save_data, dict):
        return jsonify({"error": "Invalid save format"}), 400
    coins = save_data.get("supercoins", 0)
    if not isinstance(coins, int) or coins > 999999:
        return jsonify({"error": "Invalid save data"}), 400
    g.player.cloud_save = json.dumps(save_data)
    db.session.commit()
    return jsonify({"ok": True})

# ─── Admin ────────────────────────────────────────────────────────────────────
@app.route("/api/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    from sqlalchemy import func
    total_players = Player.query.count()
    total_scores  = Score.query.count()
    total_banned  = Player.query.filter_by(banned=True).count()
    top_score     = db.session.query(func.max(Score.score)).scalar() or 0
    recent_runs   = Score.query.order_by(Score.submitted_at.desc()).limit(5).all()
    weapon_counts = db.session.query(Score.weapon, func.count(Score.id))\
                              .group_by(Score.weapon).all()
    return jsonify({
        "total_players":     total_players,
        "total_scores":      total_scores,
        "total_banned":      total_banned,
        "top_score":         top_score,
        "recent_runs":       [r.to_dict() for r in recent_runs],
        "weapon_popularity": {w: c for w, c in weapon_counts},
    })

@app.route("/api/admin/players", methods=["GET"])
@require_admin
def admin_players():
    page  = max(1, int(request.args.get("page", 1)))
    q     = request.args.get("q", "")
    per   = 30
    query = Player.query
    if q:
        query = query.filter(Player.username.ilike("%" + q + "%"))
    total   = query.count()
    players = query.order_by(Player.created_at.desc())\
                   .offset((page - 1) * per).limit(per).all()
    return jsonify({
        "total":   total,
        "page":    page,
        "players": [p.to_dict() for p in players],
    })

@app.route("/api/admin/score/<int:score_id>", methods=["DELETE"])
@require_admin
def admin_delete_score(score_id):
    s = Score.query.get_or_404(score_id)
    db.session.delete(s)
    db.session.commit()
    _sse_broadcast("refresh", "deleted")
    return jsonify({"ok": True, "deleted": score_id})

@app.route("/api/admin/ban/<username>", methods=["POST"])
@require_admin
def admin_ban(username):
    p = Player.query.filter_by(username=username).first_or_404()
    p.banned = not p.banned
    db.session.commit()
    action = "banned" if p.banned else "unbanned"
    return jsonify({"ok": True, "username": username, "action": action, "banned": p.banned})

@app.route("/api/admin/reset_saves", methods=["POST"])
@require_admin
def admin_reset_saves():
    Player.query.update({"cloud_save": "{}"})
    db.session.commit()
    return jsonify({"ok": True, "message": "All cloud saves reset"})

# ─── HTML pages ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/leaderboard")
def leaderboard_page():
    return render_template("leaderboard.html")

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

@app.route("/game")
def game_page():
    return render_template("game.html")

# ─── Serve pygbag WASM game files ─────────────────────────────────────────────
# pygbag builds to build/web/ — copy those files to static/game/
# then Flask serves them at /game/play/...
GAME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "game")

@app.route("/game/play")
@app.route("/game/play/")
def game_play_index():
    if not os.path.isdir(GAME_DIR) or not os.path.exists(os.path.join(GAME_DIR, "index.html")):
        return """<!DOCTYPE html><html><body style="background:#0a0a12;color:#fff;font-family:monospace;text-align:center;padding:4rem">
        <h2 style="color:#dc3232">Game not built yet</h2>
        <p style="color:#969696">Run <code style="color:#50c8ff">build_browser_windows.bat</code> first, then restart the server.</p>
        </body></html>""", 404
    return send_from_directory(GAME_DIR, "index.html")

@app.route("/game/play/<path:filename>")
def game_play_files(filename):
    return send_from_directory(GAME_DIR, filename)

# ─── Init ─────────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
