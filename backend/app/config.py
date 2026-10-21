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


# All model calls go through OpenRouter (OpenAI-compatible API). Model IDs use OpenRouter's "vendor/model" form.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TEXT_MODEL = os.getenv("OPENROUTER_TEXT_MODEL", "openai/gpt-5.4-mini")
# Page transcription for the Visibility Gap. gpt-5.4-mini reads images at a fraction of gpt-5.4's price.
OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "openai/gpt-5.4-mini")
OPENROUTER_REASONING_EFFORT = os.getenv("OPENROUTER_REASONING_EFFORT", "low")  # set empty to never send `reasoning`
OPENROUTER_TIMEOUT = float(os.getenv("OPENROUTER_TIMEOUT", "60"))
# Cheaper model for tasks where quality barely matters: the classifier (its regex floor still wins) and the
# Red-Team payload writer. The screeners keep OPENROUTER_TEXT_MODEL; transcription keeps OPENROUTER_VISION_MODEL.
OPENROUTER_CHEAP_MODEL = os.getenv("OPENROUTER_CHEAP_MODEL", "openai/gpt-5.4-nano")

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

# Rate limiting (shared engine, Upstash Redis). Unset Upstash vars disable it (local dev).
# These maxima are fallbacks; the central control sheet overrides them at runtime.
UPSTASH_REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("UPSTASH_REDIS_URL", "")
UPSTASH_REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("UPSTASH_REDIS_TOKEN", "")
RATE_LIMIT_SCAN_MAX = int(os.getenv("RATE_LIMIT_SCAN_MAX", "5"))
RATE_LIMIT_SCREEN_MAX = int(os.getenv("RATE_LIMIT_SCREEN_MAX", "5"))
RATE_LIMIT_REDTEAM_MAX = int(os.getenv("RATE_LIMIT_REDTEAM_MAX", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "432000"))  # 5 days

# Cost caps per fuzz round of the offline eval CLI (python -m eval.run_eval fuzz).
FUZZ_MAX_ATTACKS = int(os.getenv("FUZZ_MAX_ATTACKS", "30"))
FUZZ_TOKEN_BUDGET = int(os.getenv("FUZZ_TOKEN_BUDGET", "200000"))


def llm_enabled() -> bool:
    return bool(OPENROUTER_API_KEY)
