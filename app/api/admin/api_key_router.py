from app.core.project_permission import ProjectPermission
from app.dependencies import (
    get_api_key_service,
    require_project_permission,
)
from app.models import UserAccount
from app.schemas.api_key_schema import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRead,
)
from app.services.api_key_service import ApiKeyService
from fastapi import APIRouter, Depends, status, HTTPException

router = APIRouter(
    prefix="/api/admin/projects/{project_id}/api-keys",
    tags=["admin-api-keys"],
)


@router.post(
    "",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    project_id: int,
    payload: ApiKeyCreate,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.API_KEY_WRITE
        )
    ),
    api_key_service: ApiKeyService = Depends(
        get_api_key_service
    ),
):
    created = api_key_service.create_api_key(
        project_id=project_id,
        name=payload.name,
    )

    return ApiKeyCreated(
        id=created.api_key.id,
        project_id=created.api_key.project_id,
        name=created.api_key.name,
        key_prefix=created.api_key.key_prefix,
        api_key=created.plain_key,
    )

@router.get(
    "",
    response_model=list[ApiKeyRead],
)
def list_api_keys(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.API_KEY_READ
        )
    ),
    api_key_service: ApiKeyService = Depends(
        get_api_key_service
    ),
):
    return api_key_service.list_api_keys(
        project_id
    )

@router.patch(
    "/{api_key_id}/revoke",
    response_model=ApiKeyRead,
)
def revoke_api_key(
    project_id: int,
    api_key_id: int,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.API_KEY_WRITE
        )
    ),
    api_key_service: ApiKeyService = Depends(
        get_api_key_service
    ),
):
    try:
        return api_key_service.revoke_api_key(
            project_id=project_id,
            api_key_id=api_key_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

@router.post(
    "/{api_key_id}/rotate",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
def rotate_api_key(
    project_id: int,
    api_key_id: int,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.API_KEY_WRITE
        )
    ),
    api_key_service: ApiKeyService = Depends(
        get_api_key_service
    ),
):
    try:
        created = api_key_service.rotate_api_key(
            project_id=project_id,
            api_key_id=api_key_id,
        )

        return ApiKeyCreated(
            id=created.api_key.id,
            project_id=created.api_key.project_id,
            name=created.api_key.name,
            key_prefix=created.api_key.key_prefix,
            api_key=created.plain_key,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc