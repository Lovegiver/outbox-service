from pathlib import Path

import yaml


class ConfigService:
    def __init__(self, config_path: str = "config/app.dev.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load()

    def _load(self) -> dict:
        with self.config_path.open(encoding="utf-8") as file:
            return yaml.safe_load(file)

    def get_max_delivery_attempts(self) -> int:
        return int(
            self.config
            .get("delivery", {})
            .get("max_attempts", 3)
        )