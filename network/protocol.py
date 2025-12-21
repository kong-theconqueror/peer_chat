import json
import time

def make_message(sender, content):
    return json.dumps({
        "type": "MESSAGE",
        "sender": sender,
        "content": content,
        "timestamp": time.time()
    }).encode()

# {
#   "type": "MESSAGE",
#   "from": "peer_id",
#   "payload": "...",
#   "timestamp": 123456
# }