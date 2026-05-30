from pathlib import Path

import yaml
from app.schemas.routing_schema import DestinationConfig
from app.schemas.routing_schema import RoutingConfig


class RoutingService:

    def get_destinations(
            self,
            project: str
    ) -> list[DestinationConfig]:

        route_file = (
            Path("routes")
            / f"{project.lower()}.yaml"
        )

        if not route_file.exists():
            raise FileNotFoundError(
                f"No routing found for {project}"
            )

        with open(route_file, encoding="utf-8") as file:
            config = yaml.safe_load(file)

        routing = RoutingConfig.model_validate(config)

        return routing.destinations