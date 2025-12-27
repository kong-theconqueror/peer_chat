import json
import time
from uuid import uuid4

def encode_message(sender, receiver, content, forwarder="", sender_name="", receiver_name="", ttl=5, message_type="MESSAGE", message_id=str(uuid4())):
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
    return en_msg_str.encode("utf-8")

def decode_message(data):
    return json.loads(data.decode("utf-8"))