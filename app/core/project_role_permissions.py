from app.core.auth_enums import ProjectMemberRole
from app.core.project_permission import ProjectPermission


PROJECT_ROLE_PERMISSIONS: dict[ProjectMemberRole, set[ProjectPermission]] = {
    ProjectMemberRole.OWNER: set(ProjectPermission),

    ProjectMemberRole.DEVELOPER: {
        ProjectPermission.PROJECT_READ,
        ProjectPermission.EVENT_TYPE_READ,
        ProjectPermission.EVENT_TYPE_WRITE,
        ProjectPermission.SCHEMA_READ,
        ProjectPermission.SCHEMA_WRITE,
        ProjectPermission.ROUTE_READ,
        ProjectPermission.ROUTE_WRITE,
        ProjectPermission.API_KEY_READ,
        ProjectPermission.API_KEY_WRITE,
        ProjectPermission.METRICS_READ,
        ProjectPermission.METRICS_WRITE,
    },

    ProjectMemberRole.VIEWER: {
        ProjectPermission.PROJECT_READ,
        ProjectPermission.EVENT_TYPE_READ,
        ProjectPermission.SCHEMA_READ,
        ProjectPermission.ROUTE_READ,
        ProjectPermission.API_KEY_READ,
        ProjectPermission.METRICS_READ,
    },
}