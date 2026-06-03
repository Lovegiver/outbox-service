from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.processing_chain import ProcessingChain
from app.repositories.processing_chain_repository import (
    ProcessingChainRepository,
)
from app.services.processing_chain_builder_service import (
    ProcessingChainBuilderService,
)


class ProcessingChainActivationService:
    def __init__(
        self,
        db: Session,
        processing_chain_repository: ProcessingChainRepository,
        processing_chain_builder_service: (
            ProcessingChainBuilderService
        ),
    ) -> None:
        self.db = db

        self.processing_chain_repository = (
            processing_chain_repository
        )

        self.processing_chain_builder_service = (
            processing_chain_builder_service
        )

    def rebuild_and_activate_chain(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> ProcessingChain:

        current_active_chain = (
            self.processing_chain_repository.find_active(
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )
        )

        new_chain = (
            self.processing_chain_builder_service.build_chain(
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )
        )

        now = datetime.now(timezone.utc)

        if current_active_chain is not None:
            current_active_chain.is_active = False
            current_active_chain.status = "RETIRED"
            current_active_chain.valid_to = now

        new_chain.is_active = True
        new_chain.status = "ACTIVE"
        new_chain.valid_from = now
        new_chain.activated_at = now

        self.db.flush()

        return new_chain