"""
FastAPI Main Application and API Gateway.
Registers all six module routers under /v1 and provides GET /health endpoint.
Enforces Request ID, Latency Logging, and Rate Limiting middlewares.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIDAndLatencyMiddleware, RateLimitMiddleware
from app.db.session import check_db_health
from app.core.redis import check_redis_health

# Module Routers
from app.modules.accounts.router import router as accounts_router
from app.modules.content.router import router as content_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.quiz.router import router as quiz_router
from app.modules.recommender.router import router as recommender_router
from app.modules.experiments.router import router as experiments_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENVIRONMENT} mode.")
    yield
    logger.info("Shutting down API server.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Stateless Modular Monolith Backend for Personalized Learning Path Recommender",
    lifespan=lifespan,
)

# Cross-cutting error handlers
register_error_handlers(app)

# Middlewares (Executed in reverse order of declaration)
app.add_middleware(RateLimitMiddleware, global_limit=120, login_limit=5, window_seconds=60)
app.add_middleware(RequestIDAndLatencyMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """
    GET /health endpoint.
    Verifies API, PostgreSQL, and Redis connectivity status.
    """
    db_up = check_db_health()
    redis_up = check_redis_health()
    all_healthy = db_up and redis_up

    response_payload = {
        "status": "healthy" if all_healthy else "degraded",
        "database": "up" if db_up else "down",
        "redis": "up" if redis_up else "down",
        "version": "1.0.0",
    }
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=response_payload)


# Register all 6 module routers under /v1
api_prefix = settings.API_V1_STR
app.include_router(accounts_router, prefix=api_prefix)
app.include_router(content_router, prefix=api_prefix)
app.include_router(knowledge_router, prefix=api_prefix)
app.include_router(quiz_router, prefix=api_prefix)
app.include_router(recommender_router, prefix=api_prefix)
app.include_router(experiments_router, prefix=api_prefix)
