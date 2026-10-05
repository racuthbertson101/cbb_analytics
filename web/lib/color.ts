import type { Team } from "./data";

const lum = (hex: string) => {
  const c = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
/** DEFINITION: below this relative luminance a color disappears against the dark surfaces (navy, black). */
const MIN_LUM = 0.06;

/** A team color that stays visible on the dark theme: the primary color, else the alternate color, else a neutral. */
export function teamColor(t?: Team | null, fallback = "#8b96aa"): string {
  for (const c of [t?.color, t?.alt]) if (c && /^[0-9a-fA-F]{6}$/.test(c) && lum(c) >= MIN_LUM) return `#${c}`;
  return fallback;
}
