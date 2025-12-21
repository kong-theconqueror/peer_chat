import socket
from PyQt5.QtCore import QThread, pyqtSignal

class ServerThread(QThread):
    new_connection = pyqtSignal(object)

    def __init__(self, host="0.0.0.0", port=9000):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self.host, self.port))
        sock.listen(1)
        self.running = True

        while self.running:            
            conn, addr = sock.accept()
            self.new_connection.emit(conn)

    def stop(self):
        self.running = False