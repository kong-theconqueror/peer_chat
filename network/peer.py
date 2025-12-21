from network.server import ServerThread
from network.client import Client

class Peer:
    def __init__(self):
        self.server = ServerThread()
        self.client = None

    def start_server(self):
        self.server.start()

    def connect(self, host, port):
        self.client = Client(host, port)

    def send(self, data):
        if self.client:
            self.client.send(data)
