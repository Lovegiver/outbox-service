from enum import StrEnum


class AuthType(StrEnum):
    NONE = "NONE"
    API_KEY = "API_KEY"
    BEARER = "BEARER"