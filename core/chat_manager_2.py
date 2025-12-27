from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer
from uuid import uuid4
import os
import json
from network.client_worker_2 import ClientWorker
from network.server_worker_2 import ServerWorker
from network.protocol import encode_message, decode_message
from core.db import ChatDatabase

class ChatManager(QObject):
    # Use object for signals that may carry dicts or other payloads across threads
    message_received = pyqtSignal(object)
    log_received = pyqtSignal(object)
    status = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.clients = {}            # peer_id -> ClientWorker
        self.seen_messages = set()   # chống loop

        self.db = ChatDatabase(f'{self.config.node}.db')
        self.neigbors = self.db.get_neighbors()
        self.active_peer = []

    def init_server(self):
        self.server_thread = QThread()
        self.server_worker = ServerWorker()
        self.server_worker.set_config(self.config)

        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.run)

        # self.server_worker.new_connection.connect(self.handle_new_connection)
        self.server_worker.new_data.connect(self.handle_incoming)
        self.server_worker.status.connect(self.status.emit)

        self.server_worker.finished.connect(self.server_thread.quit)
        self.server_worker.finished.connect(self.server_worker.deleteLater)
        self.server_thread.finished.connect(self.server_thread.deleteLater)
    
    def init_client(self, peer_id, host, port):
        print('[LOG] Creat client threat:', peer_id, host, port)
        self.status.emit(f"Create client: {peer_id} {host}:{port}")

        thread = QThread()
        worker = ClientWorker(host, port)

        worker.moveToThread(thread)
        thread.started.connect(worker.connect_to_peer)

        worker.new_data.connect(self.handle_incoming)
        worker.status.connect(self.status.emit)

        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # ensure we remove worker safely when it finishes
        worker.finished.connect(lambda pid=peer_id: self._on_worker_finished(pid))

        self.clients[peer_id] = {
            "thread": thread,
            "worker": worker
        }
        print("[LOG] Creat client threat success!")

        thread.start()

    def start(self):
        """Start server, ensure neighbors exist, start clients, and run auto-discover."""
        self.init_server()
        self.server_thread.start()

        # ensure neighbor list exists in DB (populate from config files if missing)
        self._ensure_neighbors()

        # refresh neighbors after ensuring
        self.neigbors = self.db.get_neighbors()

        # start clients for neighbors (staggered starts could be added)
        for neigbor in self.neigbors:
            peer_id = neigbor["peer_id"]
            self.init_client(peer_id, neigbor["ip"], neigbor["port"])

        # schedule an automatic FIND_NODES after a short delay so running peers discover network
        QTimer.singleShot(5000, self.find_nodes)
        self.status.emit("Auto-discover scheduled in 5s")

        # monitor clients periodically and ensure peers are connected (helps detect nodes that restart)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_clients)
        self.monitor_timer.start(3000)
        self.status.emit("Client monitor started (interval 3s)")

    def remove_peer(self, peer_id):
        """Safely stop worker thread and remove peer entry."""
        obj = self.clients.get(peer_id)
        if not obj:
            return

        thread = obj.get("thread")
        worker = obj.get("worker")

        try:
            # Ask worker to stop
            if worker:
                worker.stop()
        except Exception:
            pass

        try:
            # Quit and wait for thread to finish
            if thread:
                thread.quit()
                thread.wait(2000)
        except Exception:
            pass

        # Finally remove reference
        if peer_id in self.clients:
            del self.clients[peer_id]

    def _on_worker_finished(self, peer_id):
        """Callback when a worker emits finished; ensure it's cleaned up."""
        # Ensure cleanup is performed in main thread context
        self.remove_peer(peer_id)

    def _ensure_neighbors(self):
        """Populate neighbor DB from config files if none exist."""
        try:
            neighbors = self.db.get_neighbors()
            print(f"[DEBUG] Current neighbors in DB: {len(neighbors)}")

            if neighbors:
                for n in neighbors:
                    print(f"[DEBUG] Existing neighbor: {n}")
                return

            app_dir = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(app_dir, '..', 'config')
            print(f"[DEBUG] Looking for configs in: {config_dir}")

            if not os.path.isdir(config_dir):
                print(f"[DEBUG] Config directory does not exist: {config_dir}")
                return

            # List config files
            config_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
            print(f"[DEBUG] Found config files: {config_files}")

            # insert all configs except self into DB
            for fname in config_files:
                full = os.path.join(config_dir, fname)
                try:
                    with open(full, 'r') as f:
                        cfg = json.load(f)
                    # skip self
                    if cfg.get('peer_id') == self.config.peer_id:
                        print(f"[DEBUG] Skipping self config file: {fname}")
                        continue
                    # insert neighbor if not exists
                    cur = self.db.conn.cursor()
                    cur.execute("SELECT count(*) FROM neighbor WHERE peer_id=?", (cfg.get('peer_id'),))
                    if cur.fetchone()[0] == 0:
                        cur.execute("INSERT INTO neighbor (peer_id, username, ip, port, status) VALUES (?, ?, ?, ?, 1)",
                                    (cfg.get('peer_id'), cfg.get('username'), cfg.get('ip'), cfg.get('port')))
                        self.db.conn.commit()
                        print(f"[DEBUG] Inserted neighbor {cfg.get('peer_id')} from {fname}")
                except Exception as e:
                    print(f"[DEBUG] Failed to process config {full}: {e}")
                    continue
        except Exception as e:
            print(f"[DEBUG] _ensure_neighbors failed: {e}")

    def _monitor_clients(self):
        """Periodic check to recreate missing clients and trigger reconnects for neighbors.
        This helps detect peers that were restarted after this node started.
        """
        try:
            neighbors = self.db.get_neighbors()
            for nb in neighbors:
                peer_id = nb.get("peer_id")
                if peer_id == self.config.peer_id:
                    continue

                # If client record is missing, recreate it
                if peer_id not in self.clients:
                    self.status.emit(f"Recreating client for {peer_id[:8]} {nb.get('ip')}:{nb.get('port')}")
                    self.init_client(peer_id, nb.get('ip'), nb.get('port'))
                else:
                    # If worker exists but is not running and its thread has stopped, recreate to ensure clean state
                    worker = self.clients[peer_id].get('worker')
                    thread = self.clients[peer_id].get('thread')
                    try:
                        if worker and not getattr(worker, 'running', False):
                            if thread and not thread.isRunning():
                                # thread finished previously; recreate
                                self.remove_peer(peer_id)
                                self.init_client(peer_id, nb.get('ip'), nb.get('port'))
                    except Exception as e:
                        print(f"[DEBUG] _monitor_clients error for {peer_id}: {e}")
        except Exception as e:
            print(f"[DEBUG] _monitor_clients failed: {e}")
    def send_message(self, peer_id, text):
        if peer_id not in self.clients:
            self.status.emit("Peer not connected")
            return

        worker = self.clients[peer_id]["worker"]
        if not getattr(worker, 'running', False):
            self.status.emit("Peer is not connected yet")
            return

        packet = encode_message(
            sender=self.config.peer_id,
            receiver=peer_id,
            content=text,
            message_type="MESSAGE"
        )

        try:
            worker.send_data.emit(packet)
            self.status.emit(f"Message sent to {peer_id[:8]}")
        except Exception as e:
            self.status.emit(f"Failed to send: {e}")
            print(f"[ERROR] send_message failed for {peer_id}: {e}")

    def find_nodes(self):
        """Broadcast FIND_NODES to all connected peers (safe iteration).
        Iterate over a snapshot to avoid mutation during callbacks.
        """
        for peer_id, obj in list(self.clients.items()):
            try:
                packet = encode_message(
                    sender=self.config.peer_id,
                    receiver=peer_id,
                    content="",
                    message_type="FIND_NODES"
                )

                try:
                    obj["worker"].send_data.emit(packet)
                except Exception as e:
                    print(f'[ERROR] Failed to send FIND_NODES to {peer_id}: {e}')
            except Exception as e:
                print(f'[ERROR] find_nodes failure for {peer_id}: {e}')
        
    def handle_incoming(self, raw: bytes):
        msg = decode_message(raw)

        # log incoming raw message for debugging
        try:
            self.status.emit(f"[INCOMING] {msg}")
        except Exception:
            pass

        msg_id = msg["message_id"]
        if msg_id in self.seen_messages:
            return
        self.seen_messages.add(msg_id)

        msg_type = msg["type"]

        if msg_type == "MESSAGE":
            self.message_received.emit(msg)

        elif msg_type == "FIND_NODES":
            self.handle_find_nodes(msg)

        elif msg_type == "FIND_ACK":
            # emit a structured log so UI can show from_n and content
            self.log_received.emit({
                'from_n': msg.get('from'),
                'content': f"Found node: {msg.get('from')}"
            })

    def handle_find_nodes(self, msg):
        ttl = msg["ttl"] - 1
        sender = msg["from"]

        ack = encode_message(
            sender=self.config.peer_id,
            receiver=sender,
            content="ACK",
            message_type="FIND_ACK"
        )

        if sender in self.clients:
            try:
                self.clients[sender]["worker"].send_data.emit(ack)
            except Exception as e:
                print(f"[ERROR] Failed to send ACK to {sender}: {e}")

        if ttl <= 0:
            return

        forward = encode_message(
            sender=msg["from"],
            receiver="*",
            content=msg["content"],
            ttl=ttl,
            message_type="FIND_NODES",
            message_id=msg["message_id"]
        )

        for peer_id, obj in list(self.clients.items()):
            if peer_id != sender:
                try:
                    obj["worker"].send_data.emit(forward)
                except Exception as e:
                    print(f"[ERROR] Failed to forward FIND_NODES to {peer_id}: {e}")


    def stop(self):
        self.server_worker.stop()
        self.server_thread.quit()
        self.server_thread.wait()

        for peer_id, obj in self.clients.items():
            obj["worker"].stop()
            obj["thread"].quit()
            obj["thread"].wait()

        # stop monitor timer if running
        if hasattr(self, 'monitor_timer'):
            try:
                self.monitor_timer.stop()
            except Exception:
                pass