"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Sample = { id: string; title: string; description: string };
const BADGE: Record<string, string> = { clean: "badge-clean", "white-text": "badge-poisoned", unicode: "badge-poisoned" };
const BADGE_TEXT: Record<string, string> = { clean: "Nothing hidden", "white-text": "Hidden attack", unicode: "Hidden attack" };

/** One-click sample resumes, so visitors can try HiddenInk without a file of their own. */
export default function SampleRow({ busy, onPick }: { busy: boolean; onPick: (s: Sample) => void }) {
  const [samples, setSamples] = useState<Sample[] | null>(null);
  useEffect(() => { api<{ samples: Sample[] }>("/api/samples").then((r) => setSamples(r.samples)).catch(() => setSamples([])); }, []);
  if (samples && samples.length === 0) return null;
  return (
    <section aria-label="Try a sample">
      <h2 className="mb-2 text-sm font-semibold text-gray-800">Try a sample <span className="font-normal text-gray-500">· no file needed, results in seconds</span></h2>
      <div className="grid gap-3 sm:grid-cols-3">
        {(samples ?? Array.from({ length: 3 }, (): Sample | null => null)).map((s, i) => s ? (
          <button key={s.id} type="button" disabled={busy} onClick={() => onPick(s)}
            className="card flex flex-col items-start gap-1 p-4 text-left disabled:cursor-wait disabled:opacity-60">
            <span className={BADGE[s.id] ?? "chip bg-gray-100 text-gray-700"}>{BADGE_TEXT[s.id] ?? "Sample"}</span>
            <span className="mt-1 font-medium text-gray-900">{s.title}</span>
            <span className="text-xs text-gray-500">{s.description}</span>
          </button>
        ) : <div key={i} className="skeleton h-[106px]" aria-hidden />)}
      </div>
    </section>
  );
}
