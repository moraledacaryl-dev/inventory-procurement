from fastapi import APIRouter
from app.api.routes import auth, health, modules, inventory, procurement, operations, inventory_operations, production, readiness, stabilization
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(inventory.router)
api_router.include_router(procurement.router)
api_router.include_router(operations.router)
api_router.include_router(inventory_operations.router)
api_router.include_router(production.router)
api_router.include_router(readiness.router)
api_router.include_router(stabilization.router)
api_router.include_router(modules.router)
