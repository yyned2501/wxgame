import json


def read_config():
    with open("config.json", "r") as f:
        config = json.loads(f.read())
    return config


DOMAIN = "冒险大作战"
