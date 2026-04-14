import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


class ConfigManager:
    def __init__(self):
        self._data = {"mod_path": "", "vanilla_path": ""}
        self.load()

    def load(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=""):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    @property
    def mod_path(self):
        return self._data.get("mod_path", "")

    @property
    def vanilla_path(self):
        return self._data.get("vanilla_path", "")
