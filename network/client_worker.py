import socket
from PyQt5.QtCore import QObject, pyqtSignal

class ClientWorker(QObject):
    connected = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, host, port, timeout=3.0):
        super().__init__()
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect_to_peer(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            # self.sock.settimeout(None)
            self.connected.emit()
        except socket.timeout:
            self.error.emit("Connection timeout")
        except Exception as e:
            self.error.emit(str(e))

    def send(self, data):
        if self.sock:
            self.sock.sendall(data)

    def close(self):
        if self.sock:
            self.sock.close()
