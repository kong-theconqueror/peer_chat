from PyQt5.QtCore import QObject, QThread, pyqtSignal
from uuid import uuid4
from network.client_worker import ClientWorker
from network.server_worker import ServerWorker
from network.server_client_worker import ServerClientWorker
from network.protocol import encode_message, decode_message
from core.db import ChatDatabase
from crypto.encrypt import derive_aes256_key, encrypt_text, decrypt_text
import os

class ChatManager(QObject):
    message_received = pyqtSignal(dict)
    log_received = pyqtSignal(str)
    update_peers = pyqtSignal(list)
    status = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.clients = {}            # peer_id -> ClientWorker
        self.server_clients = []     # list ServerClientWorker
        self.seen_messages = set()   # chống loop

        self.db = ChatDatabase(f'{self.config.node}.db')
        self.neigbors = self.db.get_neighbors()
        self.active_peer = []

        # --- Crypto runtime flags ---
        # Allow env overrides for quick A/B testing without changing JSON config.
        self._crypto_enabled = self._read_bool_env("PEERCHAT_ENCRYPTION", getattr(self.config, "encryption_enabled", False))
        self._crypto_log_compare = self._read_bool_env("PEERCHAT_CRYPTO_LOG_COMPARE", getattr(self.config, "crypto_log_compare", False))
        env_key = os.getenv("PEERCHAT_AES_KEY", "").strip()
        cfg_key = getattr(self.config, "aes_key", "")
        self._crypto_key = derive_aes256_key(env_key or cfg_key)

        if self._crypto_enabled and not self._crypto_key:
            print("[CRYPTO] Encryption enabled but no key provided (set PEERCHAT_AES_KEY or config aes_key). Falling back to plaintext.")
            self._crypto_enabled = False

    @staticmethod
    def _read_bool_env(name: str, default: bool = False) -> bool:
        v = os.getenv(name)
        if v is None:
            return bool(default)
        v = str(v).strip().lower()
        return v in {"1", "true", "yes", "y", "on"}

    def _maybe_encrypt_for_wire(self, plaintext: str) -> str:
        if not self._crypto_enabled or not self._crypto_key:
            return plaintext

        ciphertext = encrypt_text(plaintext, self._crypto_key)
        if self._crypto_log_compare:
            print(f"[CRYPTO][SEND] plain={plaintext!r}")
            print(f"[CRYPTO][SEND] cipher={ciphertext!r}")
        else:
            print(f"[CRYPTO][SEND] cipher={ciphertext!r}")
        return ciphertext

    def _maybe_decrypt_for_ui(self, wire_payload: str) -> str:
        if not self._crypto_enabled or not self._crypto_key:
            return wire_payload

        try:
            plaintext = decrypt_text(wire_payload, self._crypto_key)
            if self._crypto_log_compare and plaintext != wire_payload:
                print(f"[CRYPTO][RECV] cipher={wire_payload!r}")
                print(f"[CRYPTO][RECV] plain={plaintext!r}")
            return plaintext
        except Exception as e:
            print(f"[CRYPTO][RECV] Decrypt failed: {e}")
            return wire_payload

    def init_server(self):
        self.server_thread = QThread()
        self.server_worker = ServerWorker()
        self.server_worker.set_config(self.config)

        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.run)

        self.server_worker.new_connection.connect(self._on_new_connection)
        self.server_worker.status.connect(self.status.emit)
        # self.server_worker.new_data.connect(self.handle_incoming)

        self.server_worker.finished.connect(self.server_thread.quit)
        self.server_worker.finished.connect(self.server_worker.deleteLater)
        self.server_thread.finished.connect(self.server_thread.deleteLater)
    
    def init_client(self, peer_id, host, port):
        # Guard against invalid endpoints (common cause of WinError 10049 on Windows)
        try:
            port = int(port)
        except Exception:
            port = 0

        if not host or str(host).strip() in {"0.0.0.0", "*"} or port <= 0:
            self.status.emit(f"[CLIENT_SKIP] Invalid endpoint for {peer_id}: {host}:{port}")
            return

        host = str(host).strip()

        print('[LOG] Creat client threat:', peer_id, host, port)
        self.status.emit(f"Create client: {peer_id} {host}:{port}")

        thread = QThread()
        worker = ClientWorker(peer_id, host, port)

        worker.moveToThread(thread)
        thread.started.connect(worker.connect_to_peer)

        worker.new_data.connect(self.handle_incoming)
        worker.status.connect(self.status.emit)
        worker.connected.connect(self.add_active_peer)  # peer_id
        worker.disconnected.connect(self.remove_active_peer)  # peer_id

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
        self.init_server()
        self.server_thread.start()

        for neigbor in self.neigbors:
            peer_id = neigbor["peer_id"]
            self.init_client(peer_id, neigbor.get("ip"), neigbor.get("port"))

    # Handle new client connection to server
    def _on_new_connection(self, conn):
        worker = ServerClientWorker(conn)
        thread = QThread()

        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        worker.new_data.connect(self.handle_incoming)
        # When server client identifies its peer id, mark it active
        worker.peer_identified.connect(self.add_active_peer)
        # When the server client disconnects, remove active peer (use worker.peer_id)
        worker.disconnected.connect(lambda w=worker: self.remove_active_peer(getattr(w, 'peer_id', None)))

        worker.disconnected.connect(thread.quit)
        worker.disconnected.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        self.server_clients.append({
            "thread": thread,
            "worker": worker
        })
        thread.start()

    # add active peer to list
    def add_active_peer(self, peer_id):
        # Try to find neighbor in cached list
        neighbor = None
        for n in self.neigbors:
            if n["peer_id"] == peer_id:
                neighbor = n
                break

        # If not found, refresh from DB (newly discovered peer)
        if neighbor is None:
            try:
                self.neigbors = self.db.get_neighbors()
                for n in self.neigbors:
                    if n["peer_id"] == peer_id:
                        neighbor = n
                        break
            except Exception:
                pass

        # Fallback neighbor object if still missing
        if neighbor is None:
            neighbor = {
                "peer_id": peer_id,
                "username": peer_id[:8],
                "ip": "",
                "port": 0,
                "status": 1,
                "last_seen": None
            }

        # Add to active list if not already
        if not any(p.get("peer_id") == peer_id for p in self.active_peer):
            self.active_peer.append(neighbor)
            self.update_peers.emit(self.active_peer)

            # Mark neighbor as online in DB
            try:
                ip = (neighbor.get("ip") or "").strip()
                port = int(neighbor.get("port") or 0)
                # Only persist if we actually know a connectable endpoint; otherwise avoid polluting DB.
                if ip and ip != "0.0.0.0" and port > 0:
                    self.db.upsert_neighbor(peer_id, neighbor.get("username", peer_id[:8]), ip, port, status=1)
            except Exception as e:
                print(f"[DB_ERROR] Failed to mark neighbor online: {e}")
    
    # remove active peer to list
    def remove_active_peer(self, peer_id):
        if not peer_id:
            return

        for peer in list(self.active_peer):
            if peer.get("peer_id") == peer_id:
                self.active_peer.remove(peer)
                self.update_peers.emit(self.active_peer)
                break
        # Mark neighbor as offline in DB, preserving existing username/ip/port when available
        try:
            neighbor = self.db.get_neighbor(peer_id)
            if neighbor:
                username = neighbor.get("username")
                ip = neighbor.get("ip")
                port = neighbor.get("port")
                self.db.upsert_neighbor(peer_id, username, ip, int(port or 0), status=0)
        except Exception as e:
            print(f"[DB_ERROR] Failed to mark neighbor offline: {e}")

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

    def send_message(self, peer_id, text):
        if peer_id not in self.clients:
            self.status.emit("Peer not connected")
            return

        msg_id = str(uuid4())
        wire_content = self._maybe_encrypt_for_wire(text)
        packet = encode_message(
            sender=self.config.peer_id,
            sender_name=self.config.username,
            receiver=peer_id,
            content=wire_content,
            message_type="MESSAGE",
            message_id=msg_id
        )

        try:
            self.db.save_message(msg_id, self.config.peer_id, peer_id, text, sender_name=self.config.username, receiver_name=self.db.get_username(peer_id), is_sent=1)
        except Exception as e:
            print(f"[DB_ERROR] save_message failed for send_message: {e}")

        self.clients[peer_id]["worker"].send_data.emit(packet)

    def send_broadcast_message(self, text):
        """Broadcast MESSAGE to all connected peers (safe iteration)."""
        msg_id = str(uuid4())
        # Persist the broadcast message as a single outgoing record
        try:
            self.db.save_message(msg_id, self.config.peer_id, "", text, sender_name=self.config.username, receiver_name="", is_sent=1)
        except Exception as e:
            print(f"[DB_ERROR] save_message failed for broadcast: {e}")

        for peer_id, obj in list(self.clients.items()):
            if obj["worker"].running is False:
                continue
            try:
                wire_content = self._maybe_encrypt_for_wire(text)
                packet = encode_message(
                    sender=self.config.peer_id,
                    sender_name= self.config.username,
                    receiver="",
                    content=wire_content,
                    message_type="MESSAGE",
                    message_id=msg_id
                )
                print(f'[LOG] Broadcasting message to {peer_id}: {text}')
                try:
                    obj["worker"].send_data.emit(packet)
                except Exception as e:
                    print(f'[ERROR] Failed to send MESSAGE to {peer_id}: {e}')
            except Exception as e:
                print(f'[ERROR] send_broadcast_message failure for {peer_id}: {e}')

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
        print(f'[LOG] Received message: {msg}')

        msg_id = msg["message_id"]
        # Check if we've seen this message before to prevent loops
        if msg_id in self.seen_messages:
            return
        self.seen_messages.add(msg_id)
        
        # Forward message to other neigbors
        self.handle_forward_msg(msg)

        msg_type = msg["type"]
        # Dispatch based on message type
        if msg_type == "MESSAGE":
            # 1-to-1 messages should only be shown/stored by the intended receiver.
            # Broadcast messages use empty receiver ("") and are shown by everyone.
            receiver = msg.get("to", "")
            if receiver and receiver not in {"*"} and receiver != self.config.peer_id:
                return

            try:
                # Decrypt only for local persistence/UI AFTER forwarding.
                wire_content = msg.get("content", "")
                plain_content = self._maybe_decrypt_for_ui(wire_content)

                # Persist incoming message (received) with sender/receiver names when available
                sender = msg.get("from")
                sender_name = msg.get("from_n") or self.db.get_username(sender)
                receiver_name = msg.get("to_n") or self.db.get_username(receiver)
                self.db.save_message(msg_id, sender, receiver, plain_content, sender_name=sender_name, receiver_name=receiver_name, is_sent=0)
            except Exception as e:
                print(f"[DB_ERROR] save_message failed: {e}")

            msg_out = dict(msg)
            msg_out["content"] = plain_content
            self.message_received.emit(msg_out)

        elif msg_type == "FIND_NODES":
            self.handle_find_nodes(msg)

        elif msg_type == "FIND_ACK":
            content = msg.get("content", {})

            peers = []
            if isinstance(content, dict):
                if "self" in content and isinstance(content["self"], dict):
                    peers.append(content["self"])
                if "neighbors" in content and isinstance(content["neighbors"], list):
                    peers.extend([p for p in content["neighbors"] if isinstance(p, dict)])

            for p in peers:
                try:
                    peer_id = p.get("peer_id")
                    ip = p.get("ip")
                    port = p.get("port")
                    username = p.get("username", (peer_id or "")[:8])

                    if not peer_id or not ip or not port:
                        continue
                    if peer_id == self.config.peer_id:
                        continue

                    # Save/update neighbor and connect if needed
                    try:
                        self.db.upsert_neighbor(peer_id, username, ip, int(port), status=1)
                    except Exception as e:
                        print(f"[DB_ERROR] upsert_neighbor failed: {e}")

                    if peer_id not in self.clients:
                        try:
                            self.init_client(peer_id, ip, int(port))
                        except Exception as e:
                            print(f"[ERROR] Failed to init client to discovered peer {peer_id}: {e}")

                    self.status.emit(f"[DISCOVER] Found peer {username}")
                except Exception:
                    pass

    def handle_forward_msg(self, msg):
        ttl = msg["ttl"] - 1
        if ttl <= 0:
            return
        sender = msg["from"]
        forwarder = msg["forward"]
        msg["forward"] = self.config.peer_id

        forward_msg = encode_message(
            sender=msg["from"],
            sender_name=msg["from_n"],
            receiver=msg["to"],
            receiver_name=msg["to_n"],
            forwarder=self.config.peer_id,
            content=msg["content"],
            ttl=ttl,
            message_type=msg["type"],
            message_id=msg["message_id"]
        )

        for peer_id, obj in list(self.clients.items()):
            if peer_id != forwarder and peer_id != sender:
                try:
                    obj["worker"].send_data.emit(forward_msg)
                except Exception as e:
                    print(f"[ERROR] Failed to forward FIND_NODES to {peer_id}: {e}")

    def handle_find_nodes(self, msg):
        sender = msg["from"]
        ttl = msg["ttl"] - 1

        # Prepare neighbors payload (only online peers with minimal fields)
        neighbors_payload = []
        try:
            for n in self.neigbors:
                if n.get("status", 0) == 1:
                    neighbors_payload.append({
                        "peer_id": n.get("peer_id"),
                        "username": n.get("username"),
                        "ip": n.get("ip"),
                        "port": n.get("port"),
                    })
        except Exception:
            pass

        ack = encode_message(
            sender=self.config.peer_id,
            sender_name=self.config.username,
            receiver=sender,
            message_type="FIND_ACK",
            content={
                "self": {
                    "peer_id": self.config.peer_id,
                    "username": self.config.username,
                    "ip": self.config.ip,
                    "port": self.config.port
                },
                "neighbors": neighbors_payload
            }
        )

        # gửi ngược về (direct hoặc broadcast để forward)
        for peer_id, obj in list(self.clients.items()):
            try:
                obj["worker"].send_data.emit(ack)
            except Exception:
                pass

        if ttl <= 0:
            return

        forward = encode_message(
            sender=msg["from"],
            receiver="*",
            forwarder=self.config.peer_id,
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
        if self.server_worker:
            self.server_worker.stop()
        if self.server_thread:
            self.server_thread.quit()
            self.server_thread.wait()

        for peer_id in list(self.clients.keys()):
            entry = self.clients.pop(peer_id, None)
            if not entry:
                return

            entry["worker"].stop()
            entry["thread"].quit()
            entry["thread"].wait()

        # Close DB connection cleanly
        try:
            if hasattr(self, 'db') and self.db and getattr(self.db, 'conn', None):
                self.db.conn.close()
        except Exception:
            pass
