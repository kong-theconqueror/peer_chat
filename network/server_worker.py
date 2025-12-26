import socket
from PyQt5.QtCore import QObject, pyqtSignal

class ServerWorker(QObject):
    new_connection = pyqtSignal(object)   # socket
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, host="0.0.0.0", port=0):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = None
        self.running = False

    def set_config(self, config):
        self.host = config.ip
        self.port = config.port

    def run(self):
        self.status.emit("[SERVER] Server starting...")

        try:    
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen()
            # self.sock.settimeout(1.0)   # 01 secound
        
            self.status.emit(f"[SERVER] Listening on {self.host}:{self.port}")
            self.running = True

            while self.running:
                conn, addr = self.sock.accept()
                self.status.emit(f"[SERVER] Peer connected: {addr}")
                self.new_connection.emit(conn)
                self.handle_client(conn)

        except Exception as e:
            self.status.emit(f'[SERVER_ERROR] {str(e)}')
        finally:
            self.stop()

    def handle_client(self, conn):
        # conn.settimeout(1.0)
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
        try:
            self.sock.close()
        except:
            pass
        self.finished.emit()
