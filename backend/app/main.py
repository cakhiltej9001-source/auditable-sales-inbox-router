from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Sales Inbox Task Router", version="0.1.0")
    allowed_origins = [origin.strip().rstrip("/") for origin in settings.frontend_origin.split(",") if origin.strip()]
    if "http://localhost:5173" not in allowed_origins:
        allowed_origins.append("http://localhost:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()
