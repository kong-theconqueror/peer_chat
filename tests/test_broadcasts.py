import os
import sqlite3
from core.db import ChatDatabase


def test_get_broadcasts(tmp_path):
    db_file = tmp_path / "test_broadcasts.db"
    db = ChatDatabase(str(db_file))
    db.reset_db()

    # Insert a broadcast message (receiver empty) with sender_name
    db.save_message("bmsg1", "alice", "", "hello everyone", sender_name="alice", receiver_name="", is_sent=1)

    bcs = db.get_broadcasts()
    assert len(bcs) == 1
    mid, sender, sender_name, receiver, receiver_name, content, timestamp, is_sent = bcs[0]
    assert sender == "alice"
    assert sender_name == "alice"
    assert receiver == ""
    assert content == "hello everyone"

    db.conn.close()