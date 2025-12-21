import json
from PyQt5.QtCore import QObject, pyqtSignal
from network.peer import Peer
from network.protocol import make_message
from crypto.encrypt import encrypt, decrypt

class ChatManager(QObject):
    message_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.peer = Peer()
        self.peer.start_server()
        # self.peer.server.received.connect(self.handle_receive)

    def send_message(self, text):
        encrypted = encrypt(text)
        data = make_message("me", encrypted)
        self.peer.send(data)
        self.message_received.emit(f"Me: {text}")

    def handle_receive(self, data):
        msg = json.loads(data.decode())
        decrypted = decrypt(msg["content"])
        self.message_received.emit(f"Peer: {decrypted}")
