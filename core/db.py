import os
import sqlite3

class ChatDatabase:
    def __init__(self, db_filename="chat.db"):
        self.db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "db")
        self.db_path = os.path.join(self.db_dir, db_filename)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS message (
            id VARCHAR(36),
            sender TEXT,
            receiver TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_sent INTEGER DEFAULT 1
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS neighbor (
            user_id TEXT ,          -- UUID
            username TEXT,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            status INTEGER DEFAULT 1           -- 1=online, 0=offline
        )
        """)

        self.conn.commit()

    def reset_db(self):
        self.conn.execute("DROP TABLE IF EXISTS message")
        self.conn.execute("DROP TABLE IF EXISTS neighbor")

        self.create_tables()

    def save_message(self, sender, receiver, content, is_sent=1):
        sql = """
            INSERT INTO messages (sender, receiver, content, is_sent)
            VALUES (?, ?, ?, ?)
        """
        self.conn.execute(sql, (sender, receiver, content, is_sent))
        self.conn.commit()
    
    def get_conversation(self, user1, user2):
        sql = """
        SELECT sender, receiver, content, timestamp
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
            SELECT user_id, username, ip, port, last_seen, status
            FROM neighbor
            ORDER BY status DESC, last_seen DESC
        """)

        neighbors = [dict(row) for row in cursor.fetchall()]
        self.conn.close()
        return neighbors