import socket
import json
from PyQt5.QtCore import QObject, pyqtSignal
from network.protocol import decode_message, MessageBuffer

class ServerClientWorker(QObject):
    new_data = pyqtSignal(bytes)
    disconnected = pyqtSignal()
    peer_identified = pyqtSignal(str)

    def __init__(self, conn: socket.socket):
        super().__init__()
        self.conn = conn
        self.running = False
        self.peer_id = None
        self.msg_buffer = MessageBuffer()  # Buffer for handling multiple messages per recv()

    def run(self):
        print('[S_CLIENT] Running')
        try:
            self.running = True
            while self.running:
                print('[S_CLIENT] Waiting data!', )
                data = self.conn.recv(4096)
                if not data:
                    break
                
                # Add to buffer and extract all complete messages
                self.msg_buffer.add_data(data)
                messages = self.msg_buffer.get_all_messages()
                
                for msg in messages:
                    # Try to decode and identify peer id from protocol message
                    try:
                        pid = msg.get('from')
                        if pid and not self.peer_id:
                            self.peer_id = pid
                            self.peer_identified.emit(pid)
                    except Exception:
                        pass
                    
                    # Re-encode message as JSON bytes for backward compat
                    msg_bytes = json.dumps(msg).encode("utf-8")
                    self.new_data.emit(msg_bytes)
        except Exception as e:
            print("[S_CLIENT_ERROR]", str(e))
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        try:
            self.conn.close()
        except:
            pass
        self.disconnected.emit()
