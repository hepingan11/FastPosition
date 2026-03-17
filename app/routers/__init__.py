from app.routers.chat import router as chat_router
from app.routers.default import router as default_router
from app.routers.resume import router as resume_router
from app.routers.positions import router as positions_router
from app.routers.auth import router as auth_router
from app.routers.company_links import router as company_links_router

__all__ = ["chat_router", "default_router", "resume_router", "positions_router", "auth_router", "company_links_router"]