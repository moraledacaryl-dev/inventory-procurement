import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User


def _expected_token(source_system: str) -> str:
    mapping = {
        "staff": settings.staff_integration_token,
        "command-center": settings.command_center_integration_token,
        "accounting": settings.accounting_integration_token,
        "hidden-oasis-pos": settings.pos_integration_token,
    }
    return mapping.get(source_system, "")


def require_integration_token(source_system: str, supplied_token: str | None) -> None:
    expected = _expected_token(source_system)
    if not expected:
        raise HTTPException(503, f"Integration credential is not configured for {source_system}")
    if not supplied_token or not secrets.compare_digest(supplied_token, expected):
        raise HTTPException(401, "Invalid integration credential")


def integration_token_header(x_integration_token: str | None = Header(default=None)) -> str | None:
    return x_integration_token


def require_integration_actor(source_system: str):
    def dependency(
        token: str | None = Depends(integration_token_header),
        db: Session = Depends(get_db),
    ) -> User:
        require_integration_token(source_system, token)
        actor = db.scalar(
            select(User)
            .where(User.is_active.is_(True), User.role == "owner")
            .order_by(User.created_at.asc())
        )
        if not actor:
            raise HTTPException(503, "Integration posting principal is not configured")
        return actor
    return dependency
