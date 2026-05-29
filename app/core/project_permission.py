from enum import StrEnum


class ProjectPermission(StrEnum):
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"

    EVENT_TYPE_READ = "event_type:read"
    EVENT_TYPE_WRITE = "event_type:write"

    SCHEMA_READ = "schema:read"
    SCHEMA_WRITE = "schema:write"

    ROUTE_READ = "route:read"
    ROUTE_WRITE = "route:write"

    API_KEY_READ = "api_key:read"
    API_KEY_WRITE = "api_key:write"

    METRICS_READ = "metrics:read"