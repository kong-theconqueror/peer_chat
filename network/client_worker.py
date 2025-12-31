import socket
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from network.protocol import MessageBuffer
import json

class ClientWorker(QObject):
    connected = pyqtSignal(str)
    disconnected = pyqtSignal(str)
    new_data = pyqtSignal(bytes)  # Emit bytes for backward compat, but now handles one message at a time
    send_data = pyqtSignal(bytes)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, peer_id=None, host=None, port=None, sock=None, timeout=3, retry_interval=5000):
        super().__init__()
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.sock = sock
        self.timeout = timeout

        self.retry_interval = retry_interval
        self.retry_enabled = True

        self.running = False        # is running worker
        self._stopped = False       # is stop retry connect
        
        self.msg_buffer = MessageBuffer()  # Buffer for handling multiple messages per recv()

        self.send_data.connect(self._send)

    def _schedule_retry(self):
        if self._stopped or not self.retry_enabled:
            return

        print(f"[CLIENT] Retry connect to {self.host}:{self.port} after 5s")

        QTimer.singleShot(self.retry_interval, self.connect_to_peer)

    # ---------- outgoing ----------
    def connect_to_peer(self):
        if self.running or self._stopped:
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)

            self.running = True
            self.status.emit(f"[CLIENT] Connected to {self.host}:{self.port}")
            self.connected.emit(self.peer_id)
            
            self.msg_buffer = MessageBuffer()  # Reset buffer for new connection

            self.listen()   # blocking recv loop

        except (socket.timeout, ConnectionRefusedError) as e:
            self._cleanup(retry=True)

        except Exception as e:
            self.status.emit(f"[CLIENT_ERROR] {str(e)}")
            self._cleanup(retry=True)

    # ---------- incoming ----------
    def attach_socket(self):
        self.running = True
        self.connected.emit()
        self.listen()

    # ---------- recv loop ----------
    def listen(self):
        try:
            while self.running:
                data = self.sock.recv(4096)
                if not data:
                    break
                
                # Add to buffer and extract all complete messages
                self.msg_buffer.add_data(data)
                messages = self.msg_buffer.get_all_messages()
                
                # Emit each message as raw JSON bytes (for ChatManager to decode)
                # Note: These are pure JSON without length-prefix since they were already
                # extracted from the length-prefixed stream
                for msg in messages:
                    msg_bytes = json.dumps(msg).encode("utf-8")
                    self.new_data.emit(msg_bytes)

        except Exception as e:
            self.status.emit(str(e))
        finally:
            self._cleanup()

    # ---------- send ----------
    def send(self, data: bytes):
        if not self.running:
            return
        try:
            self.sock.sendall(data)
        except Exception as e:
            self.status.emit(str(e))
            self._cleanup()
    
    def _send(self, data):
        if not self.running:
            return
        try:
            print(f'[CLIENT] Sending data to {self.peer_id}')
            self.sock.sendall(data)
        except Exception as e:
            self.running = False
            self.status.emit(str(e))
            print('[ERROR]', str(e))
            self._cleanup(retry=True)

    # ---------- stop ----------
    def stop(self):
        self._stopped = True
        self.retry_enabled = False
        self.running = False

        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception as e:
            print('[STOP ERROR]', str(e))
            pass

        self.finished.emit()

    # ---------- cleanup ----------
    def _cleanup(self, retry=False):
        if self.running:
            self.running = False
            self.disconnected.emit(self.peer_id)

        try:
            self.sock.close()
        except:
            pass

        if retry:
            self._schedule_retry()
        else:
            self.finished.emit()
