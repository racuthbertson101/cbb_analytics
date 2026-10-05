/** Shared display formatters. Season numbers are the year the season ends (2026 = 2025-26); UI copy never shows raw end years. */

/** Season label for a season-ending year: 2026 -> "2025-26". */
export const seasonLabel = (y: number) => `${y - 1}-${String(y).slice(2)}`;

/** Range of seasons: (2012, 2026) -> "2011-12 to 2025-26". */
export const seasonRange = (a: number, b: number) => (a === b ? seasonLabel(a) : `${seasonLabel(a)} to ${seasonLabel(b)}`);
