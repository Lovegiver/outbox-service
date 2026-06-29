from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.services.config_service import ConfigService


class Base(DeclarativeBase):
    pass


def create_database_engine() -> Engine:
    """
    Create the SQLAlchemy engine from the active application configuration.

    The active environment is resolved by ConfigService through OUTBOX_ENV.
    """
    config_service = ConfigService()

    return create_engine(
        config_service.get_database_url(),
        echo=False,
    )


def create_session_factory(
    database_engine: Engine,
) -> sessionmaker[Session]:
    """
    Create a SQLAlchemy session factory bound to the provided engine.

    Args:
        database_engine: SQLAlchemy engine used by created sessions.

    Returns:
        A configured SQLAlchemy session factory.
    """
    return sessionmaker(
        bind=database_engine,
        autoflush=False,
        autocommit=False,
    )


engine = create_database_engine()

SessionLocal = create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    """
    Provide a SQLAlchemy session for FastAPI dependencies.

    Yields:
        A SQLAlchemy session bound to the configured database engine.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()