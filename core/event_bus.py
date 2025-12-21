from PyQt5.QtCore import QObject, pyqtSignal

class EventBus(QObject):
    message_received = pyqtSignal(str)
