"""Transactional construction and activation of metric processing snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.processing_chain import ProcessingChain
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.processing_chain_repository import ProcessingChainRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_definition_admin_service import (
    MetricConfigurationNotFoundError,
    MetricConfigurationScopeError,
)
from app.services.processing_chain_builder_service import (
    PreparedProcessingChain,
    ProcessingChainBuilderService,
)
from app.services.processing_chain_errors import (
    ProcessingChainConflictError,
    ProcessingChainIncompleteError,
    ProcessingChainNotFoundError,
)


class ProcessingChainActivationService:
    """Own build/activation transactions and serialize each schema scope."""

    def __init__(
        self,
        db: Session,
        processing_chain_repository: ProcessingChainRepository,
        processing_plan_repository: ProcessingPlanRepository,
        metric_definition_version_repository: MetricDefinitionVersionRepository,
        schema_repository: SchemaRepository,
        processing_chain_builder_service: ProcessingChainBuilderService,
    ) -> None:
        self.db = db
        self.processing_chain_repository = processing_chain_repository
        self.processing_plan_repository = processing_plan_repository
        self.metric_definition_version_repository = (
            metric_definition_version_repository
        )
        self.schema_repository = schema_repository
        self.processing_chain_builder_service = processing_chain_builder_service

    def rebuild_and_activate_chain(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> ProcessingChain:
        """Explicitly rebuild and atomically activate the selected snapshot."""
        schema_definition = self.schema_repository.find_by_id(schema_definition_id)
        self._validate_schema_scope(
            schema_definition=schema_definition,
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )

        try:
            locked_schema = self.schema_repository.find_by_id(
                schema_definition_id,
                for_update=True,
            )
            self._validate_schema_scope(
                schema_definition=locked_schema,
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )
            selected_versions = (
                self.metric_definition_version_repository
                .find_latest_compatible_versions(
                    event_type_id=event_type_id,
                    schema_definition_id=schema_definition_id,
                )
            )
            prepared = self.processing_chain_builder_service.prepare_chain(
                event_type_id=event_type_id,
                schema_definition=locked_schema,
                metric_definition_versions=selected_versions,
            )
            current_active = self.processing_chain_repository.find_active(
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )
            if self._matches(current_active, prepared):
                self.db.commit()
                return current_active

            chain = self.processing_chain_builder_service.persist_chain(
                prepared=prepared,
                version_number=(
                    self.processing_chain_repository.find_next_version_number(
                        event_type_id=event_type_id,
                        schema_definition_id=schema_definition_id,
                    )
                ),
            )
            self._activate_locked(chain, current_active=current_active)
            self.db.commit()
            self.db.refresh(chain)
            return chain
        except IntegrityError as exc:
            self.db.rollback()
            raise ProcessingChainConflictError(
                "ProcessingChain activation conflicted with another transaction"
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def activate_chain(
        self,
        event_type_id: int,
        schema_definition_id: int,
        processing_chain_id: int,
    ) -> ProcessingChain:
        """Atomically activate one complete DRAFT candidate."""
        try:
            schema_definition = self.schema_repository.find_by_id(
                schema_definition_id,
                for_update=True,
            )
            self._validate_schema_scope(
                schema_definition=schema_definition,
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )
            chain = self.processing_chain_repository.find_by_id(
                processing_chain_id
            )
            if chain is None:
                raise ProcessingChainNotFoundError(
                    f"ProcessingChain {processing_chain_id} not found"
                )
            if (
                chain.event_type_id != event_type_id
                or chain.schema_definition_id != schema_definition_id
            ):
                raise MetricConfigurationScopeError(
                    "ProcessingChain belongs to another EventType or schema"
                )
            if chain.is_active and chain.status == "ACTIVE":
                self.db.commit()
                return chain
            if chain.status != "DRAFT":
                raise ProcessingChainIncompleteError(
                    f"ProcessingChain {chain.id} is not an activatable DRAFT"
                )

            plans = self.processing_plan_repository.list_by_chain_id(chain.id)
            if not plans or any(
                not plan.is_active or plan.compiled_plan_json is None
                for plan in plans
            ):
                raise ProcessingChainIncompleteError(
                    f"ProcessingChain {chain.id} has incomplete ProcessingPlans"
                )

            current_active = self.processing_chain_repository.find_active(
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )
            self._activate_locked(chain, current_active=current_active)
            self.db.commit()
            self.db.refresh(chain)
            return chain
        except IntegrityError as exc:
            self.db.rollback()
            raise ProcessingChainConflictError(
                "ProcessingChain activation conflicted with another transaction"
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def _activate_locked(
        self,
        chain: ProcessingChain,
        *,
        current_active: ProcessingChain | None,
    ) -> None:
        """Switch active rows while the stable schema row is locked."""
        now = datetime.now(timezone.utc)
        if current_active is not None and current_active.id != chain.id:
            current_active.is_active = False
            current_active.status = "RETIRED"
            current_active.valid_to = now
            # The partial unique index is immediate. Flush retirement first while
            # retaining both state changes in the same database transaction.
            self.db.flush()
        chain.is_active = True
        chain.status = "ACTIVE"
        chain.valid_from = now
        chain.valid_to = None
        chain.activated_at = now
        self.db.flush()

    def _matches(
        self,
        current_active: ProcessingChain | None,
        prepared: PreparedProcessingChain,
    ) -> bool:
        """Return whether an explicit rebuild is functionally idempotent."""
        if current_active is None:
            return False
        current_plans = self.processing_plan_repository.list_by_chain_id(
            current_active.id
        )
        if not current_plans or any(
            not plan.is_active or plan.compiled_plan_json is None
            for plan in current_plans
        ):
            return False
        return (
            self.processing_chain_builder_service.signature_for_chain(
                current_active.id
            )
            == prepared.signature
        )

    @staticmethod
    def _validate_schema_scope(
        schema_definition,
        event_type_id: int,
        schema_definition_id: int,
    ) -> None:
        if schema_definition is None:
            raise MetricConfigurationNotFoundError(
                f"SchemaDefinition {schema_definition_id} not found"
            )
        if schema_definition.event_type_id != event_type_id:
            raise MetricConfigurationScopeError(
                "SchemaDefinition belongs to another EventType"
            )
