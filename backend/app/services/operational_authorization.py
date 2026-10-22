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


def visible_location_ids(db: Session, user: User) -> set[str] | None:
    """Return visible locations; None means unrestricted, empty set denies all.

    An Owner or an account with no assigned scope retains existing role-based
    visibility. Once configured, only active, unqualified scopes confer
    location visibility; an inactive scope never falls back to all locations.
    """
    if user.role == "owner":
        return None
    scopes = _scope_rows(db, user.id)
    if not scopes:
        return None
    active = [row for row in scopes if row.is_active and _unqualified_scope(row)]
    if any(row.location_id is None for row in active):
        return None
    return {row.location_id for row in active if row.location_id is not None}


def require_scoped_locations(db: Session, user: User, location_ids: set[str]) -> None:
    if not location_ids:
        return
    allowed = visible_location_ids(db, user)
    if allowed is not None and not location_ids.issubset(allowed):
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


def require_requisition_location(db: Session, user: User, location_id: str | None) -> None:
    """Protect requisitions and their quotations using authoritative ownership.

    An unassigned historical requisition does not belong to an arbitrary
    location. Owners and never-configured role accounts retain legacy access;
    explicitly scoped accounts must have an active matching location.
    """
    allowed = visible_location_ids(db, user)
    if allowed is not None and (location_id is None or location_id not in allowed):
        raise HTTPException(
            status_code=403,
            detail="Operational access scope does not authorize this requisition location",
        )


def require_global_operational_access(db: Session, user: User) -> None:
    """Global records with no authoritative location require broad access.

    Caller must first hold the route's role-level permission. Owners, legacy
    unassigned users and explicitly unrestricted accounts retain that role
    permission; users assigned only specific locations cannot inspect or
    mutate financial/integration records without trustworthy location links.
    """
    if visible_location_ids(db, user) is not None:
        raise HTTPException(
            status_code=403,
            detail="Global operational records require unrestricted location access",
        )
