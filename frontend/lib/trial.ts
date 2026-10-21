// Getting-started guide progress, kept in sessionStorage for this browser tab.
export type TrialStep = "scan" | "screen" | "lab";
export type TrialProgress = Partial<Record<TrialStep, boolean>> & { dismissed?: boolean };
export const TRIAL_EVENT = "hiddenink:guide-progress";
const KEY = "ail-ay2627-s1-lokesh-hiddenink:guide";

export function getTrialProgress(): TrialProgress {
  try { return JSON.parse(sessionStorage.getItem(KEY) || "{}"); } catch { return {}; }
}

function save(p: TrialProgress) {
  try { sessionStorage.setItem(KEY, JSON.stringify(p)); } catch {}
  window.dispatchEvent(new Event(TRIAL_EVENT));
}

/** Ticks a step of the guided first run. */
export function markTrialStep(step: TrialStep) {
  const p = getTrialProgress();
  if (!p[step]) save({ ...p, [step]: true });
}

export function dismissTrialGuide() {
  save({ ...getTrialProgress(), dismissed: true });
}
