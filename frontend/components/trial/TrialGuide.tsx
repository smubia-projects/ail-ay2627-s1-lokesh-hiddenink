"use client";
import { dismissTrialGuide, TrialStep } from "@/lib/trial";
import { useTrialProgress } from "./useTrialProgress";

const STEPS: { id: TrialStep; title: string; hint: string }[] = [
  { id: "scan", title: "Scan a sample", hint: "Pick one of the sample resumes below, or upload your own." },
  { id: "screen", title: "Run the protected screener", hint: "Score the resume against a job using only the visible text." },
  { id: "lab", title: "Fire a Red-Team attack", hint: "In the Red-Team Lab, hide a payload and see if HiddenInk catches it." },
];

/** The dismissible 3-step checklist shown at the top of the Scan page. */
export default function TrialGuide() {
  const progress = useTrialProgress();
  if (progress.dismissed) return null;
  const done = STEPS.filter((s) => progress[s.id]).length;
  return (
    <section className="card border-ink-100 bg-ink-50/50" aria-label="Get started">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-ink-900">Get started in 3 steps</h2>
          <p className="text-xs text-gray-600">{done === STEPS.length ? "All done. You've seen the whole flow." : `${done} of ${STEPS.length} done`}</p>
        </div>
        <button className="rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-white hover:text-gray-800" onClick={dismissTrialGuide}>
          Dismiss
        </button>
      </div>
      <ol className="mt-3 grid gap-2 sm:grid-cols-3">
        {STEPS.map((s, i) => {
          const ticked = !!progress[s.id];
          return (
            <li key={s.id} className={`flex gap-3 rounded-xl border bg-white p-3 text-sm ${ticked ? "border-green-200" : "border-gray-200"}`}>
              <span aria-hidden className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${ticked ? "bg-green-500 text-white" : "bg-ink-100 text-ink-700"}`}>
                {ticked ? "✓" : i + 1}
              </span>
              <div>
                <p className={`font-medium ${ticked ? "text-gray-500 line-through decoration-gray-300" : ""}`}>
                  {s.title}<span className="sr-only">{ticked ? " (done)" : " (to do)"}</span>
                </p>
                <p className="mt-0.5 text-xs text-gray-500">{s.hint}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
