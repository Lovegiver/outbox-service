from app.models.route_definition import RouteDefinition
from sqlalchemy import select
from sqlalchemy.orm import Session


class RouteRepository:

    def __init__(
        self,
        db: Session
    ):
        self.db = db

    def create(
        self,
        route: RouteDefinition
    ) -> RouteDefinition:

        self.db.add(route)
        self.db.commit()
        self.db.refresh(route)

        return route

    def save(
            self,
            route: RouteDefinition
    ) -> RouteDefinition:
        self.db.commit()
        self.db.refresh(route)

        return route

    def find_by_id(
        self,
        route_id: int
    ) -> RouteDefinition | None:

        statement = (
            select(RouteDefinition)
            .where(
                RouteDefinition.id == route_id
            )
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()

    def find_by_event_type(
        self,
        event_type_id: int
    ) -> list[RouteDefinition]:

        statement = (
            select(RouteDefinition)
            .where(
                RouteDefinition.event_type_id == event_type_id,
                RouteDefinition.is_active.is_(True)
            )
        )

        return list(
            self.db.execute(
                statement
            ).scalars().all()
        )

    def disable(
        self,
        route: RouteDefinition
    ) -> RouteDefinition:

        route.is_active = False

        self.db.commit()
        self.db.refresh(route)

        return route

    def delete(
        self,
        route: RouteDefinition
    ) -> None:

        self.db.delete(route)
        self.db.commit()