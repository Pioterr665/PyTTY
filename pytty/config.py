import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "server_list.json"


def load_servers():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {"groups": []}
