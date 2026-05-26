import os
import yaml
from dotenv import load_dotenv
from pathlib import Path


class ConfigService:
    def __init__(self, env: str | None = None):
        load_dotenv()
        self.env = env or os.getenv("OUTBOX_ENV", "dev")
        self.config_path = Path("config") / f"app.{self.env}.yaml"
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

    def get_worker_interval_seconds(self) -> int:
        return int(
            self.config
            .get("worker", {})
            .get("interval_seconds", 10)
        )

    def get_delivery_timeout_seconds(self) -> int:
        return int(
            self.config
            .get("delivery", {})
            .get("timeout_seconds", 5)
        )

    def get_retry_delay_seconds(self) -> int:
        return int(
            self.config
            .get("delivery", {})
            .get("retry_delay_seconds", 30)
        )