import sqlite3
from core.db import ChatDatabase


def test_propagate_names_from_upsert(tmp_path):
    db_file = tmp_path / "test_propagate.db"
    # Create DB and a message without sender_name
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE messages (
            id VARCHAR(36),
            sender TEXT,
            sender_name TEXT,
            receiver TEXT,
            receiver_name TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_sent INTEGER DEFAULT 1
        )
    """)
    conn.execute("INSERT INTO messages (id, sender, receiver, content) VALUES (?, ?, ?, ?)", ("m1", "peer1", "peer2", "hello"))
    conn.commit()
    conn.close()

    db = ChatDatabase(str(db_file))

    # Note: migrate() may have backfilled sender_name to a short id already.
    # We only require that the name is not yet the final username 'Alice'.
    cur = db.conn.cursor()
    cur.execute("SELECT sender_name FROM messages WHERE id = 'm1'")
    row = cur.fetchone()
    assert row is not None

    # Upsert neighbor and expect propagation into messages (should overwrite/backfill)
    db.upsert_neighbor("peer1", "Alice", "127.0.0.1", 8080, status=1)

    cur.execute("SELECT sender_name FROM messages WHERE id = 'm1'")
    row = cur.fetchone()
    assert row[0] == "Alice"

    # Change username and ensure messages are updated
    db.upsert_neighbor("peer1", "Alice2", "127.0.0.1", 8080, status=1)
    cur.execute("SELECT sender_name FROM messages WHERE id = 'm1'")
    row = cur.fetchone()
    assert row[0] == "Alice2"

    db.conn.close()