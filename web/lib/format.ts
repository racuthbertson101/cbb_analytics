/** Shared display formatters. Season numbers are the year the season ends (2026 = 2025-26); UI copy never shows raw end years. */

/** Season label for a season-ending year: 2026 -> "2025-26". */
export const seasonLabel = (y: number) => `${y - 1}-${String(y).slice(2)}`;

/** Range of seasons: (2012, 2026) -> "2011-12 to 2025-26". */
export const seasonRange = (a: number, b: number) => (a === b ? seasonLabel(a) : `${seasonLabel(a)} to ${seasonLabel(b)}`);

const nf = (d: number, signed = false) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: d, maximumFractionDigits: d, signDisplay: signed ? "exceptZero" : "auto" });
const ok = (x: number | null | undefined): x is number => x != null && Number.isFinite(x);
const DASH = "–";

/** Rating in points (AdjEM, margins, ratings vs average): signed, 1 decimal. "+12.3", "-0.4", "0.0". */
export const fmtRating = (x: number | null | undefined, d = 1) => (ok(x) ? nf(d, true).format(x).replace("-", "−") : DASH);
/** Efficiency or tempo per 100 possessions: unsigned, 1 decimal. */
export const fmtEff = (x: number | null | undefined, d = 1) => (ok(x) ? nf(d).format(x) : DASH);
/** Probability 0-1 as a percent; extremes read "<1%" and ">99%" so a shown 0% or 100% never appears. */
export const fmtPct = (p: number | null | undefined, d = 0) => {
  if (!ok(p)) return DASH;
  if (d === 0 && p < 0.005) return "<1%";
  if (d === 0 && p > 0.995) return ">99%";
  return `${nf(d).format(p * 100)}%`;
};
/** Rate already in percent units (e.g. eFG% stored as 0.523 -> pass 52.3) */
export const fmtRate = (x: number | null | undefined, d = 1) => (ok(x) ? `${nf(d).format(x)}%` : DASH);
/** Counts: thousands separators, no decimals. */
export const fmtInt = (x: number | null | undefined) => (ok(x) ? nf(0).format(Math.round(x)) : DASH);
/** Scores (actual or predicted points): whole numbers. */
export const fmtScore = (x: number | null | undefined) => (ok(x) ? String(Math.round(x)) : DASH);
/** Made-attempted pair: "7-15". */
export const fmtMA = (m: number | null | undefined, a: number | null | undefined) => (ok(m) && ok(a) ? `${m}-${a}` : DASH);
