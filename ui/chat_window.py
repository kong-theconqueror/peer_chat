from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, 
    QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem, QTextEdit, 
    QLineEdit, QPushButton, QAction, QDialog, QDialogButtonBox
)
import datetime

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
        # UI interactions
        self.node_list.itemClicked.connect(self.on_peer_selected)

        # Load recent broadcasts into the chat view (persisted messages)
        try:
            self.load_initial_messages()
        except Exception:
            pass

    # ---------- UI ----------
    def create_menu(self):
        self.menubar = self.menuBar()

        menu_config = self.menubar.addMenu("Config")
        menu_discover = self.menubar.addMenu("Discover")
        menu_about = self.menubar.addMenu("About")

        act_setting = QAction("Settings", self)
        act_exit = QAction("Exit", self)

        act_setting.triggered.connect(self.show_settings)
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

    def _format_timestamp(self, ts):
        """Format timestamp for display.
        Accepts int (epoch seconds), float, datetime objects, or string timestamp from DB and returns
        a human-readable string 'YYYY-MM-DD HH:MM:SS'."""
        try:
            # datetime object
            if isinstance(ts, datetime.datetime):
                return ts.strftime('%Y-%m-%d %H:%M:%S')
            # date object
            if isinstance(ts, datetime.date):
                return datetime.datetime.combine(ts, datetime.time()).strftime('%Y-%m-%d %H:%M:%S')
            # If integer epoch seconds
            if isinstance(ts, int):
                # epoch seconds -> local time
                return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            # If float
            if isinstance(ts, float):
                return datetime.datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
            # If string, try to parse common formats
            if isinstance(ts, str):
                # Common SQLite default: 'YYYY-MM-DD HH:MM:SS' (stored as UTC)
                try:
                    # remove timezone if present
                    ts_clean = ts.split('+')[0].strip()
                    parsed = datetime.datetime.strptime(ts_clean, '%Y-%m-%d %H:%M:%S')
                    # Treat parsed DB string as UTC and convert to local timezone for display
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
                    return parsed.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    # fallback: return original string
                    return ts
        except Exception:
            pass
        return ''
    
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

    def show_settings(self):
        """Open a modal dialog showing current peer config and neighbors."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings / Node Info")
        dlg_layout = QVBoxLayout()

        # Peer info
        peer_label = QLabel(f"Peer ID: {self.chat_manager.config.peer_id}")
        port_label = QLabel(f"Port: {self.chat_manager.config.port}")
        username_label = QLabel(f"Username: {self.chat_manager.config.username}")

        dlg_layout.addWidget(peer_label)
        dlg_layout.addWidget(port_label)
        dlg_layout.addWidget(username_label)

        # Neighbors list
        ntitle = QLabel("Neighbors")
        ntitle.setStyleSheet("font-weight: bold; margin-top: 8px;")
        dlg_layout.addWidget(ntitle)

        neighbors_list = QListWidget()
        try:
            neighbors = self.chat_manager.db.get_neighbors()
            for n in neighbors:
                # Show basic neighbor info (peer id, ip:port) without status
                item_text = f"{n.get('username') or n.get('peer_id')[:8]} — {n.get('peer_id')} @ {n.get('ip')}:{n.get('port')}"
                neighbors_list.addItem(item_text)
        except Exception as e:
            neighbors_list.addItem(f"Failed to load neighbors: {e}")

        dlg_layout.addWidget(neighbors_list)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        dlg_layout.addWidget(buttons)

        dlg.setLayout(dlg_layout)
        dlg.exec_()

    # ---------- Handlers ----------
    def send_message(self):
        msg = self.chat_input.text()
        self.chat_input.clear()

        ts = self._format_timestamp(datetime.datetime.now())

        # If a peer is selected, send a direct message; otherwise broadcast
        if self.selected_user and self.selected_user.get("peer_id"):
            peer_id = self.selected_user.get("peer_id")
            self.chat_view.append(f'[{ts}] {self.chat_manager.config.username}: {msg}')
            self.chat_manager.send_message(peer_id, msg)
        else:
            self.chat_view.append(f'[{ts}] {self.chat_manager.config.username}: {msg}')
            self.chat_manager.send_broadcast_message(msg)

    def message_handle(self, msg):
        print("[NEW MESSAGE] ", msg)
        # Append to view and persist handled by ChatManager (show timestamp)
        ts = self._format_timestamp(msg.get("timestamp"))
        name = msg.get("from_n") or self.chat_manager.db.get_username(msg.get("from"))
        self.chat_view.append(f'[{ts}] {name}: {msg.get("content", "")}')

    def on_peer_selected(self, item):
        peer = item.data(Qt.UserRole)
        peer_id = (peer or {}).get("peer_id")

        # Toggle behavior: click the same peer again to clear selection (back to broadcast)
        if self.selected_user and self.selected_user.get("peer_id") == peer_id:
            self.selected_user = {}
            try:
                self.load_initial_messages()
            except Exception:
                pass
            return

        self.selected_user = peer
        self.load_conversation(peer_id)

    def load_conversation(self, peer_id):
        # Load conversation between local node and peer_id
        try:
            self.chat_view.clear()
            conv = self.chat_manager.db.get_conversation(self.chat_manager.config.peer_id, peer_id)
            for sender, receiver, content, timestamp, sender_name, receiver_name in conv:
                ts = self._format_timestamp(timestamp)
                if sender == self.chat_manager.config.peer_id:
                    name = self.chat_manager.config.username
                else:
                    name = sender_name or self.chat_manager.db.get_username(sender)
                self.chat_view.append(f"[{ts}] {name}: {content}")
        except Exception as e:
            print(f"[UI_ERROR] load_conversation failed: {e}")

    def load_initial_messages(self):
        # Show broadcasts (receiver empty) as general history
        try:
            self.chat_view.clear()
            bcs = self.chat_manager.db.get_broadcasts()
            for mid, sender, sender_name, receiver, receiver_name, content, timestamp, is_sent in bcs:
                ts = self._format_timestamp(timestamp)
                if sender == self.chat_manager.config.peer_id:
                    name = self.chat_manager.config.username
                else:
                    name = sender_name or self.chat_manager.db.get_username(sender)
                self.chat_view.append(f"[{ts}] {name}: {content}")
        except Exception as e:
            print(f"[UI_ERROR] load_initial_messages failed: {e}")

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
        # Ensure ChatManager and its resources are shutdown cleanly
        try:
            self.chat_manager.stop()
        except Exception:
            pass
        # Call parent's close to close the window
        super().close()
    