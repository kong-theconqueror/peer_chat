import os
import sqlite3
import uuid

class ChatDatabase:
    def __init__(self, db_filename="chat.db"):
        self.db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "db")
        self.db_path = os.path.join(self.db_dir, db_filename)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()
        # Ensure older DBs are migrated to current schema (populate message IDs)
        try:
            self.migrate()
        except Exception:
            # Non-fatal: keep app running even if migration fails; log elsewhere if needed
            pass

    def create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
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

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS neighbor (
            peer_id TEXT ,          -- UUID
            username TEXT,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            status INTEGER DEFAULT 1           -- 1=online, 0=offline
        )
        """)

        self.conn.commit()

    def reset_db(self):
        self.conn.execute("DROP TABLE IF EXISTS messages")
        self.conn.execute("DROP TABLE IF EXISTS neighbor")

        self.create_tables()

    def migrate(self):
        """Ensure 'id', 'sender_name', and 'receiver_name' columns exist and backfill missing values."""
        cur = self.conn.cursor()

        # Ensure messages table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cur.fetchone():
            return

        # Check existing columns
        cur.execute("PRAGMA table_info(messages)")
        cols = [r[1] for r in cur.fetchall()]

        # Add 'id' column if missing
        if 'id' not in cols:
            cur.execute("ALTER TABLE messages ADD COLUMN id VARCHAR(36)")
            self.conn.commit()

        # Add sender_name/receiver_name if missing
        if 'sender_name' not in cols:
            cur.execute("ALTER TABLE messages ADD COLUMN sender_name TEXT")
            self.conn.commit()
        if 'receiver_name' not in cols:
            cur.execute("ALTER TABLE messages ADD COLUMN receiver_name TEXT")
            self.conn.commit()

        # Backfill missing or empty ids
        cur.execute("SELECT rowid, id, sender, receiver, sender_name, receiver_name FROM messages")
        rows = cur.fetchall()
        for row in rows:
            rowid = row[0]
            mid = row[1]
            sender = row[2]
            receiver = row[3]
            sname = row[4]
            rname = row[5]

            if not mid:
                new_id = str(uuid.uuid4())
                cur.execute("UPDATE messages SET id = ? WHERE rowid = ?", (new_id, rowid))

            # If sender_name missing, use short sender id or sender string
            if (sname is None or sname == '') and sender:
                cur.execute("UPDATE messages SET sender_name = ? WHERE rowid = ?", (sender[:8], rowid))

            # If receiver_name missing, set to short receiver id or empty string
            if (rname is None or rname == ''):
                if receiver:
                    cur.execute("UPDATE messages SET receiver_name = ? WHERE rowid = ?", (receiver[:8], rowid))
                else:
                    cur.execute("UPDATE messages SET receiver_name = ? WHERE rowid = ?", ('', rowid))

        self.conn.commit()

    def save_message(self, message_id, sender, receiver, content, sender_name=None, receiver_name=None, is_sent=1):
        sql = """
            INSERT INTO messages (id, sender, sender_name, receiver, receiver_name, content, is_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(sql, (message_id, sender, sender_name, receiver, receiver_name, content, is_sent))
        self.conn.commit()
    
    def get_conversation(self, user1, user2):
        sql = """
        SELECT sender, receiver, content, timestamp, sender_name, receiver_name
        FROM messages
        WHERE (sender=? AND receiver=?)
           OR (sender=? AND receiver=?)
        ORDER BY timestamp
        """
        cursor = self.conn.execute(sql, (user1, user2, user2, user1))
        return cursor.fetchall()
    
    def get_neighbors(self):
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT peer_id, username, ip, port, last_seen, status
            FROM neighbor
            ORDER BY status DESC, last_seen DESC
        """)

        neighbors = [dict(row) for row in cursor.fetchall()]
        return neighbors

    def get_neighbor(self, peer_id: str):
        """Return a neighbor dict for given peer_id or None if not found."""
        if not peer_id:
            return None
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.execute("SELECT peer_id, username, ip, port, last_seen, status FROM neighbor WHERE peer_id = ?", (peer_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None

    def get_broadcasts(self):
        """Return broadcast messages (receiver empty string) ordered by timestamp."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, sender, sender_name, receiver, receiver_name, content, timestamp, is_sent
            FROM messages
            WHERE receiver = '' OR receiver IS NULL
            ORDER BY timestamp
        """)
        return cursor.fetchall()

    def get_username(self, peer_id: str) -> str:
        """Resolve a peer_id to a username using the neighbor table. Returns
        short peer id if username not found."""
        if not peer_id:
            return ""
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT username FROM neighbor WHERE peer_id = ?", (peer_id,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        return peer_id[:8]

    def upsert_neighbor(self, peer_id: str, username: str, ip: str, port: int, status: int = 1):
        """Insert or update a neighbor by peer_id.
        If the neighbor exists, update fields and last_seen; otherwise insert.
        """
        try:
            cur = self.conn.execute("SELECT COUNT(1) FROM neighbor WHERE peer_id = ?", (peer_id,))
            exists = cur.fetchone()[0] > 0

            if exists:
                self.conn.execute(
                    """
                    UPDATE neighbor
                    SET username = ?, ip = ?, port = ?, status = ?, last_seen = CURRENT_TIMESTAMP
                    WHERE peer_id = ?
                    """,
                    (username, ip, port, status, peer_id)
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO neighbor (peer_id, username, ip, port, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (peer_id, username, ip, port, status)
                )
            self.conn.commit()

            # Propagate username into existing messages so stored history displays names
            try:
                # Update messages where this peer is the sender
                self.conn.execute(
                    "UPDATE messages SET sender_name = ? WHERE sender = ?",
                    (username, peer_id)
                )
                # Update messages where this peer is the receiver
                self.conn.execute(
                    "UPDATE messages SET receiver_name = ? WHERE receiver = ?",
                    (username, peer_id)
                )
                self.conn.commit()
            except Exception:
                # Non-fatal: don't let propagation failures crash caller
                pass
        except Exception:
            # Keep DB errors from crashing the app; caller can decide next steps
            pass