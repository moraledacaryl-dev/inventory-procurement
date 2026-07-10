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

def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(Role(role), set())
    if "*" in permissions or permission in permissions:
        return True
    domain = permission.split(".", 1)[0]
    return f"{domain}.*" in permissions or "*.read" in permissions and permission.endswith(".read")
