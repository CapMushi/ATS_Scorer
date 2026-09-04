"""
ATS Scorer v2 — FastAPI Backend.
Main entry point.
"""

import os
import sys
import logging

# Ensure packages are importable from backend/
_this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _this_dir)
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import BACKEND_PORT, CORS_ORIGINS
from src.api.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === App Setup ===
app = FastAPI(title="ATS Scorer v2", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routes from the API module
app.include_router(router)

from src.api.email_routes import router as email_router
app.include_router(email_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT)
