from fastapi import APIRouter, Depends
from app.api.deps import require_permission
from app.schemas.common import ModuleStatus
router = APIRouter(tags=["modules"])
MODULES = {
    "items": ("items.read", "Item master and unit/category framework is ready for Pass 2."),
    "suppliers": ("suppliers.read", "Supplier registry framework is ready for Pass 3."),
    "locations": ("locations.read", "Storage location framework is ready for Pass 2."),
    "stock": ("inventory.read", "Stock ledger contract is defined; posting logic belongs to Pass 2."),
    "purchasing": ("procurement.read", "Requisition and purchase-order framework is ready for Pass 3."),
    "receiving": ("receiving.read", "Goods receiving framework is ready for Pass 3."),
    "counts": ("counts.create", "Physical-count framework is ready for Pass 2."),
    "reports": ("reports.read", "Reporting shell is ready; operational reports follow core transactions."),
    "integrations": ("reports.read", "Outbox/inbox integration contracts are documented for later passes."),
}
for name, (permission, message) in MODULES.items():
    def endpoint(n=name, m=message, _=Depends(require_permission(permission))):
        return ModuleStatus(module=n, message=m)
    router.add_api_route(f"/{name}", endpoint, methods=["GET"], response_model=ModuleStatus)
