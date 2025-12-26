from PyQt5.QtCore import QObject, QThread, pyqtSignal
from uuid import uuid4
from network.client_worker_2 import ClientWorker
from network.server_worker_2 import ServerWorker
from network.protocol import encode_message, decode_message
from core.db import ChatDatabase

class ChatManager(QObject):
    message_received = pyqtSignal(dict)
    log_received = pyqtSignal(str)
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

        worker.finished.connect(lambda: self.remove_peer(peer_id))

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

    def remove_peer(self, peer_id):
        if peer_id in self.clients:
            del self.clients[peer_id]

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

    def find_nodes(self):
        for peer_id, obj in self.clients.items():
            try:
                packet = encode_message(
                    sender=self.config.peer_id,
                    receiver=peer_id,
                    content="",
                    message_type="FIND_NODES"
                )

                obj["worker"].send_data.emit(packet)
            except Exception as e:
                print('[ERROR]', str(e))
        
    def handle_incoming(self, raw: bytes):
        msg = decode_message(raw)

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
            self.log_received.emit(f"Found node: {msg['from']}")

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
            self.clients[sender]["worker"].send_data.emit(ack)

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

        for peer_id, obj in self.clients.items():
            if peer_id != sender:
                obj["worker"].send_data.emit(forward)


    def stop(self):
        self.server_worker.stop()
        self.server_thread.quit()
        self.server_thread.wait()

        for peer_id, obj in self.clients.items():
            obj["worker"].stop()
            obj["thread"].quit()
            obj["thread"].wait()