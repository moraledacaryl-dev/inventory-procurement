from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    INVENTORY_MANAGER = "inventory_manager"
    PROCUREMENT_OFFICER = "procurement_officer"
    RECEIVER = "receiver"
    COUNTER = "counter"
    VIEWER = "viewer"


ROLE_PERMISSIONS = {
    Role.OWNER: {"*"},
    Role.INVENTORY_MANAGER: {"inventory.*", "items.*", "locations.*", "counts.*", "reports.read"},
    Role.PROCUREMENT_OFFICER: {"procurement.*", "suppliers.*", "receiving.read", "reports.read"},
    Role.RECEIVER: {"receiving.*", "inventory.read", "procurement.read"},
    Role.COUNTER: {"counts.create", "counts.submit", "inventory.read"},
    Role.VIEWER: {"*.read"},
}


def permissions_for_role(role: str) -> list[str]:
    try:
        return sorted(ROLE_PERMISSIONS.get(Role(role), set()))
    except ValueError:
        return []


def has_permission(role: str, permission: str) -> bool:
    permissions = set(permissions_for_role(role))
    if "*" in permissions or permission in permissions:
        return True
    domain = permission.split(".", 1)[0]
    return f"{domain}.*" in permissions or "*.read" in permissions and permission.endswith(".read")


def accessible_modules(role: str) -> list[str]:
    modules = {
        "dashboard": "inventory.read",
        "items": "items.read",
        "locations": "locations.read",
        "stock": "inventory.read",
        "inventory-operations": "inventory.read",
        "counts": "counts.read",
        "suppliers": "suppliers.read",
        "purchasing": "procurement.read",
        "receiving": "receiving.read",
        "production": "inventory.read",
        "reports": "reports.read",
        "integrations": "reports.read",
        "readiness": "reports.read",
        "rollout": "reports.read",
    }
    return [module for module, permission in modules.items() if has_permission(role, permission)]
