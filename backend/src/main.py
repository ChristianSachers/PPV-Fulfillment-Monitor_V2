from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Import routers
from src.routes.uploads import router as uploads_router
from src.routes.upload_processing import router as upload_processing_router

# Load environment variables
load_dotenv()

# Create FastAPI app instance
app = FastAPI(
    title="PPV Fulfillment Monitor API",
    description="Data science web application for PPV fulfillment monitoring and analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(uploads_router)
app.include_router(upload_processing_router)

@app.get("/")
async def root():
    """Root endpoint providing API information."""
    return {
        "message": "Welcome to PPV Fulfillment Monitor API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring service status."""
    return {
        "status": "healthy",
        "service": "PPV Fulfillment Monitor API",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)