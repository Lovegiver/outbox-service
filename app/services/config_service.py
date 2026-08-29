import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


class ConfigService:
    def __init__(self, env: Optional[str] = None):
        load_dotenv()

        resolved_env = env or os.getenv("OUTBOX_ENV")

        if not resolved_env:
            raise RuntimeError("OUTBOX_ENV environment variable is required.")

        self.env = resolved_env
        self.config_path = Path("config") / f"app.{self.env}.yaml"
        self.config = self._load()

    def _load(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with self.config_path.open(encoding="utf-8") as file:
            return yaml.safe_load(file)

    def get_max_delivery_attempts(self) -> int:
        return int(self.config.get("delivery", {}).get("max_attempts", 3))

    def get_worker_interval_seconds(self) -> int:
        return int(self.config.get("worker", {}).get("interval_seconds", 10))

    def get_metric_execution_batch_size(self) -> int:
        """Return the maximum plan executions processed per worker cycle."""
        return int(
            self.config.get("metrics", {}).get("execution", {}).get("batch_size", 100)
        )

    def get_max_metric_execution_attempts(self) -> int:
        """Return the configured terminal attempt count for metric plans."""
        return int(
            self.config.get("metrics", {}).get("execution", {}).get("max_attempts", 3)
        )

    def get_metric_retry_initial_delay_seconds(self) -> int:
        """Return the initial delay for independent metric retries."""
        return int(
            self.config.get("metrics", {})
            .get("execution", {})
            .get("retry", {})
            .get("initial_delay_seconds", 5)
        )

    def get_metric_retry_max_delay_seconds(self) -> int:
        """Return the capped delay for independent metric retries."""
        return int(
            self.config.get("metrics", {})
            .get("execution", {})
            .get("retry", {})
            .get("max_delay_seconds", 600)
        )

    def get_metric_builder_limits(self) -> dict[str, int]:
        """Return bounded JSON Schema and Builder input limits."""
        builder = self.config.get("metrics", {}).get("builder", {})
        defaults = {
            "max_enum_values": 20,
            "max_labels": 5,
            "max_path_length": 512,
            "max_path_segments": 32,
            "max_schema_depth": 32,
            "max_schema_fields": 1000,
            "max_label_name_length": 128,
            "event_type_series_budget": 200,
            "event_type_series_warning": 160,
            "max_metric_series_estimate": 1_000_000,
        }
        limits: dict[str, int] = {}
        for name, default in defaults.items():
            value = builder.get(name, default)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("Metric Builder limits must be positive integers")
            limits[name] = value
        if any(value <= 0 for value in limits.values()):
            raise ValueError("Metric Builder limits must be positive integers")
        if limits["event_type_series_warning"] > limits["event_type_series_budget"]:
            raise ValueError("Metric Builder warning threshold exceeds its budget")
        if limits["max_metric_series_estimate"] < limits["event_type_series_budget"]:
            raise ValueError("Metric Builder estimate cap is below its budget")
        return limits

    def get_delivery_timeout_seconds(self) -> int:
        return int(self.config.get("delivery", {}).get("timeout_seconds", 5))

    def get_retry_delay_seconds(self) -> int:
        """Return the initial retry delay kept for legacy callers."""
        return int(
            self.config.get("delivery", {})
            .get("retry", {})
            .get("initial_delay_seconds", 5)
        )

    def get_retry_strategy(self) -> str:
        return str(
            self.config.get("delivery", {})
            .get("retry", {})
            .get("strategy", "exponential")
        )

    def get_retry_max_delay_seconds(self) -> int:
        return int(
            self.config.get("delivery", {})
            .get("retry", {})
            .get("max_delay_seconds", 600)
        )

    def is_retry_jitter_enabled(self) -> bool:
        return bool(
            self.config.get("delivery", {}).get("retry", {}).get("jitter", True)
        )

    def is_delivery_https_required(self) -> bool:
        return bool(
            self.config.get("delivery", {}).get("http", {}).get("require_https", False)
        )

    def get_destination_secret_provider(self) -> str:
        return str(
            self.config.get("security", {})
            .get("destination_secrets", {})
            .get("provider", "environment")
        )

    def get_jwt_secret_key(self) -> str:
        secret_key = os.getenv("OUTBOX_JWT_SECRET_KEY") or (
            self.config.get("security", {}).get("jwt", {}).get("secret_key")
        )

        if not secret_key:
            raise RuntimeError("security.jwt.secret_key is required.")

        if self.env == "prod" and str(secret_key).startswith("CHANGE_ME"):
            raise RuntimeError(
                "OUTBOX_JWT_SECRET_KEY must be configured in production."
            )

        return str(secret_key)

    def get_jwt_algorithm(self) -> str:
        return str(
            self.config.get("security", {}).get("jwt", {}).get("algorithm", "HS256")
        )

    def get_access_token_expire_minutes(self) -> int:
        return int(
            self.config.get("security", {})
            .get("jwt", {})
            .get("access_token_expire_minutes", 30)
        )

    def get_database_url(self) -> str:
        database_url = self.config.get("database", {}).get("url")

        if not database_url:
            raise RuntimeError("database.url is required in application configuration.")

        return str(database_url)
