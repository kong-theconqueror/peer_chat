import json
import time
from uuid import uuid4
import struct

def encode_message(sender, receiver, content, forwarder="", sender_name="", receiver_name="", ttl=5, message_type="MESSAGE", message_id=None):
    # Ensure a new message_id is generated per call if not provided
    if message_id is None:
        message_id = str(uuid4())

    en_msg_str = json.dumps({
        "type": message_type,
        "from": sender,
        "from_n": sender_name,
        "forward": forwarder,
        "to": receiver,
        "to_n": receiver_name,
        "message_id": message_id,
        "content": content,
        "ttl": ttl,
        "timestamp": int(time.time())
    })
    print(en_msg_str)
    
    # Length-prefix protocol: 4-byte big-endian length + UTF-8 JSON
    msg_bytes = en_msg_str.encode("utf-8")
    msg_len = len(msg_bytes)
    return struct.pack("!I", msg_len) + msg_bytes

def decode_message(data):
    """Legacy decode - expects single message only"""
    return json.loads(data.decode("utf-8"))

class MessageBuffer:
    """Handle multiple messages in one TCP recv() call using length-prefix protocol"""
    def __init__(self):
        self.buffer = b""
    
    def add_data(self, raw_bytes):
        """Add received data to buffer"""
        self.buffer += raw_bytes
    
    def extract_message(self):
        """Extract one complete message from buffer, return (msg_dict, remaining_buffer)
        Returns None if incomplete message"""
        if len(self.buffer) < 4:
            return None  # Need at least 4 bytes for length
        
        # Read 4-byte length (big-endian)
        msg_len = struct.unpack("!I", self.buffer[:4])[0]
        
        # Check if we have the full message
        if len(self.buffer) < 4 + msg_len:
            return None  # Incomplete message, wait for more data
        
        # Extract message and update buffer
        msg_bytes = self.buffer[4:4+msg_len]
        self.buffer = self.buffer[4+msg_len:]
        
        try:
            msg = json.loads(msg_bytes.decode("utf-8"))
            return msg
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[PROTOCOL_ERROR] Failed to decode message: {e}")
            # Skip this malformed message and try next
            return None
    
    def has_complete_message(self):
        """Check if buffer has at least one complete message"""
        if len(self.buffer) < 4:
            return False
        msg_len = struct.unpack("!I", self.buffer[:4])[0]
        return len(self.buffer) >= 4 + msg_len
    
    def get_all_messages(self):
        """Extract all complete messages from buffer, return list"""
        messages = []
        while self.has_complete_message():
            msg = self.extract_message()
            if msg is not None:
                messages.append(msg)
        return messages