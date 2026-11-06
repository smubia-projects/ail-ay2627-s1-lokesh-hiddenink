export type Finding = {
  id: string; page: number | null; bbox: number[] | null; text: string; techniques: string[]; detail: string;
  source: "forensics" | "vision" | "both"; category: string; severity: "low" | "medium" | "high";
  rationale: string; target_behavior: string; regex_hits: string[]; payload_matches: number;
};
export type PageInfo = { index: number; width: number; height: number; image_b64: string };
export type ScanReport = {
  scan_id: string; file_name: string; file_hash: string; file_type: "pdf" | "docx"; risk_score: number;
  verdict: "Clean" | "Suspicious" | "Poisoned"; score_breakdown: { finding_id: string; points: number; reasons: string[] }[];
  findings: Finding[]; pages: PageInfo[]; machine_text: string; sanitized_text: string; hidden_texts: string[];
  ai_layers: Record<string, string>; warnings: string[];
};
export type Criterion = { name: string; score: number; evidence: string[]; verified_evidence: string[]; grounded: boolean };
export type Protected = {
  criteria: Criterion[]; model_overall: number; overall_score: number; recommendation: string; summary: string;
  injection_attempt_noticed: boolean; dropped_claims: number; tripwire: string[]; masked: Record<string, number>;
};

export const TECHNIQUE_LABELS: Record<string, string> = {
  low_contrast: "Invisible colour", tiny_font: "Tiny font", off_page: "Off the page", invisible_render: "Invisible text mode",
  covered: "Covered by a shape", zero_width: "Zero-width characters", unicode_tags: "Unicode tag characters",
  bidi_override: "Bidirectional override", metadata: "Metadata", annotation: "Hidden annotation", form_field: "Form field",
  embedded_file: "Embedded file", docx_hidden_run: "Hidden Word text", docx_comment: "Word comment",
  visibility_gap: "Visibility Gap (vision)", transparent: "Transparent text", docx_white: "White Word text",
  docx_tiny: "Tiny Word text", docx_metadata: "Word properties",
};
export const CATEGORY_LABELS: Record<string, string> = {
  prompt_injection: "Prompt injection", data_exfiltration: "Data exfiltration", keyword_stuffing: "Keyword stuffing",
  benign_hidden: "Harmless", unclassified: "Unclassified",
};
