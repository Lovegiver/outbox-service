import re

from pydantic import BaseModel, EmailStr, Field, field_validator


def normalize_email(value: str) -> str:
    return value.strip().lower()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=32,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_address(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        requirements = (
            (r"[A-Z]", "an uppercase letter"),
            (r"[a-z]", "a lowercase letter"),
            (r"[0-9]", "a digit"),
            (r"[^A-Za-z0-9]", "a special character"),
        )
        missing = [label for pattern, label in requirements if not re.search(pattern, value)]
        if missing:
            raise ValueError("Password must contain " + ", ".join(missing))
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=72,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_address(cls, value: str) -> str:
        return normalize_email(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str

    model_config = {
        "from_attributes": True
    }
