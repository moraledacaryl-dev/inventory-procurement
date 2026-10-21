"""Enforce configured operational access scopes at financial and stock posting boundaries.

Owners retain their all-access authority. Unconfigured location scopes keep the
legacy role permissions until administrators assign explicit scopes; once scopes
are configured for an account, postings must match an active, compatible scope.
Unlike legacy location access, financial approvals always need an active
monetary authorization for non-owner accounts.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pass6 import OperationalAccessScope
from app.models.user import User


def _scope_rows(db: Session, user_id: str) -> list[OperationalAccessScope]:
    return list(db.scalars(select(OperationalAccessScope).where(
        OperationalAccessScope.user_id == user_id
    )).all())


def _unqualified_scope(scope: OperationalAccessScope) -> bool:
    # A department/workspace/record-class restriction must not turn into a
    # global authorization when the transaction lacks that dimension.
    return not (scope.workspace_id or scope.department_id or scope.record_class_id)


def require_scoped_locations(db: Session, user: User, location_ids: set[str]) -> None:
    if user.role == "owner" or not location_ids:
        return
    scopes = _scope_rows(db, user.id)
    if not scopes:
        # Preserve pre-scope installations; no location policy was assigned.
        return
    for location_id in location_ids:
        if not any(
            scope.is_active
            and _unqualified_scope(scope)
            and (scope.location_id is None or scope.location_id == location_id)
            for scope in scopes
        ):
            raise HTTPException(
                status_code=403,
                detail="Operational access scope does not authorize this location",
            )


def require_purchase_approval(
    db: Session,
    user: User,
    amount: Decimal,
    *,
    location_id: str | None = None,
) -> None:
    """Require an explicit non-owner monetary limit and matching location.

    Location-less requisitions cannot draw authority from a location-only
    scope. Approval limits are inclusive and never pooled across scope rows.
    """
    if user.role == "owner":
        return
    total = Decimal(amount)
    scopes = _scope_rows(db, user.id)
    if not any(
        scope.is_active
        and _unqualified_scope(scope)
        and Decimal(scope.approval_limit) >= total
        and (
            scope.location_id is None
            or (location_id is not None and scope.location_id == location_id)
        )
        for scope in scopes
    ):
        raise HTTPException(
            status_code=403,
            detail="An active operational scope with sufficient purchase approval limit is required",
        )
