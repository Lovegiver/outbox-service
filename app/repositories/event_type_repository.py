from app.models.event_type import EventType
from sqlalchemy import select
from sqlalchemy.orm import Session


class EventTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, event_type: EventType) -> EventType:
        self.db.add(event_type)
        self.db.commit()
        self.db.refresh(event_type)
        return event_type

    def find_by_id(
        self,
        event_type_id: int,
        *,
        for_update: bool = False,
    ) -> EventType | None:
        """Return an EventType, optionally locking the stable Builder scope."""
        stmt = select(EventType).where(EventType.id == event_type_id)
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def find_by_project_id(self, project_id: int) -> list[EventType]:
        stmt = (
            select(EventType)
            .where(EventType.project_id == project_id)
            .order_by(EventType.code)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_project_id_and_code(
        self,
        project_id: int,
        code: str,
    ) -> EventType | None:
        stmt = select(EventType).where(
            EventType.project_id == project_id,
            EventType.code == code,
        )
        return self.db.execute(stmt).scalar_one_or_none()
