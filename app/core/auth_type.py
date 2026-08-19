from enum import StrEnum


class AuthType(StrEnum):
    NONE = "NONE"
    API_KEY_HEADER = "API_KEY_HEADER"
    BEARER_TOKEN = "BEARER_TOKEN"

    # Legacy values kept readable for existing persisted routes.
    API_KEY = "API_KEY"
    BEARER = "BEARER"
