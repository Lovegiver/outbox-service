from pathlib import Path

import yaml


class RoutingService:

    def get_destinations(
            self,
            project: str
    ) -> list[dict]:

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

        return config["destinations"]