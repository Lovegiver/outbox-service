from app.models.route_definition import RouteDefinition
from app.repositories.route_repository import RouteRepository
from app.core.auth_type import AuthType


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
        destination_url: str,
        auth_type: AuthType = AuthType.NONE,
        auth_config: dict | None = None,
        secret_ref: str | None = None,
    ) -> RouteDefinition:

        route = RouteDefinition(
            event_type_id=event_type_id,
            routing_key=routing_key,
            destination_name=destination_name,
            destination_url=destination_url,
            is_active=True,
            auth_type=auth_type,
            auth_config=auth_config,
            secret_ref=secret_ref,
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

    def update_route(
            self,
            route_id: int,
            routing_key: str | None = None,
            destination_name: str | None = None,
            destination_url: str | None = None,
            auth_type: AuthType | None = None,
            auth_config: dict | None = None,
            secret_ref: str | None = None,
    ) -> RouteDefinition:

        route = self.route_repository.find_by_id(
            route_id
        )

        if route is None:
            raise ValueError(
                f"Route {route_id} not found"
            )

        if routing_key is not None:
            route.routing_key = routing_key

        if destination_name is not None:
            route.destination_name = destination_name

        if destination_url is not None:
            route.destination_url = destination_url

        if auth_type is not None:
            route.auth_type = auth_type

        if auth_config is not None:
            route.auth_config = auth_config

        if secret_ref is not None:
            route.secret_ref = secret_ref

        return self.route_repository.save(
            route
        )
