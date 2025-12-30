import os
from core.db import ChatDatabase

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "db")
DB_DIR = os.path.abspath(DB_DIR)


def main():
    print(f"Scanning DB directory: {DB_DIR}")
    files = [f for f in os.listdir(DB_DIR) if f.endswith('.db')]

    if not files:
        print("No .db files found.")
        return

    for f in files:
        print(f"Migrating {f}...")
        try:
            db = ChatDatabase(f)
            db.migrate()
            db.conn.close()
            print(f"  -> Migrated {f}")
        except Exception as e:
            print(f"  -> Failed to migrate {f}: {e}")


if __name__ == '__main__':
    main()