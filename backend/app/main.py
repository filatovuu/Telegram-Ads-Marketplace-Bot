import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import advertiser, auth, escrow, health, internal, market, me, metrics, owner
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import limiter
from app.db.session import engine
from app.services.deal_state_machine import InvalidTransitionError
from app.services.mtproto import stop_client as stop_mtproto

# Configure structured JSON logging before anything else
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: connect and disconnect from the database."""
    # Startup: attempt to verify the database connection
    try:
        async with engine.begin() as conn:
            pass  # connection pool is initialised
        logger.info("Database connection established")
    except Exception as exc:
        logger.warning("Database connection not available at startup: %s", exc)
    yield
    # Shutdown: disconnect MTProto client, then dispose of the connection pool
    await stop_mtproto()
    await engine.dispose()


app = FastAPI(
    title="Telegram Ads Marketplace API",
    description="REST API for the Telegram Ads Marketplace — channels, listings, deals, escrow.",
    version="1.0.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
    debug=settings.debug,
    lifespan=lifespan,
)

@app.get("/api/redoc", include_in_schema=False)
async def redoc_html() -> HTMLResponse:
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js",
    )


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS middleware — use configured origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
app.add_middleware(RequestLoggingMiddleware)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(InvalidTransitionError)
async def invalid_transition_handler(request: Request, exc: InvalidTransitionError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(internal.router, prefix="/api")
app.include_router(owner.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(advertiser.router, prefix="/api")
app.include_router(escrow.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
