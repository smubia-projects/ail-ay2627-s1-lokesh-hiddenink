"""Shared data models."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Technique = Literal[
    "low_contrast",
    "tiny_font",
    "off_page",
    "invisible_render",
    "covered",
    "zero_width",
    "unicode_tags",
    "bidi_override",
    "metadata",
    "annotation",
    "form_field",
    "embedded_file",
    "docx_hidden_run",
    "docx_comment",
    "visibility_gap",
]

Category = Literal["prompt_injection", "keyword_stuffing", "data_exfiltration", "benign_hidden", "unclassified"]
Severity = Literal["low", "medium", "high"]


class Finding(BaseModel):
    id: str
    page: Optional[int] = None  # 0-based; None for document-level findings
    bbox: Optional[list[float]] = None  # [x0, y0, x1, y1] in PDF points
    text: str
    techniques: list[str] = Field(default_factory=list)
    detail: str = ""
    source: Literal["forensics", "vision", "both"] = "forensics"
    category: Category = "unclassified"
    severity: Severity = "medium"
    rationale: str = ""
    target_behavior: str = ""
    regex_hits: list[str] = Field(default_factory=list)
    payload_matches: int = 0


class PageInfo(BaseModel):
    index: int
    width: float
    height: float
    image_b64: str  # PNG, base64


class ScanReport(BaseModel):
    scan_id: str
    file_name: str
    file_hash: str
    file_type: Literal["pdf", "docx"]
    risk_score: int
    verdict: Literal["Clean", "Suspicious", "Poisoned"]
    score_breakdown: list[dict]
    findings: list[Finding]
    pages: list[PageInfo]
    machine_text: str
    sanitized_text: str
    # Non-benign hidden fragments; the browser sends them back to /api/screen for the tripwire check.
    hidden_texts: list[str] = Field(default_factory=list)
    ai_layers: dict
    warnings: list[str] = Field(default_factory=list)
