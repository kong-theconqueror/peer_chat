import sys
import html
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, 
    QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QTextEdit, QLineEdit,
    QPushButton, QAction, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer

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

        # chat
        self.selected_user = {}

        # events
        self.chat_manager.message_received.connect(self.message_handle)
        self.chat_manager.log_received.connect(self.log_handle)
        self.chat_manager.status.connect(self.status_hanndle)

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
        # self.node_list.addItems(["Node A", "Node B", "Node C"])
        self.node_list.itemClicked.connect(self.on_node_selected)

        layout.addWidget(self.node_list)
        widget.setLayout(layout)

        # refresh node list periodically so it reflects connected clients
        self.node_list_timer = QTimer(self)
        self.node_list_timer.timeout.connect(self.update_node_list)
        self.node_list_timer.start(1000)

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
        self.btn_send.clicked.connect(self.send_message)

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
        msg = self.chat_input.text().strip()
        if not msg:
            return

        # determine selected peer
        peer_id = getattr(self, 'selected_peer_id', None)
        if not peer_id:
            self.log_view.append("Select a peer to send message to.")
            return

        self.chat_input.clear()
        try:
            self.chat_manager.send_message(peer_id, msg)
            # render the message on the right (owner)
            self.append_me(msg)
        except Exception as e:
            self.log_view.append(f"Failed to send: {e}")

    def message_handle(self, msg):
        # display incoming message using HTML renderer
        try:
            sender = ''
            content = ''
            if isinstance(msg, dict):
                sender = msg.get('from_n') or msg.get('from', '')
                content = msg.get('content', '')
            else:
                content = str(msg)

            self.append_other(sender, content)
        except Exception as e:
            self.log_view.append(f"Error in message_handle: {e}")

    def append_other(self, sender, msg):
        """Render another user's message (left aligned) using simple HTML/CSS styles."""
        try:
            safe_sender = html.escape(sender[:8]) if sender else ''
            safe_msg = html.escape(msg).replace('\n', '<br>')
            html_msg = f"""
<div style="background:#f1f1f1;padding:8px 12px;border-radius:10px;margin:6px;max-width:70%;float:left;clear:both;">
<b>{safe_sender}</b><br>
{safe_msg}
</div>
"""
            self.chat_view.append(html_msg)
        except Exception as e:
            self.log_view.append(f"Error in append_other: {e}")

    def append_me(self, msg):
        """Render my message (right aligned) using simple HTML/CSS styles."""
        try:
            safe_msg = html.escape(msg).replace('\n', '<br>')
            html_msg = f"""
<div style="background:#dcf8c6;padding:8px 12px;border-radius:10px;margin:6px;max-width:70%;float:right;clear:both;text-align:right;">
{safe_msg}
</div>
"""
            self.chat_view.append(html_msg)
        except Exception as e:
            self.log_view.append(f"Error in append_me: {e}")

    def log_handle(self, log):
        # Accept either a dict with from_n/content or a plain string
        if isinstance(log, dict):
            self.log_view.append(f'{log.get("from_n","")}: {log.get("content","")}')
            return

        # try to parse JSON string
        try:
            import json
            parsed = json.loads(log)
            if isinstance(parsed, dict):
                self.log_view.append(f'{parsed.get("from_n","")}: {parsed.get("content","")}')
                return
        except Exception:
            pass

        # fallback: show raw string
        self.log_view.append(str(log))
    
    def status_hanndle(self, log):
        self.log_view.append(log)

    def update_node_list(self):
        # Refresh node list to reflect current clients in ChatManager
        # Rebuild items to show live connection status
        self.node_list.clear()
        for key, obj in self.chat_manager.clients.items():
            worker = obj.get("worker")
            status = "online" if getattr(worker, 'running', False) else "offline"
            text = f"{key[:8]} - {status}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.node_list.addItem(item)

    def on_node_selected(self, item):
        # read real peer id from item data
        self.selected_peer_id = item.data(Qt.UserRole)
        self.log_view.append(f"Selected peer: {self.selected_peer_id}")

    def closeEvent(self, event):
        if hasattr(self, 'chat_manager') and self.chat_manager:
            self.chat_manager.stop()
        super().closeEvent(event)
    