import json
import os
from uuid import uuid4

class Config:
    # app_dir = os.path.dirname(os.path.abspath(__file__))
    # config_path = os.path.join(app_dir, "config.json")
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.host_ip = "0.0.0.0"    
        self.listen_port = 8080
        self.username = "anonymous"
        self.user_id = ""
    
    def load_config(self):
        try:
            with open(self.config_path, "r") as config_file:
                config_data = json.load(config_file)
                self.host_ip = config_data["host_ip"] if "host_ip" in config_data else "0.0.0.0"
                self.listen_port = config_data["listen_port"] if "listen_port" in config_data else 0
                self.username = config_data["username"] if "username" in config_data else ""
                self.user_id = config_data["user_id"] if "user_id" in config_data else str(uuid4())

        except FileNotFoundError:
            print(f"Error: The config file was not found at {self.config_path}")
  
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from the file at {self.config_path}")

    def save_config(self):
        config_data = {
            "host_ip": self.host_ip,
            "listen_port": self.listen_port,
            "username": self.username,
            "user_id": self.user_id
        }
        with open(self.config_path, "w") as f:
            # Use json.dump() to write the dictionary to the file
            json.dump(config_data, f, indent=4) # "indent=4" makes the file human-readable

        print(f"Dictionary successfully saved to {self.config_path}")