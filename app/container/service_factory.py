from app.repositories.event_type_repository import EventTypeRepository
from app.services.event_type_service import EventTypeService
from sqlalchemy.orm import Session

from app.repositories.event_delivery_repository import EventDeliveryRepository
from app.repositories.event_repository import EventRepository
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.route_repository import RouteRepository
from app.repositories.schema_repository import SchemaRepository
from app.repositories.system_metric_repository import SystemMetricRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.config_service import ConfigService
from app.services.dead_letter_service import DeadLetterService
from app.services.delivery_service import DeliveryService
from app.services.event_service import EventService
from app.services.project_service import ProjectService
from app.services.route_service import RouteService
from app.services.routing_service import RoutingService
from app.services.schema_service import SchemaService
from app.services.schema_validation_service import SchemaValidationService
from app.repositories.api_key_repository import ApiKeyRepository
from app.services.api_key_service import ApiKeyService


# Ce fichier construit les objets métier Python
# Il ne connait pas FastAPI et est utilisable sans lui

class ServiceFactory:
    config_service = ConfigService()
    routing_service = RoutingService()
    delivery_service = DeliveryService()

    @classmethod
    def create_event_service(
            cls,
            db: Session,
    ) -> EventService:
        event_repository = EventRepository(db)

        schema_repository = SchemaRepository(db)

        schema_validation_service = (
            SchemaValidationService(
                schema_repository=schema_repository
            )
        )

        return EventService(
            db=db,
            event_repository=event_repository,
            schema_validation_service=schema_validation_service,
        )

    @classmethod
    def create_project_service(
            cls,
            db: Session
    ) -> ProjectService:
        project_repository = ProjectRepository(db)
        project_member_repository = ProjectMemberRepository(db)

        return ProjectService(
            project_repository=project_repository,
            project_member_repository=project_member_repository,
        )

    @classmethod
    def create_event_type_service(
            cls,
            db: Session,
    ) -> EventTypeService:
        return EventTypeService(
            event_type_repository=EventTypeRepository(db),
            project_repository=ProjectRepository(db),
        )

    @classmethod
    def create_route_service(
            cls,
            db: Session
    ) -> RouteService:
        repository = RouteRepository(db)
        return RouteService(
            route_repository=repository
        )

    @classmethod
    def create_schema_service(
            cls,
            db: Session
    ) -> SchemaService:
        repository = SchemaRepository(db)
        return SchemaService(
            schema_repository=repository
        )

    @classmethod
    def create_event_delivery_repository(
            cls,
            db: Session
    ) -> EventDeliveryRepository:
        return EventDeliveryRepository(db)

    @staticmethod
    def create_system_metric_repository(
            db: Session,
    ) -> SystemMetricRepository:
        return SystemMetricRepository(db)

    @classmethod
    def create_auth_service(
            cls,
            db: Session,
    ) -> AuthService:
        user_repository = UserRepository(db)

        project_member_repository = (
            ProjectMemberRepository(db)
        )

        return AuthService(
            user_repository=user_repository,
            project_member_repository=project_member_repository,
        )

    @classmethod
    def create_api_key_service(
            cls,
            db: Session,
    ) -> ApiKeyService:
        api_key_repository = ApiKeyRepository(db)

        return ApiKeyService(
            api_key_repository=api_key_repository,
        )

    @classmethod
    def create_dead_letter_service(
            cls,
            db: Session,
    ) -> DeadLetterService:
        return DeadLetterService(
            db=db,
            repository=EventDeliveryRepository(db),
        )

