from PyQt5.QtCore import QObject, QThread, pyqtSignal
from uuid import uuid4
from network.client_worker import ClientWorker
from network.server_worker import ServerWorker
from network.server_client_worker import ServerClientWorker
from network.protocol import encode_message, decode_message
from core.db import ChatDatabase

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
            self.init_client(peer_id, neigbor["ip"], neigbor["port"])

    # Handle new client connection to server
    def _on_new_connection(self, conn):
        worker = ServerClientWorker(conn)
        thread = QThread()

        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        worker.new_data.connect(self.handle_incoming)

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
        for neigbor in self.neigbors:
            if neigbor["peer_id"] == peer_id and peer_id not in self.active_peer:
                self.active_peer.append(neigbor)
                self.update_peers.emit(self.active_peer)
                break
    
    # remove active peer to list
    def remove_active_peer(self, peer_id):
        for peer in self.active_peer:
            if peer["peer_id"] == peer_id:
                self.active_peer.remove(peer)
                self.update_peers.emit(self.active_peer)
                break

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

        packet = encode_message(
            sender=self.config.peer_id,
            receiver=peer_id,
            content=text,
            message_type="MESSAGE"
        )

        self.clients[peer_id]["worker"].send_data.emit(packet)

    def send_broadcast_message(self, text):
        """Broadcast MESSAGE to all connected peers (safe iteration)."""
        msg_id = str(uuid4())
        for peer_id, obj in list(self.clients.items()):
            if obj["worker"].running is False:
                continue
            try:
                packet = encode_message(
                    sender=self.config.peer_id,
                    sender_name= self.config.username,
                    receiver="",
                    content=text,
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
            self.message_received.emit(msg)

        elif msg_type == "FIND_NODES":
            self.handle_find_nodes(msg)

        elif msg_type == "FIND_ACK":
            self.log_received.emit(f"Found node: {msg['from']}")

    def handle_forward_msg(self, msg):
        ttl = msg["ttl"] - 1
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
