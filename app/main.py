from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.routes import requests, ai
from app.services.database import init_database

app = FastAPI(title="Procurement Request System")

# Initialize database on startup
init_database()

# Include routers
app.include_router(requests.router)
app.include_router(ai.router)


@app.get("/")
async def root():
    """Serve the frontend"""
    return FileResponse("static/index.html")


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")
