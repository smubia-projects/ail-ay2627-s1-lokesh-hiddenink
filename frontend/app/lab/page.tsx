"use client";
import { useEffect, useState } from "react";
import { api, b64ToBlob, downloadBlob, errorMessage } from "@/lib/api";
import { markTrialStep } from "@/lib/trial";
import { TECHNIQUE_LABELS } from "@/lib/types";

const nice = (s: string) => s.replace(/_/g, " ");

export default function LabPage() {
  const [opts, setOpts] = useState<any>(null);
  const [form, setForm] = useState({ sample_id: "random", technique: "random", goal: "random", style: "random", seed: "", screen: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => { api("/api/redteam/options").then(setOpts).catch((e) => setError(errorMessage(e))); }, []);

  async function attack() {
    setBusy(true); setError("");
    try {
      const job = form.screen ? opts.jobs[form.sample_id === "random" ? Object.keys(opts.jobs)[0] : form.sample_id] : null;
      const r = await api("/api/redteam/attack", { method: "POST", body: JSON.stringify({
        sample_id: form.sample_id, technique: form.technique, goal: form.goal, style: form.style,
        seed: form.seed ? Number(form.seed) : null, screen: form.screen, job_description: job,
      }) });
      setResult(r);
      setRuns((prev) => [r, ...prev].slice(0, 30));
      markTrialStep("lab");
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  const counted = runs.filter((r) => r.counted);
  const caught = counted.filter((r) => r.detected).length;

  const select = (key: keyof typeof form, values: string[], label: (v: string) => string = nice) => (
    <div>
      <label className="label">{key === "sample_id" ? "resume" : nice(key)}</label>
      <select className="input" value={form[key] as string} onChange={(e) => setForm({ ...form, [key]: e.target.value })}>
        <option value="random">🎲 Random</option>
        {values.map((v) => <option key={v} value={v}>{label(v)}</option>)}
      </select>
    </div>
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-ink-900">Red-Team Lab</h1>
        <p className="text-sm text-gray-600">HiddenInk attacks itself. Each run writes a fresh payload {opts?.ai_enabled ? "with an LLM" : "from templates"}, hides it with randomised settings, checks that a person really couldn&apos;t see it, then tests whether HiddenInk catches it. Generated attacks are returned to you only and never stored.</p>
      </div>
      <div className="card">
        {!opts && !error && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true" aria-label="Loading options">
            {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-[62px]" />)}
          </div>
        )}
        {opts && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {select("sample_id", opts.samples.map((s: any) => s.id), (v) => opts.samples.find((s: any) => s.id === v)?.title || v)}
            {select("technique", opts.techniques, (v) => TECHNIQUE_LABELS[v] || nice(v))}
            {select("goal", opts.goals)}
            {select("style", opts.styles)}
          </div>
        )}
        <div className="mt-3 flex flex-wrap items-end gap-4">
          <div><label className="label">Seed (optional)</label><input className="input w-36" inputMode="numeric" value={form.seed} onChange={(e) => setForm({ ...form, seed: e.target.value.replace(/\D/g, "") })} placeholder="random" /></div>
          <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" className="accent-indigo-600" checked={form.screen} disabled={!opts?.ai_enabled} onChange={(e) => setForm({ ...form, screen: e.target.checked })} />Also test both screeners (PDF only, uses more tokens)</label>
          <button className="btn-primary btn-glow ml-auto" onClick={attack} disabled={busy || !opts}>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M13 3 5 14h6l-1 7 8-11h-6z" /></svg>
            {busy ? "Attacking…" : "Fire attack"}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        <p className="mt-3 text-xs text-gray-500">Guardrails: only built-in fictional resumes, every file is watermarked as a test file, payloads only target the screening decision, and this endpoint is rate-limited.</p>
      </div>

      {busy && (
        <div className="grid gap-5 lg:grid-cols-2" aria-busy="true" aria-label="Running the attack">
          <div className="skeleton h-72" /><div className="skeleton h-72" />
        </div>
      )}
      {result && !busy && (
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="card space-y-3">
            <div className="flex items-center gap-3">
              <Outcome key={runs.length} counted={result.counted} detected={result.detected} />
              <span className="text-sm text-gray-600">Verdict {result.verdict} · risk {result.risk_score} · technique {result.technique_identified ? "identified" : "not identified"}</span>
            </div>
            <div>
              <p className="label">Hidden payload ({nice(result.answer_key.payload_source)})</p>
              <blockquote className="revealed-ink">{result.answer_key.payload}</blockquote>
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-gray-500">Technique</dt><dd>{TECHNIQUE_LABELS[result.answer_key.technique] || result.answer_key.technique}{result.answer_key.params.stacked_with ? ` + ${TECHNIQUE_LABELS[result.answer_key.params.stacked_with]}` : ""}</dd>
              <dt className="text-gray-500">Goal / style</dt><dd>{nice(result.answer_key.goal)} / {nice(result.answer_key.style)}</dd>
              <dt className="text-gray-500">Split into</dt><dd>{result.answer_key.fragments.length} location(s)</dd>
              <dt className="text-gray-500">Seed</dt><dd className="font-mono">{result.answer_key.seed}</dd>
              <dt className="text-gray-500">Detector saw</dt><dd>{result.found_techniques.map((t: string) => TECHNIQUE_LABELS[t] || t).join(", ") || "nothing"}</dd>
            </dl>
            {result.answer_key.invisibility_problems?.length > 0 && <p className="text-xs text-gray-500">{result.answer_key.invisibility_problems.join(" ")}</p>}
            <details className="text-xs"><summary className="cursor-pointer text-gray-500">Full answer key</summary><pre className="mt-2 overflow-x-auto rounded bg-gray-50 p-2">{JSON.stringify(result.answer_key, null, 2)}</pre></details>
            <button className="btn-ghost" onClick={() => downloadBlob(result.file_name, b64ToBlob(result.file_b64, result.file_name.endsWith(".pdf") ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))}>
              Download the poisoned test file
            </button>
          </div>
          <div className="card">
            {result.screening ? (
              <>
                <h2 className="font-semibold">Did the attack work on the screeners?</h2>
                <div className="mt-3 grid grid-cols-2 gap-3 text-center">
                  {[["Naive", result.screening.naive.score, result.screening.baseline.naive, result.screening.naive_fooled],
                    ["Protected", result.screening.protected.overall_score, result.screening.baseline.protected, result.screening.protected_fooled]].map(([name, score, base, fooled]: any) => (
                    <div key={name} className={`rounded-xl p-3 ${fooled ? "bg-rose-50" : "bg-emerald-50"}`}>
                      <p className="text-xs uppercase text-gray-500">{name}</p>
                      <p className="text-3xl font-bold">{Number(score).toFixed(1)}</p>
                      <p className="text-xs text-gray-500">clean resume scored {Number(base).toFixed(1)}</p>
                      <p className={`mt-1 text-sm font-medium ${fooled ? "text-rose-700" : "text-emerald-700"}`}>{fooled ? "Fooled" : "Not fooled"}</p>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                <h2 className="font-semibold">This session</h2>
                <p className="mt-1 text-sm text-gray-600">{counted.length ? `Caught ${caught} of ${counted.length} invisible attacks.` : "Run a few attacks to see a tally."}</p>
              </>
            )}
            <ul className="mt-4 space-y-1 text-xs">
              {runs.map((r, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${!r.counted ? "bg-gray-300" : r.detected ? "bg-emerald-500" : "bg-rose-500"}`} />
                  <span className="w-40 truncate">{TECHNIQUE_LABELS[r.answer_key.technique] || r.answer_key.technique}</span>
                  <span className="truncate text-gray-500">{r.answer_key.payload}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

/** The attack's outcome: "Caught" pops in with a green check burst, "Missed" shakes. Keyed per run so it replays. */
function Outcome({ counted, detected }: { counted: boolean; detected: boolean }) {
  if (!counted) return <span className="chip bg-gray-100 px-3 py-1 text-sm text-gray-600">Discarded: may be visible</span>;
  if (detected) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-emerald-100 py-1 pl-1 pr-3 text-sm font-semibold text-emerald-700" role="status">
        <span className="relative grid h-6 w-6 place-items-center" aria-hidden>
          <span className="animate-burst absolute inset-0 rounded-full border-2 border-emerald-400" />
          <span className="animate-burst absolute inset-0 rounded-full bg-emerald-300/50 [animation-delay:120ms]" />
          <span className="animate-pop relative grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4 10-10" /></svg>
          </span>
        </span>
        Caught
      </span>
    );
  }
  return (
    <span className="animate-shake inline-flex items-center gap-2 rounded-full bg-rose-100 py-1 pl-1 pr-3 text-sm font-semibold text-rose-700" role="status">
      <span className="grid h-6 w-6 place-items-center rounded-full bg-rose-500 text-white" aria-hidden>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
      </span>
      Missed
    </span>
  );
}
