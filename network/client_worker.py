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
        # self.status.emit("[CLIENT] Connecting peer...")

        # print("[CLIENT] Connecting peer...")
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)

            self.running = True
            self.status.emit(f"[CLIENT] Connected to {self.host}:{self.port}")
            self.connected.emit()

            self.listen()   # blocking recv loop

        except (socket.timeout, ConnectionRefusedError) as e:
            # self.status.emit(f"[CLIENT_ERROR] {str(e)}")
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