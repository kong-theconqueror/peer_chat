import socket
from PyQt5.QtCore import QObject, pyqtSignal

class ReceiverWorker(QObject):
    data_received = pyqtSignal(bytes)
    disconnected = pyqtSignal()

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.running = True

    def run(self):
        try:
            while self.running:
                data = self.conn.recv(1024)
                if not data:
                    break
                self.data_received.emit(data)
        finally:
            self.conn.close()
            self.disconnected.emit()

    def stop(self):
        self.running = False
        self.conn.close()