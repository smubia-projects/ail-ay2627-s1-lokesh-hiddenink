"""Runtime configuration, read from environment variables only.

Secrets (the LLM API key, the Upstash token) are never hard-coded or logged.
"""
import os
from pathlib import Path


def _load_dotenv() -> None:
    """Read backend/.env for local development. Real environment variables always win."""
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5.4-mini")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-5.4")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "low")  # set empty for non-reasoning models
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))
# Cheaper model for tasks where quality barely matters: the classifier (its regex floor still wins) and the
# Red-Team payload writer. The screeners keep OPENAI_TEXT_MODEL; transcription keeps OPENAI_VISION_MODEL.
OPENAI_CHEAP_MODEL = os.getenv("OPENAI_CHEAP_MODEL", "gpt-5.4-nano")

# Reasoning effort per task (reasoning models only). "minimal" falls back to "low" if the API rejects it.
REASONING_VISION = os.getenv("REASONING_VISION", "minimal")
REASONING_CLASSIFY = os.getenv("REASONING_CLASSIFY", "minimal")
REASONING_SCREEN = os.getenv("REASONING_SCREEN", "low")
REASONING_PAYLOAD = os.getenv("REASONING_PAYLOAD", "minimal")

# Output token caps per task. A response cut off at the cap is retried once with double the cap.
MAX_TOKENS_VISION = int(os.getenv("MAX_TOKENS_VISION", "4000"))
MAX_TOKENS_CLASSIFY = int(os.getenv("MAX_TOKENS_CLASSIFY", "2000"))
MAX_TOKENS_SCREEN = int(os.getenv("MAX_TOKENS_SCREEN", "2500"))
MAX_TOKENS_PAYLOAD = int(os.getenv("MAX_TOKENS_PAYLOAD", "1500"))

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

MAX_FILE_MB = float(os.getenv("MAX_FILE_MB", "10"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))

# Cost caps per fuzz round of the offline eval CLI (python -m eval.run_eval fuzz).
FUZZ_MAX_ATTACKS = int(os.getenv("FUZZ_MAX_ATTACKS", "30"))
FUZZ_TOKEN_BUDGET = int(os.getenv("FUZZ_TOKEN_BUDGET", "200000"))


def openai_enabled() -> bool:
    return bool(OPENAI_API_KEY)
