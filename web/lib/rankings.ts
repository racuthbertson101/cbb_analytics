import type { Game, Ratings } from "./data";

export type Row = {
  id: string; rank: number; rankPrev: number | null; w: number; l: number; cw: number; cl: number;
  off: number; def: number; margin: number; tempo: number; sos: number | null; luck: number | null; trend: number[];
};

/** Index of the last ratings snapshot whose date is <= asof (snapshot D uses games strictly before D). */
export function dateIndex(dates: string[], asof: string): number {
  let lo = 0, hi = dates.length - 1, ans = -1;
  while (lo <= hi) {
    const m = (lo + hi) >> 1;
    if (dates[m] <= asof) { ans = m; lo = m + 1; } else hi = m - 1;
  }
  return ans;
}

function ranksAt(R: Ratings, i: number): Map<string, number> {
  const arr = R.teams.map((t, j) => [t, (R.off[i][j] ?? NaN) - (R.def[i][j] ?? NaN)] as const).filter((x) => isFinite(x[1]));
  arr.sort((a, b) => b[1] - a[1]);
  return new Map(arr.map(([t], r) => [t, r + 1]));
}

/** All table values as of a date. Records/SOS/luck use only games strictly before `asof` (or the whole season for the final snapshot). */
export function computeRankings(R: Ratings, games: Game[], asof: string, d1Ids: Set<string>, prevDays = 7): Row[] {
  const i = dateIndex(R.dates, asof);
  if (i < 0) return [];
  const isFinal = i === R.dates.length - 1;
  const cutoff = isFinal ? "9999-12-31" : R.dates[i];
  const jOf = new Map(R.teams.map((t, j) => [t, j]));
  const rec = new Map<string, { w: number; l: number; cw: number; cl: number; opp: number[]; exp: number; n: number; act: number }>();
  const get = (t: string) => rec.get(t) ?? (rec.set(t, { w: 0, l: 0, cw: 0, cl: 0, opp: [], exp: 0, n: 0, act: 0 }), rec.get(t)!);
  const margin = (t: string) => { const j = jOf.get(t); return j == null ? null : (R.off[i][j] ?? NaN) - (R.def[i][j] ?? NaN); };
  for (const g of games) {
    if (!g.ok || g.d >= cutoff || g.t === "exhibition") continue;
    const hw = (g.hs as number) > (g.as as number);
    const h = get(g.h), a = get(g.a);
    if (hw) { h.w++; a.l++; } else { h.l++; a.w++; }
    if (g.cg && g.t === "regular") { if (hw) { h.cw++; a.cl++; } else { h.cl++; a.cw++; } }
    if (g.d1) {
      const mh = margin(g.h), ma = margin(g.a);
      if (ma != null && isFinite(ma)) h.opp.push(ma);
      if (mh != null && isFinite(mh)) a.opp.push(mh);
      if (g.p != null) { h.exp += g.p; a.exp += 1 - g.p; h.act += hw ? 1 : 0; a.act += hw ? 0 : 1; h.n++; a.n++; }
    }
  }
  const prevI = dateIndex(R.dates, (() => { const t = new Date(R.dates[i] + "T12:00:00Z"); t.setUTCDate(t.getUTCDate() - prevDays); return t.toISOString().slice(0, 10); })());
  const prevRanks = prevI >= 0 ? ranksAt(R, prevI) : null;
  const now = ranksAt(R, i);
  const rows: Row[] = [];
  const step = Math.max(1, Math.floor(i / 40));
  R.teams.forEach((t, j) => {
    if (!d1Ids.has(t)) return;
    const off = R.off[i][j], def = R.def[i][j];
    const r = rec.get(t);
    if (off == null || def == null || !r || (r.w + r.l === 0 && !isFinal && i > 0)) return;
    const trend: number[] = [];
    for (let k = 0; k <= i; k += step) { const o = R.off[k][j], d = R.def[k][j]; if (o != null && d != null) trend.push(o - d); }
    trend.push(off - def);
    rows.push({
      id: t, rank: now.get(t) ?? 999, rankPrev: prevRanks?.get(t) ?? null, w: r.w, l: r.l, cw: r.cw, cl: r.cl, off, def, margin: off - def,
      tempo: R.tempo[i][j] ?? NaN, sos: r.opp.length ? r.opp.reduce((a, b) => a + b, 0) / r.opp.length : null,
      luck: r.n ? r.act - r.exp : null, trend,
    });
  });
  rows.sort((a, b) => a.rank - b.rank);
  return rows;
}
