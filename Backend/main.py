"""
BITBYBIT — Autonomous AI Payment & Project Agent
═════════════════════════════════════════════════
FastAPI entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db

# Import routes
from routes.auth import router as auth_router
from routes.employer import router as employer_router
from routes.freelancer import router as freelancer_router
from routes.escrow import router as escrow_router
from routes.ai import router as ai_router
from routes.pfi import router as pfi_router
from routes.content import router as content_router
from routes.design import router as design_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    await init_db()
    yield
    # Shutdown: nothing needed


app = FastAPI(
    title="BITBYBIT — Autonomous AI Payment Agent",
    description="AI-powered intermediary for freelance project management, escrow, and quality assurance.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# ── Mount routers ────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(employer_router)
app.include_router(freelancer_router)
app.include_router(escrow_router)
app.include_router(ai_router)
app.include_router(pfi_router)
app.include_router(content_router)
app.include_router(design_router)


# ── Health check ─────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "BITBYBIT",
        "status": "operational",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
