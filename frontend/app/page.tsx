"use client";
import { useEffect, useRef, useState } from "react";
import Findings from "@/components/Findings";
import RevealView from "@/components/RevealView";
import { useScan } from "@/components/ScanContext";
import Screening from "@/components/Screening";
import SampleRow from "@/components/trial/SampleRow";
import TrialGuide from "@/components/trial/TrialGuide";
import { prefersReducedMotion } from "@/components/ui/motion";
import Notice from "@/components/ui/Notice";
import Verdict from "@/components/Verdict";
import { api, downloadBlob, errorMessage } from "@/lib/api";
import { markTrialStep } from "@/lib/trial";
import { ScanReport } from "@/lib/types";

const SCAN_STEPS = ["Reading every character…", "Rendering pages…", "Asking the vision model what a human sees…", "Scoring risk…"];

export default function ScanPage() {
  const { report, setReport, active, setActive, clearScan, beginRequest } = useScan();
  const [scanning, setScanning] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [aiEnabled, setAiEnabled] = useState(false);
  const [drag, setDrag] = useState(false);
  const [showText, setShowText] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(0);
  const scanSteps = aiEnabled ? SCAN_STEPS : SCAN_STEPS.filter((x) => !x.includes("vision"));

  useEffect(() => { api("/api/info").then((h) => setAiEnabled(!!h.ai_enabled)).catch(() => {}); }, []);
  useEffect(() => {
    if (!busy) return;
    setStep(0);
    const t = setInterval(() => setStep((n) => n + 1), 1800);
    return () => clearInterval(t);
  }, [busy]);

  async function runScan(label: string, request: () => Promise<ScanReport>) {
    clearScan();
    const current = beginRequest();
    setScanning(label); setBusy(true); setError(""); setShowText(false);
    try {
      const r = await request();
      if (current()) { setReport(r); markTrialStep("scan"); }  // ignore results for a scan that was replaced or signed out of meanwhile
    } catch (e) { if (current()) setError(errorMessage(e)); } finally { setBusy(false); }
  }

  function scan(f: File) {
    const fd = new FormData();
    fd.append("file", f);
    return runScan(f.name, () => api<ScanReport>("/api/scan", { method: "POST", body: fd }));
  }

  function scanSample(s: { id: string; title: string }) {
    return runScan(s.title.toLowerCase(), () => api<ScanReport>(`/api/samples/${s.id}/scan`, { method: "POST" }));
  }

  function select(id: string) {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "nearest" });
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-ink-900">Scan a document</h1>
        <p className="text-sm text-gray-600">Upload a resume (PDF or DOCX, up to 10 MB and 5 pages). Files are processed in memory and never stored.</p>
      </div>

      <TrialGuide />
      <SampleRow busy={busy} onPick={scanSample} />

      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) scan(f); }}
        onClick={() => !busy && input.current?.click()}
        onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !busy) { e.preventDefault(); input.current?.click(); } }}
        role="button" tabIndex={0} aria-busy={busy} aria-label="Upload a resume, PDF or DOCX"
        className={`relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed px-6 py-10 text-center transition duration-200 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-uv-400/40 ${drag
          ? "scale-[1.01] border-uv-500 bg-uv-500/5 shadow-[0_0_0_6px_rgba(139,92,246,0.12),0_12px_40px_-12px_rgba(139,92,246,0.6)]"
          : "border-uv-400/60 bg-white/70 hover:border-uv-500 hover:bg-uv-500/[0.03]"}`}>
        <input ref={input} type="file" accept=".pdf,.docx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) scan(f); e.target.value = ""; }} />
        {busy && (
          <div aria-hidden className="pointer-events-none absolute inset-0">
            <div className="animate-scan-beam absolute inset-0">
              <div className="absolute inset-x-0 top-1/2 h-10 -translate-y-1/2 bg-gradient-to-b from-transparent via-uv-500/15 to-transparent blur-md" />
              <div className="absolute inset-x-0 top-1/2 h-[2px] bg-gradient-to-r from-uv-500 via-glow-400 to-uv-500 shadow-[0_0_12px_2px_rgba(34,211,238,0.5)]" />
            </div>
          </div>
        )}
        <span aria-hidden className={`mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-uv-500 to-ink-600 text-white shadow-[0_6px_18px_-6px_rgba(139,92,246,0.7)] ${drag ? "animate-float" : ""}`}>
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 8.5a4 4 0 0 1-.5 7.97" /><path d="M12 12v8" /><path d="m8.5 15.5 3.5-3.5 3.5 3.5" /></svg>
        </span>
        <p className="font-display text-lg font-medium text-ink-900">{busy ? `Scanning ${scanning}…` : "Drop a resume (PDF or DOCX)"}</p>
        <p className="mt-1 text-xs text-gray-500" aria-live="polite">
          {busy ? scanSteps[step % scanSteps.length] : "or click to choose a file · up to 10 MB and 5 pages · try a file from the Red-Team Lab to see an attack being caught"}
        </p>
      </div>
      {error && <Notice kind="error">{error}</Notice>}

      {report && (
        <>
          <Verdict report={report} />
          {report.warnings.length > 0 && (
            <ul className="space-y-1 text-xs text-amber-700">{report.warnings.map((w) => <li key={w}>⚠ {w}</li>)}</ul>
          )}
          <div className="grid gap-5 lg:grid-cols-2">
            <RevealView report={report} active={active} onSelect={select} />
            <div className={report.pages.length ? "" : "lg:col-span-2"}>
              <Findings report={report} active={active} onSelect={select} />
            </div>
          </div>
          <div className="card">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold">Sanitized text</h2>
                <p className="text-xs text-gray-500">Only the human-visible text, with hidden content and invisible characters removed. Safe to pass to any LLM.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-ghost" aria-expanded={showText} aria-controls="sanitized-text" onClick={() => setShowText((s) => !s)}>
                  {showText ? "Hide text" : "Show text"}
                </button>
                <button className="btn-ghost" onClick={() => downloadBlob(report.file_name.replace(/\.(pdf|docx)$/i, "") + "_sanitized.txt", new Blob([report.sanitized_text], { type: "text/plain" }))}>
                  Download sanitized text
                </button>
              </div>
            </div>
            {showText && (
              <pre id="sanitized-text" tabIndex={0} className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-gray-200 bg-gray-50 p-3 font-mono text-xs text-gray-800">
                {report.sanitized_text || "(No visible text was found.)"}
              </pre>
            )}
          </div>
          <Screening report={report} enabled={aiEnabled} />
        </>
      )}
    </div>
  );
}
