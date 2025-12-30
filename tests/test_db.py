import os
import time
from core.db import ChatDatabase


def test_save_and_get_conversation():
    db_filename = "test_messages.db"
    db = ChatDatabase(db_filename)

    try:
        # Ensure a clean DB
        db.reset_db()

        # Insert two messages between alice and bob (include sender/receiver names)
        db.save_message("msg1", "alice", "bob", "hi bob", sender_name="alice", receiver_name="bob", is_sent=1)
        # small pause to ensure timestamp order
        time.sleep(0.01)
        db.save_message("msg2", "bob", "alice", "hi alice", sender_name="bob", receiver_name="alice", is_sent=0)

        conv = db.get_conversation("alice", "bob")

        # Expect two rows, ordered by timestamp ascending
        assert len(conv) == 2
        contents = [row[2] for row in conv]
        assert contents == ["hi bob", "hi alice"]
        # Ensure sender_name was stored
        sender_names = [row[4] for row in conv]
        assert sender_names == ["alice", "bob"]

    finally:
        try:
            db.conn.close()
        except Exception:
            pass
        try:
            os.remove(db.db_path)
        except FileNotFoundError:
            pass
