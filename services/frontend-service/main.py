# Frontend Service - Static file server for UI
import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Second-Brain Frontend Service",
    version="1.0"
)

# Get API URL from environment variable
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8001')

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check endpoint for frontend service"""
    return {"status": "healthy", "service": "frontend"}

# ---------------------------------------------------------------------------
# Static Files and Frontend
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/config.js")
async def serve_config():
    """Serve configuration as JavaScript"""
    config_js = f"""
// Auto-generated configuration
window.APP_CONFIG = {{
    apiBaseUrl: '{API_BASE_URL}'
}};
"""
    return HTMLResponse(content=config_js, media_type="application/javascript")

@app.get("/")
async def serve_frontend():
    """Serve the main frontend HTML file"""
    return FileResponse("index.html")

@app.get("/login.html")
async def serve_login():
    """Serve the login page"""
    return FileResponse("login.html")

@app.get("/test-auth.html")
async def serve_test_auth():
    """Serve the authentication test page"""
    return FileResponse("test-auth.html")

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )