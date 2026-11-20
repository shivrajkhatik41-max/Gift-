import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


class Database:
    def __init__(self, path="bot_history.db"):
        self.path = str(path)
        self.lock = RLock()
        self._init_db()

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with self.lock, self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    feature TEXT DEFAULT 'chat',
                    created_at TEXT NOT NULL
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS user_state (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'auto',
                    pdf_name TEXT,
                    pdf_text TEXT
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id)")

    def add_message(self, uid, role, content, feature="chat"):
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        with self.lock, self._connect() as con:
            con.execute(
                "INSERT INTO messages(user_id, role, content, feature, created_at) VALUES(?,?,?,?,?)",
                (uid, role, content, feature, stamp),
            )

    def get_recent_messages(self, uid, limit=10):
        with self.lock, self._connect() as con:
            rows = con.execute(
                "SELECT role, content, feature, created_at FROM messages "
                "WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_all_messages(self, uid):
        with self.lock, self._connect() as con:
            rows = con.execute(
                "SELECT role, content, feature, created_at FROM messages "
                "WHERE user_id=? ORDER BY id ASC", (uid,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_language(self, uid):
        with self.lock, self._connect() as con:
            row = con.execute("SELECT language FROM user_state WHERE user_id=?", (uid,)).fetchone()
        return row["language"] if row else "auto"

    def set_language(self, uid, language):
        with self.lock, self._connect() as con:
            con.execute(
                "INSERT INTO user_state(user_id, language) VALUES(?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET language=excluded.language",
                (uid, language),
            )

    def set_active_pdf(self, uid, name, text):
        with self.lock, self._connect() as con:
            con.execute(
                "INSERT INTO user_state(user_id, pdf_name, pdf_text) VALUES(?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET pdf_name=excluded.pdf_name, pdf_text=excluded.pdf_text",
                (uid, name, text),
            )

    def get_active_pdf(self, uid):
        with self.lock, self._connect() as con:
            row = con.execute("SELECT pdf_text FROM user_state WHERE user_id=?", (uid,)).fetchone()
        return row["pdf_text"] if row else None

    def clear_user(self, uid):
        with self.lock, self._connect() as con:
            con.execute("DELETE FROM messages WHERE user_id=?", (uid,))
            con.execute(
                "INSERT INTO user_state(user_id, language, pdf_name, pdf_text) VALUES(?, 'auto', NULL, NULL) "
                "ON CONFLICT(user_id) DO UPDATE SET language='auto', pdf_name=NULL, pdf_text=NULL",
                (uid,),
            )
