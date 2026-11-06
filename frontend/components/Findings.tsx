import { CATEGORY_LABELS, ScanReport, TECHNIQUE_LABELS } from "@/lib/types";

const SEV = { high: "bg-rose-100 text-rose-700", medium: "bg-amber-100 text-amber-700", low: "bg-gray-100 text-gray-600" };
const EDGE = { high: "border-l-rose-500", medium: "border-l-amber-500", low: "border-l-gray-300" };

export default function Findings({ report, active, onSelect }: { report: ScanReport; active: string | null; onSelect: (id: string) => void }) {
  const points = Object.fromEntries(report.score_breakdown.map((b) => [b.finding_id, b]));
  if (!report.findings.length) {
    return (
      <div className="card flex items-center gap-3 text-sm text-gray-600">
        <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-emerald-100 text-emerald-600">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4 10-10" /></svg>
        </span>
        No hidden content found. The text an AI reads matches what a person sees.
      </div>
    );
  }
  return (
    <div className="card">
      <h2 className="mb-1 font-semibold">Visibility Gap report</h2>
      <p className="mb-3 text-xs text-gray-500">Each item is text the AI would read that a person would not see.</p>
      <ul className="space-y-3">
        {report.findings.map((f) => (
          <li key={f.id} id={f.id} onClick={() => onSelect(f.id)}
            className={`cursor-pointer rounded-xl border border-l-4 bg-white p-3 transition-shadow ${EDGE[f.severity]} ${active === f.id ? "border-uv-400 shadow-[0_0_0_3px_rgba(167,139,250,0.3)]" : "border-gray-200 hover:shadow-md"}`}>
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span className={`chip ${SEV[f.severity]}`}>{f.severity}</span>
              <span className="chip bg-ink-50 text-ink-700">{CATEGORY_LABELS[f.category] || f.category}</span>
              {f.techniques.map((t) => <span key={t} className="chip bg-uv-500/10 text-uv-700">{TECHNIQUE_LABELS[t] || t}</span>)}
              <span className="chip bg-gray-50 text-gray-500">found by {f.source === "both" ? "forensics + vision" : f.source}</span>
              {f.payload_matches > 0 && <span className="chip bg-purple-100 text-purple-700">matches {f.payload_matches} known attack{f.payload_matches > 1 ? "s" : ""}</span>}
              {f.page !== null && <span className="ml-auto text-xs text-gray-500">page {f.page + 1}</span>}
            </div>
            <blockquote className="revealed-ink">{f.text}</blockquote>
            <p className="mt-2 text-sm text-gray-700">{f.rationale}{f.target_behavior ? ` Goal: ${f.target_behavior}.` : ""}</p>
            <p className="mt-1 text-xs text-gray-500">{f.detail}</p>
            {points[f.id] && <p className="mt-1 text-xs text-gray-500">+{points[f.id].points} risk: {points[f.id].reasons.join(", ")}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
