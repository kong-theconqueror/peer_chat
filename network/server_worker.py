import socket
from PyQt5.QtCore import QObject, pyqtSignal

class ServerWorker(QObject):
    host="0.0.0.0"
    port=9000
    new_data = pyqtSignal(bytes)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, host="0.0.0.0", port=9000):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False

    def set_config(self, config):
        self.host = config.ip
        self.port = config.port
        print(f'[LOG] Set config {self.host}:{self.port}')


    def run(self):

        self.status.emit("Server starting...")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen(1)
        server.settimeout(1.0)   # 01 secound
        print(f'[LOG] Start listening in {self.host}:{self.port}')

        try:
            self.running = True
            while self.running:
                try:
                    conn, addr = server.accept()
                    self.status.emit(f"Peer connected: {addr}")
                    self.handle_client(conn)
                except socket.timeout:
                    continue
        finally:
            server.close()
            self.finished.emit()
        
        self.running = False
        
    def handle_client(self, conn):
        conn.settimeout(1.0)
        while self.running:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                self.new_data.emit(data)
            except socket.timeout:
                continue
        conn.close()

    def stop(self):
        self.running = False