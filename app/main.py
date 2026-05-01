import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.db.session import SessionLocal

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": settings.LOG_LEVEL,
        "handlers": ["console"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up %s [%s]", settings.PROJECT_NAME, settings.ENVIRONMENT)
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Database connection verified.")
    except Exception as e:
        logger.critical("Database connection failed on startup: %s", e)
        raise
    finally:
        db.close()
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="A production-ready URL shortener API built with FastAPI and PostgreSQL.",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [settings.BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


app.include_router(router)


@app.get("/health", tags=["Health"])
def health_check():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    finally:
        db.close()

    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }