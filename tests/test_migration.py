import os
import sqlite3
from core.db import ChatDatabase


def test_migrate_adds_id_and_backfills(tmp_path):
    db_file = tmp_path / "test_no_id.db"

    # Create a DB with a messages table that lacks 'id' column (old schema)
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE messages (
            sender TEXT,
            receiver TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_sent INTEGER DEFAULT 1
        )
    """)
    conn.execute("INSERT INTO messages (sender, receiver, content) VALUES (?, ?, ?)", ("alice", "bob", "hello"))
    conn.commit()
    conn.close()

    # Instantiate ChatDatabase which should run migration in __init__
    db = ChatDatabase(str(db_file))

    # Check that 'id', 'sender_name' and 'receiver_name' columns now exist
    cur = db.conn.cursor()
    cur.execute("PRAGMA table_info(messages)")
    cols = [r[1] for r in cur.fetchall()]
    assert 'id' in cols
    assert 'sender_name' in cols
    assert 'receiver_name' in cols

    # Check that existing row has non-empty id and sender_name/receiver_name were backfilled
    cur.execute("SELECT id, sender_name, receiver_name FROM messages")
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] is not None and rows[0][0] != ""
    assert rows[0][1] is not None and rows[0][1] != ""
    assert rows[0][2] is not None

    db.conn.close()