export const fmt = (x: number | null | undefined, d = 1) => (x == null || !isFinite(x) ? "–" : x.toFixed(d));
export const pct = (x: number | null | undefined, d = 0) => (x == null ? "–" : (x * 100).toFixed(d) + "%");
export const signed = (x: number | null | undefined, d = 1) => (x == null ? "–" : (x > 0 ? "+" : "") + x.toFixed(d));

/** Season label for a season-ending year: 2026 -> "2025-26". */
export const seasonLabel = (y: number) => `${y - 1}-${String(y).slice(2)}`;
/** Season (ending year) that a calendar date belongs to. */
export const seasonOf = (d: string) => {
  const y = +d.slice(0, 4), m = +d.slice(5, 7);
  return m >= 9 ? y + 1 : y;
};
export const addDays = (d: string, n: number) => {
  const t = new Date(d + "T12:00:00Z");
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
};
export const prettyDate = (d: string) =>
  new Date(d + "T12:00:00Z").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

/**
 * Diverging heat scale in OKLCH. t in [0,1]: 0 = worst, 1 = best percentile.
 * Lightness stays in 0.30-0.50 so light text keeps >= 4.5:1 contrast on every cell.
 */
export function heat(t: number | null | undefined): string {
  if (t == null || !isFinite(t)) return "transparent";
  const x = Math.max(0, Math.min(1, t));
  const s = Math.abs(x - 0.5) * 2; // 0 at the middle, 1 at the extremes
  const hue = x < 0.5 ? 38 : 190;
  const L = 0.27 + 0.2 * s;
  const C = 0.02 + 0.115 * s;
  return `oklch(${L.toFixed(3)} ${C.toFixed(3)} ${hue})`;
}

/** Percentile (0..1, higher = better) of each value; nulls stay null. */
export function percentiles(vals: (number | null)[], higherBetter = true): (number | null)[] {
  const idx = vals.map((v, i) => [v, i] as const).filter((x) => x[0] != null).sort((a, b) => (a[0] as number) - (b[0] as number));
  const out: (number | null)[] = vals.map(() => null);
  const n = idx.length;
  idx.forEach(([, i], r) => (out[i] = (higherBetter ? r : n - 1 - r) / Math.max(1, n - 1)));
  return out;
}
