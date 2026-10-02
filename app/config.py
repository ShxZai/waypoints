"""Settings, read from .env in the project folder (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

WEB_DIR = ROOT / "web"
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
NOTES_DIR = Path(os.getenv("NOTES_DIR", ROOT / "notes"))
DB_PATH = DATA_DIR / "waypoints.db"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Which route the teacher uses to reach Claude:
#   claude_code — your Claude subscription, through Claude Code's non-interactive mode
#   api         — an Anthropic API key (pay per use), set ANTHROPIC_API_KEY
TEACHER = os.getenv("TEACHER", "claude_code").strip().lower()

# Claude Code route: model alias + effort per task tier. "complex" is only used
# to draw up the plan; the fallback keeps it working on plans without Opus.
CC_MODELS = {
    "quick": (os.getenv("CC_MODEL_QUICK", "sonnet"), os.getenv("CC_EFFORT_QUICK", "low")),
    "default": (os.getenv("CC_MODEL_DEFAULT", "sonnet"), os.getenv("CC_EFFORT_DEFAULT", "high")),
    "complex": (os.getenv("CC_MODEL_COMPLEX", "opus"), os.getenv("CC_EFFORT_COMPLEX", "high")),
}
CC_FALLBACK_MODEL = os.getenv("CC_FALLBACK_MODEL", "sonnet")

# API route: model id + effort per task tier.
API_MODELS = {
    "quick": (os.getenv("API_MODEL_QUICK", "claude-sonnet-5"), "low"),
    "default": (os.getenv("API_MODEL_DEFAULT", "claude-sonnet-5"), "high"),
    "complex": (os.getenv("API_MODEL_COMPLEX", "claude-opus-5"), "high"),
}

RUN_TIMEOUT = float(os.getenv("RUN_TIMEOUT", "10"))
RUN_OUTPUT_CAP = 20_000
