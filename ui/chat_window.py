import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QMenuBar, 
    QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QTextEdit, QLineEdit,
    QPushButton, QAction
)
from PyQt5.QtCore import Qt

class ChatWindow(QMainWindow):
    def __init__(self, chat_manager):
        super().__init__()
        self.chat_manager = chat_manager

        self.setWindowTitle("Peer Chat")
        self.resize(900, 400)

        self.create_menu()
        self.create_ui()

        # layout = QVBoxLayout()
        # layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(0)
        # layout.addWidget(self.menubar)
        # layout.addWidget(self.chat_ui)
        # self.setLayout(layout)

        self.chat_manager.message_received.connect(self.display_message)

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

        self.node_list = QListWidget()
        self.node_list.addItems(["Node A", "Node B", "Node C"])

        layout.addWidget(self.node_list)
        widget.setLayout(layout)
        return widget
    
    def create_chat_panel(self):
        widget = QWidget()
        layout = QVBoxLayout()

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)

        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type message...")
        self.btn_send = QPushButton("Send")

        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.btn_send)

        layout.addWidget(self.chat_view)
        layout.addLayout(input_layout)

        widget.setLayout(layout)
        return widget
    
    def create_log_panel(self):
        widget = QWidget()
        layout = QVBoxLayout()

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        layout.addWidget(self.log_view)
        widget.setLayout(layout)
        return widget

    def send_message(self):
        msg = self.chat_input.text()
        self.chat_input.clear()
        self.chat_manager.send_message(msg)

    def display_message(self, msg):
        self.log_view.append(msg)

    def close(self):
        self.chat_manager.stop()
        super().__init__()