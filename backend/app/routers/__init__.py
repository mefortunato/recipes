from app.routers.health import router as health_router
from app.routers.recipes import router as recipes_router
from app.routers.auth import router as auth_router

__all__ = ["health_router", "recipes_router", "auth_router"]
