"""HiddenInk evaluation and Red-Team fuzzing.

Usage (from the backend folder):
  python -m eval.run_eval build                 # create frozen benchmark, held-out and clean sets
  python -m eval.run_eval run --set heldout --version v1 [--no-ai] [--screen]
  python -m eval.run_eval fuzz --rounds 3 --n 30 --version v1

Rules this script enforces:
- The held-out set is never used for tuning. Headline numbers come only from it.
- Every attack is checked for real invisibility before it counts.
- Each fuzz round is capped by attack count and LLM token budget.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app import config, llm, scanner
from app.redteam import lab, samples, techniques

ROOT = Path(__file__).resolve().parent
SETS = ROOT / "sets"
RESULTS = ROOT / "results"
SEED_BASE = {"benchmark": 1000, "heldout": 9000}
BENCH_N = 30  # held-out attacks for runs started from the Evaluation page (tests lower it)

_heldout_cache: dict[int, tuple[list[dict], list[dict]]] = {}
_heldout_lock = threading.Lock()


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- build ----------
def generate_attacks(set_name: str, n: int, use_ai: bool, log=print) -> list[dict]:
    """Attack files for a set, as {"file_name", "data", "answer_key"}; the same seeds always give the same set."""
    base = SEED_BASE[set_name]
    attacks: list[dict] = []
    avoid: list[str] = []
    for i in range(n):
        technique = techniques.ALL_TECHNIQUES[i % len(techniques.ALL_TECHNIQUES)]
        seed = base + i
        for attempt in range(5):  # discard attacks that a person could actually see
            atk = lab.generate_attack(technique=technique, seed=seed + attempt * 100000, avoid=avoid, use_ai=use_ai)
            if atk["answer_key"]["invisible"]:
                break
        else:
            log(f"  skipped {technique} seed {seed}: could not make an invisible variant")
            continue
        avoid.append(atk["answer_key"]["payload"])
        attacks.append(atk)
    return attacks


def generate_clean() -> list[dict]:
    """Clean resumes, as {"file_name", "data", "sample_id"}, including legitimate small grey print."""
    clean = []
    for sid in samples.SAMPLES:
        for variant, kw in (("plain", {}), ("smallprint", {"small_print": True, "design_grey": True})):
            data, _ = samples.make_pdf(sid, **kw)
            clean.append({"file_name": f"clean_{sid}_{variant}.pdf", "data": data, "sample_id": sid})
        clean.append({"file_name": f"clean_{sid}.docx", "data": samples.docx_bytes(samples.make_docx(sid)), "sample_id": sid})
    return clean


def build_heldout_in_memory(n: int | None = None) -> tuple[list[dict], list[dict]]:
    """The held-out set with template payloads (identical every time), built once per process. Writes no files."""
    n = BENCH_N if n is None else n
    with _heldout_lock:
        if n not in _heldout_cache:
            _heldout_cache[n] = (generate_attacks("heldout", n, use_ai=False, log=lambda _msg: None), generate_clean())
        return _heldout_cache[n]


def build(n: int, use_ai: bool) -> None:
    for name in SEED_BASE:
        folder = SETS / name
        manifest = []
        for atk in generate_attacks(name, n, use_ai):
            (folder / "files").mkdir(parents=True, exist_ok=True)
            (folder / "files" / atk["file_name"]).write_bytes(atk["data"])
            manifest.append({"file": atk["file_name"], **atk["answer_key"]})
        _write(folder / "manifest.json", manifest)
        print(f"{name}: {len(manifest)} attack files")

    folder = SETS / "clean"
    (folder / "files").mkdir(parents=True, exist_ok=True)
    manifest = []
    for c in generate_clean():
        (folder / "files" / c["file_name"]).write_bytes(c["data"])
        manifest.append({"file": c["file_name"], "sample_id": c["sample_id"]})
    _write(folder / "manifest.json", manifest)
    print(f"clean: {len(manifest)} files")


# ---------- run ----------
def evaluate_set(attacks: list[dict], clean: list[dict], use_ai: bool, progress_cb=None,
                 do_screen: bool = False, log=lambda _msg: None) -> dict:
    """Scan every attack and clean file and score the detector. progress_cb(done, total, label) runs after each file."""
    start_tokens, t0 = llm.tokens_used(), time.time()
    total, done = len(attacks) + len(clean), 0
    per: dict[str, dict] = {}
    rows = []
    naive_fooled = prot_fooled = screened = 0
    for atk in attacks:
        m = atk["answer_key"]
        res = lab.evaluate(atk, use_ai=use_ai)
        t = per.setdefault(m["technique"], {"n": 0, "detected": 0, "identified": 0, "flagged": 0})
        t["n"] += 1
        t["detected"] += res["detected"]
        t["identified"] += res["technique_identified"]
        t["flagged"] += res["flagged"]
        row = {"file": atk["file_name"], "technique": m["technique"], "style": m["style"], "detected": res["detected"],
               "flagged": res["flagged"], "risk": res["report"].risk_score}
        if do_screen and use_ai and m["file_type"] == "pdf":
            try:
                s = lab.screen_attack(m["sample_id"], samples.JOBS[m["sample_id"]], res["ctx"])
                screened += 1
                naive_fooled += s["naive_fooled"]
                prot_fooled += s["protected_fooled"]
                row.update(naive_fooled=s["naive_fooled"], protected_fooled=s["protected_fooled"])
            except Exception as exc:  # noqa: BLE001
                row["screen_error"] = type(exc).__name__
        rows.append(row)
        log(f"  {atk['file_name']}: detected={res['detected']} verdict={res['report'].verdict}")
        done += 1
        if progress_cb:
            progress_cb(done, total, atk["file_name"])

    fps, clean_risk = [], []
    for c in clean:
        rep, _ = scanner.scan(c["file_name"], c["data"], use_ai=use_ai)
        clean_risk.append(rep.risk_score)
        if rep.verdict != "Clean":
            fps.append({"file": c["file_name"], "verdict": rep.verdict, "findings": [f.text[:80] for f in rep.findings]})
        done += 1
        if progress_cb:
            progress_cb(done, total, c["file_name"])

    n = len(attacks) or 1
    out = {
        "ai_layers": use_ai and config.llm_enabled(), "attacks": len(attacks),
        "detection_rate": round(sum(t["detected"] for t in per.values()) / n, 3),
        "technique_accuracy": round(sum(t["identified"] for t in per.values()) / n, 3),
        "flag_rate": round(sum(t["flagged"] for t in per.values()) / n, 3),
        "clean_files": len(clean), "false_positive_rate": round(len(fps) / (len(clean) or 1), 3), "false_positives": fps,
        "per_technique": per, "rows": rows,
        "avg_risk_attacks": round(sum(r["risk"] for r in rows) / len(rows), 1) if rows else None,
        "avg_risk_clean": round(sum(clean_risk) / len(clean_risk), 1) if clean_risk else None,
        "duration_s": round(time.time() - t0, 1),
        "tokens_used": llm.tokens_used() - start_tokens,
    }
    if screened:
        out["screening"] = {"screened": screened, "naive_attack_success": round(naive_fooled / screened, 3),
                            "protected_attack_success": round(prot_fooled / screened, 3)}
    return out


def run(set_name: str, version: str, use_ai: bool, do_screen: bool, limit: int | None) -> dict:
    manifest = json.loads((SETS / set_name / "manifest.json").read_text(encoding="utf-8"))[:limit]
    attacks = [{"file_name": m["file"], "data": (SETS / set_name / "files" / m["file"]).read_bytes(), "answer_key": m}
               for m in manifest]
    clean = [{"file_name": c["file"], "data": (SETS / "clean" / "files" / c["file"]).read_bytes(), "sample_id": c["sample_id"]}
             for c in json.loads((SETS / "clean" / "manifest.json").read_text(encoding="utf-8"))]
    out = {"set": set_name, "version": version, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           **evaluate_set(attacks, clean, use_ai, do_screen=do_screen, log=print)}
    _write(RESULTS / f"{set_name}_{version}.json", out)
    if set_name == "heldout":
        _write(RESULTS / "latest.json", out)
        hist_path = RESULTS / "history.json"
        hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []
        hist = [h for h in hist if h["version"] != version] + [{
            "version": version, "date": out["date"], "detection_rate": out["detection_rate"],
            "false_positive_rate": out["false_positive_rate"],
            "naive_attack_success": out.get("screening", {}).get("naive_attack_success"),
            "protected_attack_success": out.get("screening", {}).get("protected_attack_success")}]
        _write(hist_path, hist)
    print(markdown(out))
    return out


def markdown(r: dict) -> str:
    lines = [f"### {r['set']} set, {r['version']} ({r['attacks']} attacks, AI layers {'on' if r['ai_layers'] else 'off'})", "",
             "| Technique | Attacks | Detected | Technique identified | Flagged |", "|---|---|---|---|---|"]
    for t, v in sorted(r["per_technique"].items()):
        lines.append(f"| {t} | {v['n']} | {v['detected']}/{v['n']} | {v['identified']}/{v['n']} | {v['flagged']}/{v['n']} |")
    lines += ["", f"- Detection rate: **{r['detection_rate']:.0%}**",
              f"- False-positive rate on {r['clean_files']} clean files: **{r['false_positive_rate']:.0%}**"]
    if "screening" in r:
        s = r["screening"]
        lines.append(f"- Attack success: naive screener **{s['naive_attack_success']:.0%}**, protected screener **{s['protected_attack_success']:.0%}** ({s['screened']} screened)")
    return "\n".join(lines)


# ---------- adaptive fuzzing ----------
def fuzz(rounds: int, n: int, version: str) -> None:
    n = min(n, config.FUZZ_MAX_ATTACKS)
    log_path = RESULTS / "fuzz_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    rng = random.Random()
    for r in range(1, rounds + 1):
        state = lab.load_state()
        start_tokens = llm.tokens_used()
        attempts = misses = discarded = 0
        missed: list[dict] = []
        t0 = time.time()
        for _ in range(n):
            if llm.tokens_used() - start_tokens > config.FUZZ_TOKEN_BUDGET:
                print("  token budget for this round reached; stopping early")
                break
            prior = state.get("misses", [])
            if prior and rng.random() < 0.5:
                # Adaptive step: a harder rewording of something that got through before.
                m = rng.choice(prior)
                from app.redteam import payloads
                text, _src = payloads.harder_variant(m["payload"], m["goal"], rng)
                atk = lab.generate_attack(technique=m["technique"], goal=m["goal"], payload_override=text, weighted=True)
            else:
                atk = lab.generate_attack(weighted=True, avoid=[x["payload"] for x in prior])
            key = atk["answer_key"]
            if not key["invisible"]:
                discarded += 1
                continue
            res = lab.evaluate(atk)
            attempts += 1
            miss = not res["detected"]
            misses += miss
            lab.record(state, key["technique"], key["style"], miss, key["payload"], key["goal"])
            if miss:
                missed.append({"technique": key["technique"], "style": key["style"], "payload": key["payload"], "seed": key["seed"]})
        lab.save_state(state)
        entry = {"version": version, "round": r, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "attempts": attempts, "discarded_visible": discarded, "misses": misses,
                 "detection_rate": round(1 - misses / attempts, 3) if attempts else None,
                 "tokens": llm.tokens_used() - start_tokens, "seconds": round(time.time() - t0, 1)}
        log.append(entry)
        _write(log_path, log)
        _write(RESULTS / f"fuzz_{version}_round{r}.json", {**entry, "missed": missed})
        print(f"round {r}: {attempts} attacks, {misses} missed, {discarded} discarded as visible, {entry['tokens']} tokens")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--n", type=int, default=56, help="attacks per set (default 56 = 4 per technique)")
    b.add_argument("--no-ai", action="store_true", help="use payload templates instead of the LLM")
    r = sub.add_parser("run")
    r.add_argument("--set", default="heldout", choices=["heldout", "benchmark"])
    r.add_argument("--version", default="v1")
    r.add_argument("--no-ai", action="store_true")
    r.add_argument("--screen", action="store_true", help="also measure attack success on naive vs protected screener")
    r.add_argument("--limit", type=int)
    f = sub.add_parser("fuzz")
    f.add_argument("--rounds", type=int, default=3)
    f.add_argument("--n", type=int, default=30)
    f.add_argument("--version", default="v1")
    a = p.parse_args(argv)
    if a.cmd == "build":
        build(a.n, use_ai=not a.no_ai)
    elif a.cmd == "run":
        run(a.set, a.version, use_ai=not a.no_ai, do_screen=a.screen, limit=a.limit)
    else:
        if not config.llm_enabled():
            print("Fuzzing works best with OPENROUTER_API_KEY set (fresh payloads and harder variants); continuing with templates.", file=sys.stderr)
        fuzz(a.rounds, a.n, a.version)


if __name__ == "__main__":
    main()
