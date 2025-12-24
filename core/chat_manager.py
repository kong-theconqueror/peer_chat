from PyQt5.QtCore import QObject, pyqtSignal, QThread
from network.server_worker import ServerWorker
from network.client_worker import ClientWorker
from core.db import ChatDatabase
from network.protocol import encode_message, decode_message

class ChatManager(QObject):
    message_received = pyqtSignal(dict)
    log_received = pyqtSignal(dict)
    status = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config = None
        # SERVER THREAD
        self.server_thread = QThread()
        self.server_worker = ServerWorker()

        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.run)

        self.server_worker.new_data.connect(self.handle_data)
        self.server_worker.status.connect(self.status.emit)

        self.server_worker.finished.connect(self.server_thread.quit)
        self.server_worker.finished.connect(self.server_worker.deleteLater)
        self.server_thread.finished.connect(self.server_thread.deleteLater)

        # CLIENT
        # self.client_thread = QThread()
        self.client_worker = None

    def set_config(self, config):
        self.config = config
        self.server_worker.set_config(config) 

    def start(self):
        self.server_thread.start()

    def connect_to_peer(self, host, port):
        self.client_worker = ClientWorker(host, port)
        self.client_worker.connect_to_peer()

    def send_message(self, text):
        if self.client_worker:
            self.client_worker.send(text.encode())

    def handle_data(self, data):
        msg = decode_message(data)
        if msg['type'] == "MESSAGE":
            self.message_received.emit(msg)
        elif msg['type'] == "FIND_NODES":
            self.log_received.emit(msg)

            self.client_worker
        else:
            pass

    def stop(self):
        self.server_worker.stop()
        self.server_thread.quit()
        self.server_thread.wait()

    def find_nodes(self):
        ttl = self.config.ttl
        chat_db = ChatDatabase(f'{self.config.node}.db')
        neighbors = chat_db.get_neighbors()
        print(neighbors)

        for neighbor in neighbors:
            try:
                self.connect_to_peer(neighbor["ip"], neighbor["port"])
                en_message = encode_message(
                        sender=self.config.user_id,
                        sender_name = self.config.username,
                        receiver="",
                        content="Ping!",
                        message_type="FIND_NODES"
                    )
                print(en_message)
                self.send_message(en_message)
            except Exception as err:
                # print(f"[ERROR] connect to {neighbor["username"]} timeout!")
                print(f"[ERROR]", str(err))