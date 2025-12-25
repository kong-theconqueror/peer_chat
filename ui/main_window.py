import os
from PyQt5.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout,
    QWidget, QLabel, QComboBox, QLineEdit, QMessageBox
)
from ui.chat_window import ChatWindow
from core.chat_manager_2 import ChatManager
from utils.config import Config
from core.db import ChatDatabase

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Peer Chat")
        self.resize(300, 200)
        self.app_config = {}

        self.chat_manager = None

        self.lbl_node = QLabel("Select Node:")
        self.combo_node = QComboBox()
        self.combo_node.addItems([chr(c) for c in range(ord('A'), ord('M') + 1)])
        self.combo_node.currentTextChanged.connect(self.on_node_changed)

        self.lbl_user = QLabel("Username:")
        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Enter your username")

        self.btn_open_chat = QPushButton("Start Chat")
        self.btn_open_chat.clicked.connect(self.open_chat)

        layout = QVBoxLayout()
        layout.addWidget(self.lbl_node)
        layout.addWidget(self.combo_node)
        layout.addWidget(self.lbl_user)
        layout.addWidget(self.input_user)
        layout.addWidget(self.btn_open_chat)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def on_node_changed(self, text):
        print(f"[LOG] Selected node: {text}")
        #load config from file
        self.app_config = Config(f'{text}.json')
        self.app_config.load_config()

        self.input_user.setText(self.app_config.username)

    def open_chat(self):
        username = self.input_user.text().strip()

        if not username:
            QMessageBox.warning(self, "Error", "Username is required!")
            return
        else:
            self.app_config.username = username
            self.app_config.save_config()
            
            self.chat_manager = ChatManager(self.app_config)
            self.chat_manager.start()
        
        self.chat_window = ChatWindow(self.chat_manager)
        self.chat_window.setWindowTitle(f'Peer Chat - Node {self.app_config.node}')
        self.chat_window.show()

