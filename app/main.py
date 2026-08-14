"""Brain OS Enterprise Workflow Platform -- FastAPI application entry point.

Run locally with:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack, asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langgraph.checkpoint.sqlite import SqliteSaver

from app.api.middleware import MaxBodySizeMiddleware
from app.api.rate_limit import RateLimiter
from app.api.routes import router
from app.database.connection import init_schema
from app.database.vector_store import VectorMemory
from app.services.document_intelligence import DocumentIntelligenceService
from app.services.executive_briefing import ExecutiveBriefingService
from app.services.notification_service import NotificationService
from app.services.risk_engine import RiskEngine
from app.utils.config import get_settings
from app.utils.logging import configure_logging, get_logger
from app.workflows.graph import WorkflowEngine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_data_dir()

    # Facility 3: Knowledge Memory -- schema is created automatically on startup.
    init_schema(settings.database_path)

    resources = ExitStack()
    checkpointer = resources.enter_context(SqliteSaver.from_conn_string(settings.checkpoint_db_path))
    vector_memory = VectorMemory(settings.chroma_persist_path, settings.chroma_collection_name)

    engine = WorkflowEngine(
        database_path=settings.database_path,
        checkpointer=checkpointer,
        document_intelligence=DocumentIntelligenceService(),
        risk_engine=RiskEngine(settings.auto_approve_threshold, settings.duplicate_similarity_threshold),
        vector_memory=vector_memory,
        briefing_service=ExecutiveBriefingService(settings.anthropic_api_key, settings.anthropic_model),
        notification_service=NotificationService(settings.slack_bot_token, settings.slack_approval_channel),
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.rate_limiter = RateLimiter(settings.rate_limit_max_requests, settings.rate_limit_window_seconds)

    logger.info(
        "%s starting up (environment=%s, db=%s)", settings.app_name, settings.environment, settings.database_path
    )
    try:
        yield
    finally:
        resources.close()
        logger.info("%s shut down cleanly.", settings.app_name)


def create_app() -> FastAPI:
    application = FastAPI(
        title="Brain OS Enterprise Workflow Platform",
        description="Document intake, risk-scored approval workflow, and executive briefing over invoice text.",
        version="0.1.0",
        lifespan=lifespan,
    )
    # Added at construction time (not in lifespan): Starlette requires
    # middleware to be registered before the app starts serving.
    application.add_middleware(MaxBodySizeMiddleware, max_bytes=get_settings().max_request_body_bytes)
    application.include_router(router)

    @application.get("/health", tags=["system"])
    def health(request: Request) -> JSONResponse:
        """Liveness/readiness probe: confirms the process is up AND its SQLite
        store is actually reachable, not just that FastAPI is responding."""
        settings = request.app.state.settings
        try:
            with sqlite3.connect(settings.database_path, timeout=2) as conn:
                conn.execute("SELECT 1")
        except sqlite3.Error:
            logger.error("Health check failed: database unreachable.", exc_info=True)
            return JSONResponse(
                {"status": "degraded", "service": settings.app_name, "database": "unreachable"}, status_code=503
            )
        return JSONResponse({"status": "ok", "service": settings.app_name, "database": "ok"})

    return application


app = create_app()
