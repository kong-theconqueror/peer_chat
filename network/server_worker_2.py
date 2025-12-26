import socket
from PyQt5.QtCore import QObject, QThread, pyqtSignal

class ClientHandlerWorker(QObject):
    new_data = pyqtSignal(bytes)
    disconnected = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, conn, addr):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.running = True

    def run(self):
        self.conn.settimeout(1.0)

        try:
            while self.running:
                try:
                    data = self.conn.recv(4096)
                    if not data:
                        break
                    self.new_data.emit(data)

                except socket.timeout:
                    continue
                except OSError:
                    break

        finally:
            self.cleanup()

    def send(self, data: bytes):
        try:
            self.conn.sendall(data)
        except Exception:
            self.cleanup()

    def stop(self):
        self.running = False

    def cleanup(self):
        if self.running:
            self.running = False
            self.disconnected.emit()

        try:
            self.conn.close()
        except:
            pass

        self.finished.emit()

class ServerWorker(QObject):
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = False
        self.sock = None
        self.config = None
        self.handlers = []   # giữ reference để tránh GC

    def set_config(self, config):
        self.config = config

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.config.ip, self.config.port))
            self.sock.listen()
            self.sock.settimeout(1.0)

            self.running = True
            self.status.emit(
                f"[SERVER] Listening on {self.config.ip}:{self.config.port}"
            )

            while self.running:
                try:
                    conn, addr = self.sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                self.status.emit(f"[SERVER] Incoming connection from {addr}")
                self._create_handler(conn, addr)

        except Exception as e:
            self.status.emit(f"[SERVER_ERROR] {str(e)}")

        finally:
            self.stop()
    
    def stop(self):
        self.running = False

        for h in self.handlers:
            try:
                h.stop()
            except:
                pass

        try:
            if self.sock:
                self.sock.close()
        except Exception as e:
            print(f'[SERVER_ERROR] Error closing server socket: {e}')
            pass

        self.finished.emit()

    def _create_handler(self, conn, addr):
        handler = ClientHandlerWorker(conn, addr)
        thread = QThread()

        handler.moveToThread(thread)
        thread.started.connect(handler.run)

        # forward data lên ChatManager
        handler.new_data.connect(self._forward_data)

        handler.finished.connect(thread.quit)
        handler.finished.connect(handler.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self.handlers.append(handler)

        thread.start()

    def _forward_data(self, data: bytes):
        # ChatManager đã connect server_worker.status,
        # nên emit data thông qua status hoặc signal riêng nếu muốn
        # Ở đây emit status cho debug, ChatManager nhận new_data từ ClientWorker
        self.status.emit("[SERVER] Data received")
        # ChatManager sẽ connect ClientHandlerWorker.new_data trực tiếp
