"""Runs the full detection pipeline on one file."""
from __future__ import annotations

import hashlib
import logging
import uuid

from rapidfuzz import fuzz

from . import classify, config, gap, payload_library
from .forensics import docx as docx_forensics
from .forensics import pdf as pdf_forensics
from .forensics import unicode as uni
from .models import Finding, ScanReport
from .scoring import score

log = logging.getLogger("hiddenink.scanner")

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"


def detect_type(name: str, data: bytes) -> str:
    lower = name.lower()
    if data.startswith(PDF_MAGIC) and lower.endswith(".pdf"):
        return "pdf"
    if data.startswith(ZIP_MAGIC) and lower.endswith(".docx"):
        return "docx"
    raise ValueError("Only .pdf and .docx files are supported (checked by extension and file signature).")


def _group_spans(spans) -> list[dict]:
    """Merge consecutive hidden spans on the same page with the same techniques into one finding."""
    groups: list[dict] = []
    for s in spans:
        if not s.hidden:
            continue
        last = groups[-1] if groups else None
        if (last and last["page"] == s.page and last["techniques"] == s.techniques
                and abs(s.bbox[1] - last["bbox"][3]) < max(30, 3 * s.size) and s.seqno - last["_last_seq"] <= 2):
            last["text"] += " " + s.text.strip()
            last["bbox"] = [min(last["bbox"][0], s.bbox[0]), min(last["bbox"][1], s.bbox[1]),
                            max(last["bbox"][2], s.bbox[2]), max(last["bbox"][3], s.bbox[3])]
            last["_seqnos"].append(s.seqno)
            last["_last_seq"] = s.seqno
        else:
            groups.append({"page": s.page, "bbox": list(s.bbox), "text": s.text.strip(),
                           "techniques": list(s.techniques), "detail": " ".join(s.details),
                           "_seqnos": [s.seqno], "_last_seq": s.seqno})
    return groups


def scan(file_name: str, data: bytes, use_ai: bool = True) -> tuple[ScanReport, dict]:
    """Returns the report and a context with the texts the screeners need (used by the Red-Team Lab)."""
    if len(data) > config.MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"File is larger than {config.MAX_FILE_MB:g} MB.")
    ftype = detect_type(file_name, data)
    use_ai = use_ai and config.openai_enabled()
    ai_layers = {"vision_gap": "off", "classifier": "off", "payload_library": "fuzzy"}
    warnings: list[str] = []
    if not config.openai_enabled():
        warnings.append("OpenAI key not configured: running deterministic layers only.")

    raw: list[dict] = []
    pages: list[dict] = []
    if ftype == "pdf":
        a = pdf_forensics.analyse_pdf(data, config.MAX_PAGES)
        pages = a.pages
        groups = _group_spans(a.spans)
        machine_text = "\n\n".join(a.page_texts)
        sanitized = pdf_forensics.visible_text(a.spans)
        if use_ai and pages:
            try:
                gap_findings, _human, cross = gap.run(a.spans, pages)
                ai_layers["vision_gap"] = "on"
                for g in groups:
                    states = [cross.get(f"{g['page']}:{q}") for q in g["_seqnos"]]
                    if states and all(st == "seen" for st in states):
                        g["vision_seen"] = True
                        g["detail"] += " Note: the vision model could read this text, so it may be visible."
                        g["source"] = "forensics"
                    elif any(st == "unseen" for st in states):
                        g["source"] = "both"
                for gf in gap_findings:
                    groups.append({"page": gf["page"], "bbox": gf["bbox"], "text": gf["text"],
                                   "techniques": ["visibility_gap"], "detail": gf["detail"], "source": "vision"})
                    sanitized = sanitized.replace(gf["text"], "")
            except Exception as exc:  # noqa: BLE001
                log.warning("vision gap failed: %s", type(exc).__name__)
                ai_layers["vision_gap"] = "error"
                warnings.append("Vision check unavailable for this scan; deterministic checks still ran.")
        raw.extend(groups)
        raw.extend({"techniques": [d.pop("technique")], **d} for d in [dict(x) for x in a.doc_findings])
    else:
        a = docx_forensics.analyse_docx(data)
        machine_text = a.machine_text
        sanitized = a.visible_text
        merged: list[dict] = []
        for r in a.runs:
            if not r.hidden:
                continue
            if merged and merged[-1]["techniques"] == r.techniques and merged[-1]["_last"] == r.index - 1:
                merged[-1]["text"] += r.text
                merged[-1]["_last"] = r.index
            else:
                merged.append({"page": None, "bbox": None, "text": r.text, "techniques": list(r.techniques),
                               "detail": " ".join(r.details), "_last": r.index})
        raw.extend(merged)
        raw.extend({"techniques": [d.pop("technique")], **d} for d in [dict(x) for x in a.doc_findings])
        warnings.append("DOCX pages are not rendered, so the vision check is skipped; text-level checks still ran.")

    findings: list[dict] = []
    for i, r in enumerate(raw):
        text = uni.strip_invisible(r["text"]).strip() if "unicode_tags" not in r["techniques"] else r["text"]
        if not text:
            continue
        findings.append({"id": f"f{i + 1}", "page": r.get("page"), "bbox": r.get("bbox"), "text": text[:3000],
                         "techniques": r["techniques"], "detail": r.get("detail", ""),
                         "source": r.get("source", "forensics"), "vision_seen": r.get("vision_seen", False)})

    err = classify.classify(findings, use_llm=use_ai)
    ai_layers["classifier"] = "on" if use_ai and not err else ("error" if err else "off")
    if err:
        warnings.append(err)

    try:
        matches = payload_library.match([f["text"] for f in findings])
        for f, m in zip(findings, matches):
            f["payload_matches"] = m
    except Exception as exc:  # noqa: BLE001
        log.warning("payload library match failed: %s", type(exc).__name__)

    risk, verdict, breakdown = score(findings)
    # Strip any hidden findings' text that survived into the sanitized version (e.g. metadata never is).
    for f in findings:
        if len(f["text"]) >= 12 and f["page"] is not None:
            sanitized = sanitized.replace(f["text"], "")
    sanitized = uni.strip_invisible(sanitized)

    hidden_texts = [f["text"] for f in findings if f["category"] != "benign_hidden"]
    report = ScanReport(
        scan_id=uuid.uuid4().hex,
        file_name=file_name[:200],
        file_hash=hashlib.sha256(data).hexdigest(),
        file_type=ftype,
        risk_score=risk,
        verdict=verdict,
        score_breakdown=breakdown,
        findings=[Finding(**{k: v for k, v in f.items() if k != "vision_seen"}) for f in findings],
        pages=pages,
        machine_text=machine_text,
        sanitized_text=sanitized,
        hidden_texts=hidden_texts,
        ai_layers=ai_layers,
        warnings=warnings,
    )
    context = {"machine_text": machine_text, "sanitized_text": sanitized, "hidden_texts": hidden_texts}
    return report, context


def payload_found(report: ScanReport, payload: str, threshold: int = 80) -> bool:
    """Used by the Red-Team Lab: did any finding contain the injected payload?"""
    p = payload.lower()
    return any(fuzz.partial_ratio(p[:300], f.text.lower()) >= threshold for f in report.findings)
