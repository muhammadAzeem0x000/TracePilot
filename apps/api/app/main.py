import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config.settings import get_settings
from app.repositories.incidents import RepositoryError
from app.services.runtime import build_investigation_runtime

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.investigation_worker_enabled:
        yield
        return

    runtime = build_investigation_runtime(settings)
    application.state.investigation_runtime = runtime
    worker_task = asyncio.create_task(runtime.worker.run_forever())
    try:
        yield
    finally:
        await runtime.worker.stop()
        await worker_task


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="TracePilot API",
        version="0.4.0",
        description="Durable evidence-grounded incident investigation and evaluation.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    application.include_router(router)

    @application.exception_handler(RepositoryError)
    async def repository_error_handler(
        _request: Request,
        error: RepositoryError,
    ) -> JSONResponse:
        logger.exception("Incident persistence failed", exc_info=error)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Incident storage is temporarily unavailable"},
        )

    @application.exception_handler(RuntimeError)
    async def configuration_error_handler(
        _request: Request,
        error: RuntimeError,
    ) -> JSONResponse:
        logger.error("API configuration error: %s", error)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(error)},
        )

    return application


app = create_app()
