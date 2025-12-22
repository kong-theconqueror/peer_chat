import json
import time

def encode_message(sender, content):
    return json.dumps({
        "type": "MESSAGE",
        "sender": sender,
        "content": content,
        "timestamp": time.time()
    }).encode("utf-8")

def decode_message(data):
    return json.loads(data.decode("utf-8"))