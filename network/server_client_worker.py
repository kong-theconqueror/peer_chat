import socket
from PyQt5.QtCore import QObject, pyqtSignal

class ServerClientWorker(QObject):
    new_data = pyqtSignal(bytes)
    disconnected = pyqtSignal()

    def __init__(self, conn: socket.socket):
        super().__init__()
        self.conn = conn
        self.running = False

    def run(self):
        print('[S_CLIENT] Running')
        try:
            self.running = True
            while self.running:
                print('[S_CLIENT] Waiting data!', )
                data = self.conn.recv(4096)
                if not data:
                    break
                self.new_data.emit(data)
        except Exception as e:
            print("[S_CLIENT_ERROR]", str(e))
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        try:
            self.conn.close()
        except:
            pass
        self.disconnected.emit()