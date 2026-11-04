import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data Directory (supports Render persistent disk mount e.g. /var/data)
DATA_DIR = os.getenv("DATA_DIR", "").strip()
raw_db_path = os.getenv("DATABASE_PATH", "").strip()
raw_chroma_path = os.getenv("CHROMA_PATH", "").strip()

if DATA_DIR:
    if raw_db_path and os.path.isabs(raw_db_path):
        DATABASE = raw_db_path
    elif raw_db_path:
        DATABASE = os.path.join(DATA_DIR, os.path.basename(raw_db_path))
    else:
        DATABASE = os.path.join(DATA_DIR, "lost_found.db")

    if raw_chroma_path and os.path.isabs(raw_chroma_path):
        CHROMA_PATH = raw_chroma_path
    elif raw_chroma_path:
        CHROMA_PATH = os.path.join(DATA_DIR, os.path.basename(raw_chroma_path))
    else:
        CHROMA_PATH = os.path.join(DATA_DIR, "chroma_data")
else:
    DATABASE = raw_db_path if raw_db_path else os.path.join(BASE_DIR, "lost_found.db")
    CHROMA_PATH = raw_chroma_path if raw_chroma_path else os.path.join(BASE_DIR, "chroma_data")

# Matching thresholds
SIMILARITY_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.28"))
STRONG_MATCH_THRESHOLD = float(os.getenv("STRONG_MATCH_THRESHOLD", "0.65"))
POSSIBLE_MATCH_THRESHOLD = float(os.getenv("POSSIBLE_MATCH_THRESHOLD", "0.40"))

# Vector Store (ChromaDB) Configuration
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "items_rag")
CHROMA_TELEMETRY = os.getenv("CHROMA_TELEMETRY", "0").lower() in ("1", "true", "yes")

# Disable ChromaDB anonymous telemetry by default to avoid network timeouts / SSL errors on cloud hosts
if not CHROMA_TELEMETRY:
    os.environ["ANONYMIZED_TELEMETRY"] = "False"

# LLM Configuration (OpenAI primary, Gemini optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "10"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower().strip()  # "openai", "gemini", or "none"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "10"))

# Admin / Security
ADMIN_KEY = os.getenv("ADMIN_KEY", "campus_admin_secret_2026")
DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
