import json
import os
from uuid import uuid4

class Config:
    def __init__(self, config_filename="config.json"):
        self.config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
        self.config_path = os.path.join(self.config_dir, config_filename)
        self.ip = "0.0.0.0"    
        self.port = 8080
        self.username = "anonymous"
        self.peer_id = ""
        self.node = ""
        self.ttl = 5
    
    def load_config(self):
        try:
            with open(self.config_path, "r") as config_file:
                config_data = json.load(config_file)
                self.ip = config_data["ip"] if "ip" in config_data else "0.0.0.0"
                self.port = config_data["port"] if "port" in config_data else 0
                self.username = config_data["username"] if "username" in config_data else ""
                self.peer_id = config_data["peer_id"] if "peer_id" in config_data else str(uuid4())
                self.node = config_data["node"] if "node" in config_data else ""
                
                print(f"[LOG] Config successfully load from {self.config_path}")

        except FileNotFoundError:
            print(f"[ERROR] The config file was not found at {self.config_path}")
  
        except json.JSONDecodeError:
            print(f"[ERROR] Could not decode JSON from the file at {self.config_path}")

    def save_config(self):
        config_data = {
            "ip": self.ip,
            "port": self.port,
            "username": self.username,
            "peer_id": self.peer_id,
            "node": self.node,
            "ttl": self.ttl
        }
        with open(self.config_path, "w") as f:
            # Use json.dump() to write the dictionary to the file
            json.dump(config_data, f, indent=4) # "indent=4" makes the file human-readable

        print(f"[LOG] Config successfully saved to {self.config_path}")