"""
Centralized configuration for ATS Scorer v2 backend.
Loads environment variables and defines runtime constants.
ALL scoring constants live here — this is the single source of truth.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Also try loading from backend/ directory itself
_env_local = Path(__file__).resolve().parent / ".env"
if _env_local.exists():
    load_dotenv(_env_local, override=True)


# === LLM API Keys ===
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS: list[str] = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",")] if os.getenv("GROQ_API_KEYS") else ([GROQ_API_KEY] if GROQ_API_KEY else [])
LLM_DISABLED: bool = os.getenv("LLM_DISABLED", "false").lower() == "true"

# === Backend Config ===
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8001"))
CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001", "https://ats-scorer-tau.vercel.app"]

# === Model Config ===
EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

# === LLM Rate Limits ===
GROQ_RPM: int = 30
GEMINI_RPM: int = 15
LLM_RETRY_DELAY_SECONDS: float = 5.0
LLM_INTER_CALL_DELAY_SECONDS: float = 12.5  # 12.5s gap = safe for 5 RPM

# === Processing Limits ===
MAX_CVS_PER_BATCH: int = 30

# === Scoring Weights (Fixed — not exposed to frontend) ===
VECTOR_WEIGHT: float = 0.6
BM25_WEIGHT: float = 0.4
SKILLS_SECTION_WEIGHT: float = 0.35
RECENT_EXP_WEIGHT: float = 0.45
OLDER_EXP_WEIGHT: float = 0.20

# === BM25 Config ===
BM25_SATURATION_MULTIPLIER: float = 0.45   # Fixed saturation, no batch-size dependency
BM25_MIN_DUMMY_DOCS: int = 15              # Dummy docs for IDF stability

# === Calibration Anchors ===
CALIBRATION_FLOOR: float = 0.10
CALIBRATION_CEILING: float = 0.52

# === Penalty Config ===
MUST_HAVE_PENALTY_SEVERITY: float = 0.85   # 0 skills matched = lose 85% of score
NICE_TO_HAVE_BONUS_MAX: float = 0.05
