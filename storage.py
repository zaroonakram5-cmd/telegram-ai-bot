"""
Per-user storage of provider + API key, encrypted at rest with Fernet.

SQLite is fine for a single-instance bot. The encryption key must be set
via the STORAGE_SECRET env var and kept safe - anyone with it can decrypt
every stored API key.
"""

import os
import sqlite3
from datetime import date
from cryptography.fernet import Fernet

DB_PATH = os.environ.get("BOT_DB_PATH", "bot_data.sqlite3")


def _get_fernet() -> Fernet:
    secret = os.environ.get("STORAGE_SECRET")
    if not secret:
        raise RuntimeError(
            "STORAGE_SECRET is not set. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "and put it in your .env file."
        )
    return Fernet(secret.encode())


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_config (
            user_id INTEGER PRIMARY KEY,
            provider TEXT,
            encrypted_key TEXT,
            model TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            provider TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS free_trial_usage (
            user_id INTEGER,
            day TEXT,
            message_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
        """
    )
    conn.commit()
    conn.close()


def set_provider(user_id: int, provider: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO user_config (user_id, provider) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET provider = excluded.provider,
                                            encrypted_key = NULL
        """,
        (user_id, provider),
    )
    conn.commit()
    conn.close()


def set_api_key(user_id: int, api_key: str):
    fernet = _get_fernet()
    encrypted = fernet.encrypt(api_key.encode()).decode()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE user_config SET encrypted_key = ? WHERE user_id = ?",
        (encrypted, user_id),
    )
    conn.commit()
    conn.close()


def set_model(user_id: int, model: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE user_config SET model = ? WHERE user_id = ?",
        (model, user_id),
    )
    conn.commit()
    conn.close()


def get_config(user_id: int):
    """Returns (provider, decrypted_api_key, model) or (None, None, None)."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT provider, encrypted_key, model FROM user_config WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None, None, None
    provider, encrypted_key, model = row
    if not encrypted_key:
        return provider, None, model
    fernet = _get_fernet()
    api_key = fernet.decrypt(encrypted_key.encode()).decode()
    return provider, api_key, model


def clear_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM user_config WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def log_usage(user_id: int, provider: str, model: str, input_tokens: int, output_tokens: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO usage_log (user_id, provider, model, input_tokens, output_tokens)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, provider, model, input_tokens, output_tokens),
    )
    conn.commit()
    conn.close()


def get_usage_summary(user_id: int):
    """Returns a list of (provider, model, total_input, total_output, message_count)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT provider, model, SUM(input_tokens), SUM(output_tokens), COUNT(*)
        FROM usage_log
        WHERE user_id = ?
        GROUP BY provider, model
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_free_trial_count_today(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT message_count FROM free_trial_usage WHERE user_id = ? AND day = ?",
        (user_id, date.today().isoformat()),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def increment_free_trial_count(user_id: int):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO free_trial_usage (user_id, day, message_count) VALUES (?, ?, 1)
        ON CONFLICT(user_id, day) DO UPDATE SET message_count = message_count + 1
        """,
        (user_id, today),
    )
    conn.commit()
    conn.close()
