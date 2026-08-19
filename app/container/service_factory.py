from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db

from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.event_delivery_repository import EventDeliveryRepository
from app.repositories.event_repository import EventRepository
from app.repositories.event_type_repository import EventTypeRepository
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.route_repository import RouteRepository
from app.repositories.schema_repository import SchemaRepository
from app.repositories.system_metric_repository import SystemMetricRepository
from app.repositories.metric_state_repository import MetricStateRepository
from app.repositories.user_repository import UserRepository
from app.services.api_key_service import ApiKeyService
from app.services.auth_service import AuthService
from app.services.config_service import ConfigService
from app.services.dead_letter_service import DeadLetterService
from app.services.delivery_service import DeliveryService
from app.services.event_ingress_service import EventIngressService
from app.services.event_type_service import EventTypeService
from app.services.project_member_service import ProjectMemberService
from app.services.project_service import ProjectService
from app.services.route_service import RouteService
from app.services.routing_service import RoutingService
from app.services.schema_service import SchemaService
from app.services.schema_validation_service import SchemaValidationService
from app.repositories.analytical_observation_repository import (
    AnalyticalObservationRepository,
)
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.repositories.processing_chain_repository import (
    ProcessingChainRepository,
)
from app.repositories.processing_plan_repository import (
    ProcessingPlanRepository,
)

from app.services.metric_definition_version_schema_service import (
    MetricDefinitionVersionSchemaService,
)
from app.services.metrics_extraction_service import (
    MetricsExtractionService,
)
from app.services.metric_state_aggregation_service import (
    MetricStateAggregationService,
)
from app.services.processing_chain_activation_service import (
    ProcessingChainActivationService,
)
from app.services.processing_chain_builder_service import (
    ProcessingChainBuilderService,
)
from app.services.processing_plan_provider import (
    ProcessingPlanProvider,
)
from app.services.metric_definition_admin_service import (
    MetricDefinitionAdminService,
)
from app.services.metric_builder_service import (
    MetricBuilderService,
)


# Ce fichier construit les objets métier Python
# Il ne connait pas FastAPI et est utilisable sans lui

class ServiceFactory:
    config_service = ConfigService()
    routing_service = RoutingService()
    delivery_service = DeliveryService(config_service=config_service)

    @classmethod
    def create_event_ingress_service(
            cls,
            db: Session,
    ) -> EventIngressService:
        event_repository = EventRepository(db)

        schema_repository = SchemaRepository(db)

        schema_validation_service = (
            SchemaValidationService(
                schema_repository=schema_repository
            )
        )

        return EventIngressService(
            db=db,
            event_repository=event_repository,
            schema_validation_service=schema_validation_service,
            metrics_extraction_service=(
                    cls.create_metrics_extraction_service(db)
            ),
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

    @classmethod
    def create_project_member_service(
        cls,
        db: Session,
    ) -> ProjectMemberService:
        return ProjectMemberService(
            project_repository=ProjectRepository(db),
            project_member_repository=ProjectMemberRepository(db),
            user_repository=UserRepository(db),
        )

    @classmethod
    def create_processing_chain_repository(
        cls,
        db: Session,
    ) -> ProcessingChainRepository:
        """
        Create the repository responsible for ProcessingChain persistence.
        """
        return ProcessingChainRepository(db)

    @classmethod
    def create_processing_plan_repository(
        cls,
        db: Session,
    ) -> ProcessingPlanRepository:
        """
        Create the repository responsible for ProcessingPlan persistence.
        """
        return ProcessingPlanRepository(db)

    @classmethod
    def create_processing_chain_builder_service(
        cls,
        db: Session,
    ) -> ProcessingChainBuilderService:
        """
        Create the service responsible for building ProcessingChain snapshots.
        """
        return ProcessingChainBuilderService(
            processing_chain_repository=(
                cls.create_processing_chain_repository(db)
            ),
            processing_plan_repository=(
                cls.create_processing_plan_repository(db)
            ),
            metric_definition_version_repository=(
                MetricDefinitionVersionRepository(db)
            ),
            schema_repository=SchemaRepository(db),
        )

    @classmethod
    def create_processing_chain_activation_service(
        cls,
        db: Session,
    ) -> ProcessingChainActivationService:
        """
        Create the service responsible for atomically activating
        analytical processing chains.
        """
        return ProcessingChainActivationService(
            db=db,
            processing_chain_repository=(
                cls.create_processing_chain_repository(db)
            ),
            processing_chain_builder_service=(
                cls.create_processing_chain_builder_service(db)
            ),
        )

    @classmethod
    def get_processing_chain_activation_service(
            cls,
            db: Session = Depends(get_db),
    ) -> ProcessingChainActivationService:
        return cls.create_processing_chain_activation_service(db)

    @classmethod
    def create_processing_plan_provider(
        cls,
        db: Session,
    ) -> ProcessingPlanProvider:
        """
        Create the runtime provider responsible for exposing compiled
        analytical processing plans.
        """
        return ProcessingPlanProvider(
            processing_chain_repository=(
                cls.create_processing_chain_repository(db)
            ),
            processing_plan_repository=(
                cls.create_processing_plan_repository(db)
            ),
        )

    @classmethod
    def create_metrics_extraction_service(
        cls,
        db: Session,
    ) -> MetricsExtractionService:
        """
        Create the runtime analytical extraction service.
        """
        return MetricsExtractionService(
            analytical_observation_repository=(
                AnalyticalObservationRepository(db)
            ),
            processing_plan_provider=(
                cls.create_processing_plan_provider(db)
            ),
        )

    @classmethod
    def create_metric_definition_version_schema_service(
        cls,
        db: Session,
    ) -> MetricDefinitionVersionSchemaService:
        """
        Create the service responsible for validating and registering
        YAML/schema compatibilities.
        """
        return MetricDefinitionVersionSchemaService(
            db=db,
            compatibility_repository=MetricDefinitionVersionSchemaRepository(db),
            metric_definition_version_repository=MetricDefinitionVersionRepository(db),
            schema_repository=SchemaRepository(db),
            processing_chain_activation_service=(
                cls.create_processing_chain_activation_service(db)
            ),
        )

    @classmethod
    def create_metric_definition_admin_service(
        cls,
        db: Session,
    ) -> MetricDefinitionAdminService:
        """
        Create the administrative service used to manage metric definitions
        and YAML metric definition versions.

        Args:
            db: SQLAlchemy session used by the service.

        Returns:
            A configured MetricDefinitionAdminService instance.
        """
        return MetricDefinitionAdminService(db)


    @classmethod
    def create_metric_builder_service(
        cls,
        db: Session,
    ) -> MetricBuilderService:
        """
        Create the business-oriented Metrics Builder service.

        Args:
            db: SQLAlchemy session used by repositories and admin services.

        Returns:
            Configured MetricBuilderService instance.
        """
        return MetricBuilderService(
            schema_repository=SchemaRepository(db),
            metric_definition_admin_service=(
                cls.create_metric_definition_admin_service(db)
            ),
        )

    @classmethod
    def create_metric_state_aggregation_service(
        cls,
        db: Session,
    ) -> MetricStateAggregationService:
        """
        Create the service responsible for materializing Prometheus metric state.

        Args:
            db: SQLAlchemy session used by repositories.

        Returns:
            Configured MetricStateAggregationService instance.
        """
        return MetricStateAggregationService(
            metric_state_repository=MetricStateRepository(db),
        )
