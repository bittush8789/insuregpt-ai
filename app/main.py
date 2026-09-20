"""
InsureGPT Main Application Entrypoint.
Initializes FastAPI, configures CORS, mounts API routers, and serves the ChatGPT-style frontend.
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.mysql import init_db, get_db
from app.api import chat, conversations, documents

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes database on startup."""
    print(f"[{settings.app_name}] Initializing MySQL database connection...")
    db_ok = init_db()
    if db_ok:
        print(f"[{settings.app_name}] Database and tables successfully verified.")
    else:
        print(f"[{settings.app_name}] WARNING: Database initialization encountered errors.")
    yield
    print(f"[{settings.app_name}] Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="ChatGPT-style Insurance AI Assistant based on Hybrid RAG + Agentic RAG + Memory + AI Guardrails.",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(documents.router)


@app.get("/api/health", tags=["Health"], status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint verifying server and database operational readiness."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Mount Frontend Static Assets
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        """Serve the ChatGPT-style frontend index.html."""
        return FileResponse(os.path.join(frontend_dir, "index.html"))
