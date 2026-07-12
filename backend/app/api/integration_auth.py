import secrets

from fastapi import Header, HTTPException

from app.core.config import settings


def _expected_token(source_system: str) -> str:
    mapping = {
        "staff": settings.staff_integration_token,
        "command-center": settings.command_center_integration_token,
        "accounting": settings.accounting_integration_token,
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
