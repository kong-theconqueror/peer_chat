from core.chat_manager import ChatManager
from utils.config import Config
from core.db import ChatDatabase


def test_active_removes_and_db_status(tmp_path):
    # Prepare a db and config
    db_file = tmp_path / "nodeA.db"
    cfg_file = tmp_path / "A.json"

    # Minimal config object
    class DummyConfig:
        def __init__(self):
            self.peer_id = "nodeA"
            self.username = "user_A"
            self.node = "A"
            self.ip = "127.0.0.1"
            self.port = 8080

    cfg = DummyConfig()

    db = ChatDatabase(str(db_file))
    db.reset_db()

    # Insert neighbor entry
    db.upsert_neighbor("peer1", "user_B", "127.0.0.1", 8081, status=0)

    cm = ChatManager(cfg)
    cm.db = db

    # Simulate adding active peer
    cm.add_active_peer("peer1")
    neighbors = db.get_neighbors()
    # peer1 should now be status=1
    peer = [p for p in neighbors if p["peer_id"] == "peer1"][0]
    assert peer["status"] == 1

    # Simulate removing active peer
    cm.remove_active_peer("peer1")
    neighbors = db.get_neighbors()
    peer = [p for p in neighbors if p["peer_id"] == "peer1"][0]
    assert peer["status"] == 0

    db.conn.close()