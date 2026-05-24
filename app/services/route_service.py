from app.models.route_definition import RouteDefinition
from app.repositories.route_repository import RouteRepository


class RouteService:

    def __init__(
        self,
        route_repository: RouteRepository
    ):
        self.route_repository = route_repository

    def create_route(
        self,
        event_type_id: int,
        routing_key: str,
        destination_name: str,
        destination_url: str
    ) -> RouteDefinition:

        route = RouteDefinition(
            event_type_id=event_type_id,
            routing_key=routing_key,
            destination_name=destination_name,
            destination_url=destination_url,
            enabled=True
        )

        return self.route_repository.create(route)

    def get_event_type_routes(
        self,
        event_type_id: int
    ) -> list[RouteDefinition]:

        return self.route_repository.find_by_event_type(event_type_id)

    def disable_route(
        self,
        route_id: int
    ) -> RouteDefinition:

        route = self.route_repository.find_by_id(route_id)

        if route is None:
            raise ValueError(
                f"Route {route_id} not found"
            )

        return self.route_repository.disable(route)