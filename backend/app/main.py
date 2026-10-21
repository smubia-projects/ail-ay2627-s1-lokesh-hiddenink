"""HiddenInk API.

A stateless public demo: nothing is stored on the server. /api/scan returns the full report
(including the sanitized text) to the browser, and /api/screen takes that text back in the
request body.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config, demo_samples, scanner, screen
from .redteam import lab

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hiddenink")

app = FastAPI(title="HiddenInk API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


async def _read_upload(file: UploadFile) -> bytes:
    limit = int(config.MAX_FILE_MB * 1024 * 1024)
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {config.MAX_FILE_MB:g} MB.")
    return data


# ---------- health & info ----------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
def info():
    """Which AI layers are available, so the UI can enable or explain them."""
    return {"ai_enabled": config.llm_enabled(), "text_model": config.OPENROUTER_TEXT_MODEL,
            "vision_model": config.OPENROUTER_VISION_MODEL, "max_file_mb": config.MAX_FILE_MB,
            "max_pages": config.MAX_PAGES}


# ---------- scanning ----------
@app.post("/api/scan")
async def scan(request: Request, file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        report, _ctx = scanner.scan(file.filename or "upload", data, use_ai=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return report


# ---------- built-in sample resumes ----------
@app.get("/api/samples")
def samples():
    return {"samples": demo_samples.sample_list()}


@app.post("/api/samples/{sample_id}/scan")
def sample_scan(sample_id: str):
    """Scans a built-in sample. The result is cached per process, so repeat clicks don't call the model."""
    report = demo_samples.sample_scan(sample_id)
    if report is None:
        raise HTTPException(404, "Unknown sample.")
    return report


# ---------- protected AI screener ----------
class ScreenIn(BaseModel):
    job_description: str = Field(min_length=20, max_length=6000)
    # Both come from the /api/scan report the browser already holds; the server keeps no copy.
    sanitized_text: str = Field(min_length=1, max_length=60000)
    hidden_texts: list[str] = Field(default_factory=list, max_length=100)


@app.post("/api/screen")
def run_screen(request: Request, body: ScreenIn):
    if not config.llm_enabled():
        raise HTTPException(501, "Screening needs an OpenRouter API key on the server.")
    hidden = [h[:3000] for h in body.hidden_texts]
    try:
        return {"protected": screen.protected(body.job_description, body.sanitized_text, hidden).model_dump()}
    except Exception as exc:  # noqa: BLE001
        log.warning("protected screener failed: %s", type(exc).__name__)
        return {"protected_error": f"Protected screener failed ({type(exc).__name__})."}


# ---------- Red-Team Lab ----------
@app.get("/api/redteam/options")
def redteam_options():
    return lab.options()


class RedTeamIn(BaseModel):
    sample_id: str = "random"
    technique: str = "random"
    goal: str = "random"
    style: str = "random"
    seed: Optional[int] = None
    job_description: Optional[str] = Field(default=None, max_length=6000)
    screen: bool = False


@app.post("/api/redteam/attack")
def redteam_attack(request: Request, body: RedTeamIn):
    # Generated attacks are returned to the browser only; nothing about the run is persisted.
    try:
        return lab.attack_and_test(body.sample_id, body.technique, body.goal, body.style, body.seed,
                                   screen_job=body.job_description if body.screen else None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
