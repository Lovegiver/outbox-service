import os
import yaml

from dotenv import load_dotenv
from pathlib import Path
from typing import Optional


class ConfigService:
    def __init__(self, env: Optional[str] = None):
        load_dotenv()

        resolved_env = env or os.getenv("OUTBOX_ENV")

        if not resolved_env:
            raise RuntimeError(
                "OUTBOX_ENV environment variable is required."
            )

        self.env = resolved_env
        self.config_path = Path("config") / f"app.{self.env}.yaml"
        self.config = self._load()

    def _load(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )

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

    def get_database_url(self) -> str:
        database_url = (
            self.config
            .get("database", {})
            .get("url")
        )

        if not database_url:
            raise RuntimeError(
                "database.url is required in application configuration."
            )

        return str(database_url)