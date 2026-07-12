from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import SESSION_COOKIE_NAME, get_current_user
from app.core.config import settings
from app.core.roles import accessible_modules, permissions_for_role
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, SessionUserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.access_token_minutes * 60,
        expires=settings.access_token_minutes * 60,
        path="/",
        secure=settings.app_env.lower() == "production",
        httponly=True,
        samesite="lax",
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.email != email:
        user.email = email
        db.commit()
    token = create_access_token(user.id, user.role)
    _set_session_cookie(response, token)
    return LoginResponse(access_token=token, user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.app_env.lower() == "production",
        httponly=True,
        samesite="lax",
    )


@router.get("/me", response_model=SessionUserOut)
def me(user: User = Depends(get_current_user)):
    return SessionUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=permissions_for_role(user.role),
        accessible_modules=accessible_modules(user.role),
    )
