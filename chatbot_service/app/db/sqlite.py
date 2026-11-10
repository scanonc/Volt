import os
from pathlib import Path
import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS indexed_products (
    product_id INTEGER PRIMARY KEY,
    content_hash TEXT NOT NULL,
    embedding TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_indexed_products_hash ON indexed_products(content_hash);
"""


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Retorna una conexión configurada con foreign keys y busy_timeout."""
    if db_path != ':memory:':
        parent_dir = Path(db_path).parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row

    if db_path != ':memory:':
        conn.execute("PRAGMA journal_mode = WAL;")

    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> None:
    """Inicializa el esquema de SQLite si no existe."""
    conn = get_db_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
