import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("flowdesk")

from core.database import engine
from routers import auth, tasks, notifications, knowledge, search
from routers.collections import router as collections_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for startup and shutdown.
    Handles DB connection checks safely for serverless environments.
    """
    try:
        # Simple query to test the NeonDB connection pool on startup
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to the database.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        
    yield # App runs and handles requests here
    
    # Shutdown gracefully
    await engine.dispose()
    logger.info("Database connections closed.")


# Initialize FastAPI app
app = FastAPI(
    title="FlowDesk API",
    description="Backend for the FlowDesk productivity app",
    version="1.0.0",
    lifespan=lifespan
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    
    # Log everything except health checks to avoid noise
    if request.url.path != "/health":
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - {formatted_process_time}ms"
        )
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Server Error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please check logs for details."},
    )

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://flowdesk-g6bppjsua-ajones-projects-ed4b9177.vercel.app",
    "https://flowdesk-sand.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://flowdesk-.*\.vercel\.app", # Allow all Vercel previews
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(notifications.router)
app.include_router(knowledge.router)
app.include_router(collections_router)
app.include_router(search.router)

@app.api_route("/health", methods=["GET", "HEAD"], tags=["System"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}