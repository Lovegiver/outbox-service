from collections.abc import Callable
from fastapi import Depends, HTTPException
from fastapi import Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session
from starlette import status
from typing import Optional

from app.container.service_factory import ServiceFactory
from app.core.auth_enums import UserRole
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.models import UserAccount
from app.models.api_key import ApiKey
from app.services.api_key_service import ApiKeyService
from app.services.auth_service import AuthService
from app.services.event_ingress_service import EventIngressService
from app.services.event_type_service import EventTypeService
from app.services.jwt_service import JwtService

bearer_scheme = HTTPBearer()

# Ce fichier est lié à FastAPI
# Il injecte FastAPI

def get_auth_service(
        db: Session = Depends(get_db)
) -> AuthService:
    return ServiceFactory.create_auth_service(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserAccount:

    token = credentials.credentials

    try:
        payload = JwtService.decode_token(token)

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id_raw = payload.get("sub")

    if not isinstance(
            user_id_raw,
            str,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user_id = int(
        user_id_raw
    )

    user = auth_service.find_user_by_id(user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def get_event_ingress_service(
        db: Session = Depends(get_db)
) -> EventIngressService:
    return ServiceFactory.create_event_ingress_service(db)

def require_admin(
    current_user: UserAccount = Depends(
        get_current_user
    ),
) -> UserAccount:

    if current_user.role != UserRole.ADMIN:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return current_user

def require_project_permission(
    permission: ProjectPermission,
) -> Callable:

    def dependency(
        project_id: int,
        current_user: UserAccount = Depends(
            get_current_user
        ),
        auth_service: AuthService = Depends(
            get_auth_service
        ),
    ) -> UserAccount:

        if current_user.role == UserRole.ADMIN:
            return current_user

        has_permission = auth_service.has_project_permission(
            user_id=current_user.id,
            project_id=project_id,
            permission=permission,
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient project permissions",
            )

        return current_user

    return dependency

def require_project_permission_from_payload(
    permission: ProjectPermission,
) -> Callable:

    def dependency(
        payload,
        current_user: UserAccount = Depends(get_current_user),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> UserAccount:

        if current_user.role == UserRole.ADMIN:
            return current_user

        has_permission = auth_service.has_project_permission(
            user_id=current_user.id,
            project_id=payload.project_id,
            permission=permission,
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient project permissions",
            )

        return current_user

    return dependency

def require_event_type_permission(
    permission: ProjectPermission,
) -> Callable:

    def dependency(
        event_type_id: int,
        current_user: UserAccount = Depends(get_current_user),
        auth_service: AuthService = Depends(get_auth_service),
        event_type_service: EventTypeService = Depends(get_event_type_service),
    ) -> UserAccount:

        try:
            event_type = event_type_service.get_event_type(event_type_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

        if current_user.role == UserRole.ADMIN:
            return current_user

        has_permission = auth_service.has_project_permission(
            user_id=current_user.id,
            project_id=event_type.project_id,
            permission=permission,
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient project permissions",
            )

        return current_user

    return dependency

def get_api_key_service(
        db: Session = Depends(get_db),
) -> ApiKeyService:

    return ServiceFactory.create_api_key_service(
        db
    )

def get_current_api_key(
    x_api_key: Optional[str] = Header(
        default=None,
        alias="X-API-Key",
    ),
    api_key_service: ApiKeyService = Depends(
        get_api_key_service,
    ),
) -> ApiKey:

    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    api_key = (
        api_key_service.authenticate_api_key(
            x_api_key
        )
    )

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return api_key

def get_event_type_service(
        db: Session = Depends(get_db),
) -> EventTypeService:
    return ServiceFactory.create_event_type_service(db)