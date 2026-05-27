from app.dependencies import get_current_user, get_auth_service
from app.models import UserAccount
from app.schemas.auth_schema import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.jwt_service import JwtService
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
)
def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):

    try:
        user = auth_service.register(
            email=request.email,
            password=request.password,
        )

        return user

    except ValueError as ex:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):

    user = auth_service.authenticate(
        email=request.email,
        password=request.password,
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = JwtService.create_access_token(
        user
    )

    return TokenResponse(
        access_token=token
    )

@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    current_user: UserAccount = Depends(get_current_user),
):

    return current_user