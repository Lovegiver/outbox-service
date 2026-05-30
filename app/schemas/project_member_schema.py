from app.core.auth_enums import ProjectMemberRole
from pydantic import BaseModel


class ProjectMemberResponse(BaseModel):
    user_id: int
    email: str
    role: ProjectMemberRole

    model_config = {
        "from_attributes": True
    }


class AddProjectMemberRequest(BaseModel):
    email: str
    role: ProjectMemberRole


class UpdateProjectMemberRoleRequest(BaseModel):
    role: ProjectMemberRole