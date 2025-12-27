from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, 
    QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem, QTextEdit, 
    QLineEdit, QPushButton, QAction
)

class ChatWindow(QMainWindow):
    def __init__(self, chat_manager):
        super().__init__()
        self.chat_manager = chat_manager

        self.setWindowTitle("Peer Chat")
        self.resize(900, 400)

        self.create_menu()
        self.create_ui()

        # chat
        self.selected_user = {}

        # events
        self.chat_manager.message_received.connect(self.message_handle)
        self.chat_manager.log_received.connect(self.log_handle)
        self.chat_manager.status.connect(self.status_hanndle)
        self.chat_manager.update_peers.connect(self.update_peer_list)

    # ---------- UI ----------
    def create_menu(self):
        self.menubar = self.menuBar()

        menu_config = self.menubar.addMenu("Config")
        menu_discover = self.menubar.addMenu("Discover")
        menu_about = self.menubar.addMenu("About")

        act_setting = QAction("Settings", self)
        act_exit = QAction("Exit", self)

        act_exit.triggered.connect(self.close)

        menu_config.addAction(act_setting)
        menu_config.addSeparator()
        menu_config.addAction(act_exit)

        act_find_nodes = QAction("Find Nodes", self)
        act_find_nodes.triggered.connect(self.chat_manager.find_nodes)
        menu_discover.addAction(act_find_nodes)

        menu_about.addAction("About App")

    def create_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        # self.chat_ui = QWidget()

        splitter = QSplitter(Qt.Horizontal)

        splitter.addWidget(self.create_node_panel())
        splitter.addWidget(self.create_chat_panel())
        splitter.addWidget(self.create_log_panel())

        splitter.setSizes([200, 500, 300])

        layout = QHBoxLayout(central)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(splitter)

        # self.chat_ui.setLayout(layout)
    
    def create_node_panel(self):
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("User List")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.node_list = QListWidget()
        # self.node_list.addItems(["Node A", "Node B", "Node C"])

        layout.addWidget(title)
        layout.addWidget(self.node_list)
        widget.setLayout(layout)
        return widget
    
    def create_chat_panel(self):
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Chat box")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)

        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type message...")
        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self.send_message)

        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.btn_send)

        layout.addWidget(title)
        layout.addWidget(self.chat_view)
        layout.addLayout(input_layout)

        widget.setLayout(layout)
        return widget
    
    def create_log_panel(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Logs")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        layout.addWidget(title)
        layout.addWidget(self.log_view)
        widget.setLayout(layout)
        return widget

    # ---------- Handlers ----------
    def send_message(self):
        msg = self.chat_input.text()
        self.chat_input.clear()
        self.chat_view.append(f'{self.chat_manager.config.username}: {msg}')
        # self.chat_manager.send_message(msg)
        self.chat_manager.send_broadcast_message(msg)

    def message_handle(self, msg):
        print("[NEW MESSAGE] ", msg)
        self.chat_view.append(f'{msg["from_n"]}: {msg["content"]}')

    def log_handle(self, log):
        self.log_view.append(f'{log["from_n"]}: {log["content"]}')
    
    def status_hanndle(self, log):
        self.log_view.append(log)
    
    def update_peer_list(self, peers):
        self.node_list.clear()
        for peer in peers:
            item = QListWidgetItem(f'{peer["username"]}')
            item.setData(Qt.UserRole, peer)
            self.node_list.addItem(item)

    def close(self):
        self.chat_manager.stop()
        super().__init__()
    