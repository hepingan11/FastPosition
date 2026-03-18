import os
import sys
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, chat, company_links, default, positions, resume


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Fast resume delivery platform API",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(default.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(resume.router)
    app.include_router(positions.router)
    app.include_router(company_links.router)

    @app.on_event("startup")
    async def startup_event():
        init_db()
        app_port = os.getenv("APP_PORT", "8000")
        print(f"{settings.APP_NAME} API started")
        print(f"API docs: http://localhost:{app_port}/docs")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=os.getenv("APP_RELOAD", "true").lower() == "true",
    )
