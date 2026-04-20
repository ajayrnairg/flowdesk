from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from core.database import engine
from routers import auth, tasks, notifications

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
        print("Successfully connected to the database.")
    except Exception as e:
        print(f"Database connection failed: {e}")
        
    yield # App runs and handles requests here
    
    # Shutdown gracefully
    await engine.dispose()
    print("Database connections closed.")


# Initialize FastAPI app
app = FastAPI(
    title="FlowDesk API",
    description="Backend for the FlowDesk productivity app",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "https://flowdesk-nhb5jehog-ajones-projects-ed4b9177.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(notifications.router)

@app.get("/health", tags=["System"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}