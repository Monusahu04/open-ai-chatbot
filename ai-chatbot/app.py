import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from openai import OpenAI
from werkzeug.security import check_password_hash, generate_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(APP_DIR, ".env"))

DB_PATH = os.path.join(APP_DIR, "chat.db")
MODEL = "openai/gpt-oss-20b"
MAX_MESSAGE_LEN = 4000
HISTORY_WINDOW = 20  # how many past messages to send back to the model for context
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,20}$")

SYSTEM_PROMPT = (
    "You are a helpful assistant. Today's date is "
    + datetime.utcnow().strftime("%B %d, %Y")
    + ". Your training data has a cutoff and may be outdated for anything that "
    "changes over time (office holders, current events, prices, versions). "
    "As of this date, Donald Trump is the President of the United States "
    "(47th president, second term, inaugurated January 20, 2025). "
    "If you are unsure whether a fact may have changed since your training, "
    "say so instead of stating it with false confidence."
)

app = Flask(
    __name__,
    template_folder=os.path.join(APP_DIR, "templates"),
    static_folder=os.path.join(APP_DIR, "static"),
)

# Sessions need a stable secret key. Set SECRET_KEY in .env for production so
# logins survive a restart; otherwise a random one is used for this run only.
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError(
        f"GROQ_API_KEY is not configured. Create a file at {os.path.join(APP_DIR, '.env')} "
        "with a line: GROQ_API_KEY=your_actual_key"
    )

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
)


# ---------------------------------------------------------------------------
# Data store (SQLite)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT 'New chat',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    latency_ms INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute("PRAGMA foreign_keys = ON")

        # If an older version of this app already created a `conversations`
        # table (before user accounts existed), it won't have a `user_id`
        # column. CREATE TABLE IF NOT EXISTS silently does nothing in that
        # case, so every query referencing user_id would fail. Detect that
        # and rebuild the old tables instead of leaving the app broken.
        existing = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        ).fetchone()
        if existing:
            columns = {row[1] for row in db.execute("PRAGMA table_info(conversations)")}
            if "user_id" not in columns:
                db.executescript(
                    "DROP TABLE IF EXISTS messages; DROP TABLE IF EXISTS conversations;"
                )
                db.commit()

        db.executescript(SCHEMA)
        db.commit()


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in."}), 401
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)

    return wrapped


def current_user_id():
    return session.get("user_id")


# ---------------------------------------------------------------------------
# Routes: pages
# ---------------------------------------------------------------------------


@app.route("/")
@login_required
def home():
    return render_template("index.html", username=session.get("username"))


@app.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("login.html")


# ---------------------------------------------------------------------------
# Routes: auth
# ---------------------------------------------------------------------------


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not USERNAME_PATTERN.match(username):
        return jsonify({
            "error": "Username must be 3-20 characters: letters, numbers, underscores only."
        }), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        return jsonify({"error": "That username is already taken."}), 409

    password_hash = generate_password_hash(password)
    cur = db.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, now()),
    )
    db.commit()

    session["user_id"] = cur.lastrowid
    session["username"] = username
    return jsonify({"username": username}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    remember = bool(data.get("remember"))

    db = get_db()
    user = db.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect username or password."}), 401

    session.permanent = remember
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"username": user["username"]})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def me():
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in."}), 401
    return jsonify({"username": session.get("username")})


# ---------------------------------------------------------------------------
# Routes: conversations (per-user data store)
# ---------------------------------------------------------------------------


@app.route("/api/conversations", methods=["GET"])
@login_required
def list_conversations():
    db = get_db()
    rows = db.execute(
        "SELECT id, title, created_at FROM conversations WHERE user_id = ? ORDER BY id DESC",
        (current_user_id(),),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/conversations", methods=["POST"])
@login_required
def create_conversation():
    db = get_db()
    cur = db.execute(
        "INSERT INTO conversations (user_id, title, created_at) VALUES (?, ?, ?)",
        (current_user_id(), "New chat", now()),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "title": "New chat", "created_at": now()}), 201


@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
@login_required
def delete_conversation(conversation_id):
    db = get_db()
    db.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, current_user_id()),
    )
    db.commit()
    return jsonify({"deleted": conversation_id})


@app.route("/api/conversations/<int:conversation_id>/messages", methods=["GET"])
@login_required
def get_messages(conversation_id):
    db = get_db()
    owned = db.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, current_user_id()),
    ).fetchone()
    if owned is None:
        return jsonify({"error": "Conversation not found."}), 404

    rows = db.execute(
        "SELECT role, content, latency_ms, created_at FROM messages "
        "WHERE conversation_id = ? ORDER BY id ASC",
        (conversation_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Routes: chat
# ---------------------------------------------------------------------------


@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        conversation_id = data.get("conversation_id")
        user_id = current_user_id()

        if not message:
            return jsonify({"error": "Please enter a message."}), 400

        if len(message) > MAX_MESSAGE_LEN:
            return jsonify({
                "error": f"Message is too long. Please keep it under {MAX_MESSAGE_LEN} characters."
            }), 400

        db = get_db()

        # Create a conversation on the fly if the client didn't have one yet.
        if not conversation_id:
            cur = db.execute(
                "INSERT INTO conversations (user_id, title, created_at) VALUES (?, ?, ?)",
                (user_id, message[:60], now()),
            )
            db.commit()
            conversation_id = cur.lastrowid
        else:
            row = db.execute(
                "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
            if row is None:
                return jsonify({"error": "That conversation no longer exists."}), 404

        # Store the user's message.
        db.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) "
            "VALUES (?, 'user', ?, ?)",
            (conversation_id, message, now()),
        )
        db.commit()

        # Build recent history for context.
        history_rows = db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (conversation_id, HISTORY_WINDOW),
        ).fetchall()
        history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]
        messages_for_model = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        start = time.perf_counter()
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages_for_model,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        reply = completion.choices[0].message.content

        db.execute(
            "INSERT INTO messages (conversation_id, role, content, latency_ms, created_at) "
            "VALUES (?, 'assistant', ?, ?, ?)",
            (conversation_id, reply, latency_ms, now()),
        )
        db.commit()

        return jsonify({
            "response": reply,
            "conversation_id": conversation_id,
            "latency_ms": latency_ms,
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Something went wrong. Please try again."}), 500


init_db()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")