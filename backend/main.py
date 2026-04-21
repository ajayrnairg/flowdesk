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
# In production, you'd want to be more restrictive, but for Vercel previews, 
# we allow all .vercel.app subdomains.
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://flowdesk-g6bppjsua-ajones-projects-ed4b9177.vercel.app", # Main domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex="https://flowdesk-.*\.vercel\.app", # Allow all Vercel previews
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(notifications.router)

@app.api_route("/health", methods=["GET", "HEAD"], tags=["System"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}