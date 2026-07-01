from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.password_service import PasswordService
from tests.domain.persisted_object import (
    PersistedEvent,
    PersistedEventType,
    PersistedProject,
    PersistedProjectMember,
    PersistedSchemaDefinition,
    PersistedUserAccount,
)
from tests.domain.record import (
    EventRecord,
    EventTypeRecord,
    ProjectMemberRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
    UserAccountRecord,
)
from tests.infrastructure.object_factory import ObjectFactory


@dataclass(frozen=True)
class ProjectMemberSeed:
    project: PersistedProject
    user: PersistedUserAccount
    membership: PersistedProjectMember


@dataclass(frozen=True)
class MinimalEventGraphSeed:
    project: PersistedProject
    event_type: PersistedEventType
    schema_definition: PersistedSchemaDefinition
    event: PersistedEvent


class Seed:
    def __init__(self, factory: ObjectFactory):
        self.factory = factory

    def project_registered(
        self,
        name: str,
        description: str | None = None,
        project_status: str = "active",
    ) -> PersistedProject:
        return self.factory.project(
            ProjectRecord(
                name=name,
                description=description,
                is_active=(project_status == "active"),
            )
        )

    def project_member_registered(
        self,
        project: PersistedProject,
        user: PersistedUserAccount,
        role: str,
    ) -> PersistedProjectMember:
        return self.factory.project_member(
            ProjectMemberRecord(
                project=project,
                user=user,
                role=role,
            )
        )

    def project_with_member(
        self,
        role: str = "OWNER",
        project_name: str = "Hermes",
        user_email: str = "user@example.test",
    ) -> ProjectMemberSeed:
        project = self.factory.project(
            ProjectRecord(name=project_name)
        )

        user = self.factory.user_account(
            UserAccountRecord(email=user_email)
        )

        membership = self.factory.project_member(
            ProjectMemberRecord(
                project=project,
                user=user,
                role=role,
            )
        )

        return ProjectMemberSeed(
            project=project,
            user=user,
            membership=membership,
        )

    def project_owner(
        self,
        project_name: str = "Hermes",
        user_email: str = "owner@example.test",
    ) -> ProjectMemberSeed:
        return self.project_with_member(
            role="OWNER",
            project_name=project_name,
            user_email=user_email,
        )

    def project_developer(
        self,
        project_name: str = "Hermes",
        user_email: str = "developer@example.test",
    ) -> ProjectMemberSeed:
        return self.project_with_member(
            role="DEVELOPER",
            project_name=project_name,
            user_email=user_email,
        )

    def project_viewer(
        self,
        project_name: str = "Hermes",
        user_email: str = "viewer@example.test",
    ) -> ProjectMemberSeed:
        return self.project_with_member(
            role="VIEWER",
            project_name=project_name,
            user_email=user_email,
        )

    def minimal_event_graph(
        self,
        project_name: str = "Hermes",
        event_type_code: str = "article.analyzed",
        event_type_name: str = "Article analyzed",
        json_schema: Optional[dict] = None,
        payload: Optional[dict] = None,
    ) -> MinimalEventGraphSeed:
        project = self.factory.project(
            ProjectRecord(name=project_name)
        )

        event_type = self.factory.event_type(
            EventTypeRecord(
                project=project,
                code=event_type_code,
                name=event_type_name,
            )
        )

        schema_definition = self.factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema=json_schema or {"type": "object"},
            )
        )

        event = self.factory.event(
            EventRecord(
                event_type=event_type,
                schema_definition=schema_definition,
                payload=payload or {"duration_seconds": 12.3},
            )
        )

        return MinimalEventGraphSeed(
            project=project,
            event_type=event_type,
            schema_definition=schema_definition,
            event=event,
        )

    def user_registered(
        self,
        email: str,
        password: str,
        global_role: str = "USER",
        account_status: str = "active",
    ):
        return self.factory.user_account(
            UserAccountRecord(
                email=email,
                password_hash=PasswordService.hash_password(password),
                role=global_role,
                is_active=(account_status == "active"),
            )
        )
