import socket
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

class ClientWorker(QObject):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    new_data = pyqtSignal(bytes)
    send_data = pyqtSignal(bytes)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, host=None, port=None, sock=None, timeout=3, retry_interval=5000):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = sock
        self.timeout = timeout

        self.retry_interval = retry_interval
        self.retry_enabled = True

        self.running = False        # is running worker
        self._stopped = False       # is stop retry connect

        self.send_data.connect(self._send)

    def _schedule_retry(self):
        if self._stopped or not self.retry_enabled:
            return

        # self.status.emit(
        #     f"[CLIENT] Retry connect to {self.host}:{self.port} after 5s"
        # )
        print(f"[CLIENT] Retry connect to {self.host}:{self.port} after 5s")

        QTimer.singleShot(self.retry_interval, self.connect_to_peer)

    # ---------- outgoing ----------
    def connect_to_peer(self):
        if self.running or self._stopped:
            return

        print(f"[CLIENT DEBUG] Attempting connection to {self.host}:{self.port}")
        self.status.emit(f"[CLIENT] Connecting to {self.host}:{self.port}")

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)

            print(f"[CLIENT DEBUG] Socket created, connecting...")
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)

            self.running = True
            print(f"[CLIENT DEBUG] Connected successfully!")
            self.status.emit(f"[CLIENT] Connected to {self.host}:{self.port}")
            self.connected.emit()

            self.listen()   # blocking recv loop

        except socket.timeout as e:
            print(f"[CLIENT DEBUG] Connection timeout: {e}")
            self.status.emit(f"[CLIENT] Timeout connecting to {self.host}:{self.port}")
            self._cleanup(retry=True)

        except ConnectionRefusedError as e:
            print(f"[CLIENT DEBUG] Connection refused: {e}")
            self.status.emit(f"[CLIENT] Connection refused by {self.host}:{self.port}")
            self._cleanup(retry=True)

        except Exception as e:
            print(f"[CLIENT DEBUG] Other error: {e}")
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
                self.new_data.emit(data)

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
        except:
            pass

        self.finished.emit()

    # ---------- cleanup ----------
    def _cleanup(self, retry=False):
        if self.running:
            self.running = False
            self.disconnected.emit()

        try:
            self.sock.close()
        except:
            pass

        if retry:
            self._schedule_retry()
        else:
            self.finished.emit()