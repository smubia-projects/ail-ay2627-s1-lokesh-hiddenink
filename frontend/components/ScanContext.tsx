"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Protected, ScanReport } from "@/lib/types";

// Keeps the current scan across page changes (context) and refreshes in the same tab (sessionStorage).

export const SAMPLE_JD = "Data Analyst. Requirements: 2+ years of SQL and Python for analysis; experience building dashboards in Power BI or Tableau; ability to explain insights to non-technical stakeholders; degree in a quantitative field.";

export type ScreenResult = { protected?: Protected; protected_error?: string };

type ScanState = {
  report: ScanReport | null;
  setReport: (r: ScanReport | null) => void;
  active: string | null;
  setActive: (id: string | null) => void;
  jobDescription: string;
  setJobDescription: (jd: string) => void;
  /** Screening results for the current report only. */
  screening: ScreenResult | null;
  setScreening: (scanId: string, result: ScreenResult | null) => void;
  clearScan: () => void;
  /** Call before an async request; the returned check is false if the scan was cleared or replaced meanwhile. */
  beginRequest: () => () => boolean;
};

const ScanContext = createContext<ScanState | null>(null);
const REPORT_KEY = "ail-ay2627-s1-lokesh-hiddenink:scan";
const UI_KEY = "ail-ay2627-s1-lokesh-hiddenink:scan-ui";

function load<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {}
  return null;
}

function save(key: string, value: object | null) {
  try {
    if (value) sessionStorage.setItem(key, JSON.stringify(value));
    else sessionStorage.removeItem(key);
  } catch {
    // Too large (page images) or storage unavailable: keep it in memory only, and drop any older copy.
    try { sessionStorage.removeItem(key); } catch {}
  }
}

export function ScanProvider({ children }: { children: React.ReactNode }) {
  const [loaded, setLoaded] = useState(false);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [jobDescription, setJobDescription] = useState(SAMPLE_JD);
  const [screened, setScreened] = useState<{ scanId: string; result: ScreenResult } | null>(null);
  const epoch = useRef(0);

  const clearScan = useCallback(() => {
    epoch.current += 1;
    setReport(null); setActive(null); setScreened(null);
  }, []);

  const beginRequest = useCallback(() => {
    const at = epoch.current;
    return () => epoch.current === at;
  }, []);

  const setScreening = useCallback((scanId: string, result: ScreenResult | null) => {
    setScreened(result ? { scanId, result } : null);
  }, []);

  useEffect(() => {
    const r = load<{ report: ScanReport }>(REPORT_KEY);
    const ui = load<{ active: string | null; jobDescription: string; screened: typeof screened }>(UI_KEY);
    if (r?.report) setReport(r.report);
    if (ui) {
      if (r?.report) { setActive(ui.active); setScreened(ui.screened); }
      if (ui.jobDescription) setJobDescription(ui.jobDescription);
    }
    setLoaded(true);
  }, []);

  // Stored separately so selecting a finding doesn't re-serialize the page images.
  useEffect(() => { if (loaded) save(REPORT_KEY, report ? { report } : null); }, [loaded, report]);
  useEffect(() => { if (loaded) save(UI_KEY, { active, jobDescription, screened }); }, [loaded, active, jobDescription, screened]);

  const screening = screened && report && screened.scanId === report.scan_id ? screened.result : null;
  return (
    <ScanContext.Provider value={{ report, setReport, active, setActive, jobDescription, setJobDescription, screening, setScreening, clearScan, beginRequest }}>
      {children}
    </ScanContext.Provider>
  );
}

export function useScan(): ScanState {
  const ctx = useContext(ScanContext);
  if (!ctx) throw new Error("useScan must be used inside <ScanProvider>.");
  return ctx;
}
