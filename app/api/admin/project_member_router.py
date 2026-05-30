from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_project_permission
from app.models import UserAccount
from app.schemas.project_member_schema import (
    AddProjectMemberRequest,
    ProjectMemberResponse,
    UpdateProjectMemberRoleRequest,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/admin/projects/{project_id}/members",
    tags=["admin-project-members"],
)


@router.get("", response_model=list[ProjectMemberResponse])
def list_members(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.PROJECT_READ
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_member_service(db)

    try:
        memberships = service.list_members(project_id)

        return [
            ProjectMemberResponse(
                user_id=membership.user_id,
                email=membership.user.email,
                role=membership.role,
            )
            for membership in memberships
        ]

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post("", response_model=ProjectMemberResponse)
def add_member(
    project_id: int,
    request: AddProjectMemberRequest,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.PROJECT_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_member_service(db)

    try:
        membership = service.add_member(
            project_id=project_id,
            email=request.email,
            role=request.role,
        )

        return ProjectMemberResponse(
            user_id=membership.user_id,
            email=membership.user.email,
            role=membership.role,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.patch("/{user_id}/role", response_model=ProjectMemberResponse)
def update_member_role(
    project_id: int,
    user_id: int,
    request: UpdateProjectMemberRoleRequest,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.PROJECT_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_member_service(db)

    try:
        membership = service.update_member_role(
            project_id=project_id,
            user_id=user_id,
            role=request.role,
        )

        return ProjectMemberResponse(
            user_id=membership.user_id,
            email=membership.user.email,
            role=membership.role,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.delete("/{user_id}", status_code=204)
def remove_member(
    project_id: int,
    user_id: int,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.PROJECT_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_member_service(db)

    try:
        service.remove_member(
            project_id=project_id,
            user_id=user_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc