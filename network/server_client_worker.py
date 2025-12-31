import socket
from PyQt5.QtCore import QObject, pyqtSignal
from network.protocol import decode_message

class ServerClientWorker(QObject):
    new_data = pyqtSignal(bytes)
    disconnected = pyqtSignal()
    peer_identified = pyqtSignal(dict)

    def __init__(self, conn: socket.socket):
        super().__init__()
        self.conn = conn
        self.running = False
        self.peer_id = None

    def run(self):
        print('[S_CLIENT] Running')
        try:
            self.running = True
            while self.running:
                print('[S_CLIENT] Waiting data!', )
                data = self.conn.recv(4096)
                if not data:
                    break
                # Try to decode and identify peer id from protocol message
                try:
                    msg = decode_message(data)
                    peer_id = msg.get('from')
                    if peer_id and not self.peer_id:
                        self.peer_id = peer_id
                        self.peer_identified.emit({
                            "peer_id": peer_id,
                            "username": msg.get('from_n') or peer_id,
                            "ip": "",
                            "port": 0,
                            "status": 1,
                            "last_seen": None
                        })
                except Exception:
                    pass
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
