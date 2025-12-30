import os
import json
from uuid import uuid4
from core.db import ChatDatabase
# from core.neighbor import 

nodes = []
for i in range(0, 13):
    node_name = chr(ord('A')+ i)
    node = {
        "ip": '127.0.0.1',
        "port": 8080 + i,
        "username": f"user_{node_name}",
        "peer_id": str(uuid4()),
        "node": node_name,
        "ttl": 5
    }
    nodes.append(node)
    
node_map = [[0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
[1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0],
[1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0],
[1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
[0, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
[0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0],
[0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0],
[0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
[0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0],
[0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1],
[0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0],
[0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0],
[0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0]]

# generate config file
for node in nodes:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(app_dir, "config", f"{node['node']}.json")

    with open(config_path, "w") as f:
        # Use json.dump() to write the dictionary to the file
        json.dump(node, f, indent=4) # "indent=4" makes the file human-readable

    print(f"Dictionary successfully saved to {config_path}")

def insert_neighbor(conn, peer_id, username, ip, port, status=1):
    conn.execute("""
    INSERT INTO neighbor (peer_id, username, ip, port, status)
    VALUES (?, ?, ?, ?, ?)
    """, (peer_id, username, ip, port, status))
    conn.commit()

# generate db file
index = 0
for node in nodes:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(app_dir, "db", f"{node['node']}.db")

    chat_db = ChatDatabase(f"{node['node']}.db")
    chat_db.reset_db()
    print(f"Create DB successfully saved to {config_path}")

    # print(node_map[index])    
    for j in range(0, len(node_map[index])):
        # print("j", j)
        if node_map[index][j] == 1:
            insert_neighbor(chat_db.conn, nodes[j]["peer_id"], nodes[j]["username"], nodes[j]["ip"], nodes[j]["port"], 1)
    
    index += 1

