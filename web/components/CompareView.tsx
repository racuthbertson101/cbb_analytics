"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Team, useJson, useMeta, useTeams } from "@/lib/data";
import { teamColor } from "@/lib/color";
import { fmtEff, fmtInt, fmtPct, fmtRate, fmtRating, fmtScore, seasonLabel } from "@/lib/format";
import { cdf, interp, Pred, Preseason, RatingsFile, sigmaOf } from "@/lib/predict";
import { prettyDate, seasonOf } from "@/lib/util";
import ShotChart, { Bins } from "./ShotChart";
import Sparkline from "./Sparkline";
import TeamLogo from "./TeamLogo";
import ContextTag from "./ui/ContextTag";
import GameLink, { ScoreLink } from "./ui/GameLink";
import MatchupBar from "./ui/MatchupBar";
import SeasonChip from "./ui/SeasonChip";

/* ---------------- data types ---------------- */
type Pair = [number | null, number | null];
type Profile = {
  rec: [number, number, number, number]; n: number; ff: Record<string, Pair>; mix: Record<string, number | null> | null;
  sys: Record<string, Pair>; res: { q: number[] | null; top50: [number, number]; best: [string, string, number] | null; worst: [string, string, number] | null };
  form: [string, string, string, string, number, number | null][];
  cons: { resid_sd: number | null; resid_sd_pc: number | null; upset_losses: [number, number | null, number]; upset_wins: [number, number | null, number] };
  rot: { cols: string[]; players: (string | number | null)[][]; ht_in: number | null; exp_years: number | null; returning_min_share: number | null };
};
type Profiles = { season: number; asof: string; teams: Record<string, Profile> };
type HRow = [string, string, string, string, number, number, number | null];
type History = { cols: string[]; rows: HRow[] };
type Analogs = { grid_margin: number[]; grid_poss: number[]; cells: ([number, number, number, number, number] | null)[]; seasons: number[]; window: { margin: number; poss: number } };
type AnalogGames = { cols: string[]; rows: (string | number)[][] };
type MatchEval = { results: { per_feature: Record<string, { improvement: number; seasons_improved: number; passes: boolean }> } | null; adoption_rule: { of_seasons: number } };
type Snap = { teams: string[]; off: (number | null)[]; def: (number | null)[]; tempo: (number | null)[]; mu: number; hca: number; date?: string };
type Out = {
  missing: false; poss: number; k: number; m: number; sa: number; sb: number; p: number; sd: number; lo: number; hi: number;
  parts: [string, number][]; sens: number[]; ratings: { oA: number; dA: number; oB: number; dB: number; tA: number; tB: number };
};

const card = "card p-5";
const h2 = "mb-3 flex items-center text-sm font-medium uppercase tracking-wider text-muted";
const SYS: [string, string][] = [["adj", "Adjusted efficiency"], ["cons", "Consensus"], ["elo", "Elo"], ["bt", "Bradley-Terry"], ["pd", "Player-driven"], ["mrank", "Mean rank"], ["wab", "Wins above bubble"], ["sor", "Strength of record"], ["sos", "Strength of schedule"], ["ncsos", "Non-conference SOS"]];
const FF: { k: string; label: string }[] = [{ k: "efg", label: "Effective FG%" }, { k: "tov", label: "Turnover %" }, { k: "orb", label: "Off. rebound %" }, { k: "ftr", label: "FT rate" }];
const siteOf = (v: string | null) => (v === "a" || v === "1" ? 1 : v === "b" || v === "-1" ? -1 : 0);
const siteKey = (s: number) => (s === 1 ? "a" : s === -1 ? "b" : "n");
const pctOf = (xs: number[], v: number, higher = true) => xs.filter((x) => (higher ? x < v : x > v)).length / Math.max(xs.length, 1);
const ordinal = (n: number) => `${n}${["th", "st", "nd", "rd"][(n % 100 >= 11 && n % 100 <= 13) || n % 10 > 3 ? 0 : n % 10]}`;

/** Snapshot of one season's ratings: as of a date in the ratings file (latest by default), or the preseason file. */
function snapshot(R: RatingsFile | null | undefined, PRE: Preseason | null | undefined, asof: string | null): Snap | null {
  if (R) {
    let i = R.dates.length - 1;
    if (asof) { const k = R.dates.findIndex((d) => d > asof); i = k > 0 ? k - 1 : k === 0 ? 0 : i; }
    return { teams: R.teams, off: R.off[i], def: R.def[i], tempo: R.tempo[i], mu: R.mu[i], hca: R.hca[i], date: R.dates[i] };
  }
  return PRE ? { ...PRE } : null;
}

function useSeason(season: number, asof: string | null) {
  const meta = useMeta();
  const pre = !!meta && meta.upcoming_season === season;
  const { data: R } = useJson<RatingsFile>(meta && season && !pre ? `ratings/${season}.json` : null);
  const { data: PRE } = useJson<Preseason>(pre ? `ratings/${season}_preseason.json` : null);
  const { data: P } = useJson<Profiles>(meta && season && !pre && season >= 2010 ? `profiles/${season}.json` : null);
  const snap = useMemo(() => snapshot(R, PRE, asof), [R, PRE, asof]);
  return { pre, R, snap, prof: P };
}

/* ---------------- page ---------------- */
export default function CompareView() {
  const meta = useMeta();
  const { teams, map } = useTeams();
  const sp = useSearchParams();
  const router = useRouter();
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const seasonB = Number(sp.get("seasonB")) || season;
  const cross = seasonB !== season;
  const a = sp.get("a") || "130", b = sp.get("b") || "150";
  const site = cross ? 0 : siteOf(sp.get("site"));
  const asof = sp.get("asof");
  const set = (kv: Record<string, string | null>) => {
    const p = new URLSearchParams(sp.toString());
    Object.entries(kv).forEach(([k, v]) => (v == null ? p.delete(k) : p.set(k, v)));
    router.replace(`?${p}`, { scroll: false });
  };
  const SA = useSeason(season, cross ? null : asof), SB = useSeason(seasonB, cross ? null : asof);
  const { data: PP } = useJson<Pred>("params/predict.json");
  const { data: ME } = useJson<MatchEval>("params/matchup_eval.json");
  const ta = map.get(a), tb = map.get(b);
  const ca = teamColor(ta, "#f2b544"), cb = teamColor(tb, "#4cc9c0");
  const pa = SA.prof?.teams[a], pb = SB.prof?.teams[b];

  /** Prediction: same formula as the model; cross-season = ratings relative to each season's mean, neutral, later season's tempo context. */
  const out = useMemo((): Out | { missing: true } | null => {
    const A = SA.snap, B = SB.snap;
    if (!PP || !A || !B) return null;
    const i = A.teams.indexOf(a), j = B.teams.indexOf(b);
    if (i < 0 || j < 0 || A.off[i] == null || B.off[j] == null) return { missing: true };
    const meanT = (S: Snap) => { const xs = S.tempo.filter((x): x is number => x != null); return xs.reduce((s, x) => s + x, 0) / xs.length; };
    const L = season >= seasonB ? A : B;
    const mu = L.mu, hca = A.hca;
    const oA = (A.off[i] as number) - A.mu, dA = (A.def[i] as number) - A.mu, oB = (B.off[j] as number) - B.mu, dB = (B.def[j] as number) - B.mu;
    const tA = (A.tempo[i] as number) - meanT(A) + meanT(L), tB = (B.tempo[j] as number) - meanT(B) + meanT(L);
    const poss = (tA + tB) / 2, k = poss / 100, adv = hca * site;
    const ea = mu + oA + dB + adv, eb = mu + oB + dA - adv;
    const m = (ea - eb) * k;
    const prob = (mm: number) => interp(cdf(mm / sigmaOf(PP, poss)), PP.cal_x, PP.cal_y);
    return {
      missing: false, poss, k, m, sa: ea * k, sb: eb * k, p: prob(m), sd: sigmaOf(PP, poss), lo: m + PP.q10, hi: m + PP.q90,
      parts: [["A offense", oA * k], ["B offense", -oB * k], ["A defense", -dA * k], ["B defense", dB * k], ["Home court", 2 * adv * k]],
      sens: [1, 0, -1].map((s) => prob(m + 2 * hca * k * (s - site))),
      ratings: { oA: A.off[i] as number, dA: A.def[i] as number, oB: B.off[j] as number, dB: B.def[j] as number, tA: A.tempo[i] as number, tB: B.tempo[j] as number },
    };
  }, [SA.snap, SB.snap, PP, a, b, site, season, seasonB]);

  const tag = (feature?: string) => {
    const r = feature ? ME?.results?.per_feature[feature] : null;
    return <ContextTag kind="context" title={r ? `Context only: tested out of sample, did not improve predictions (log loss change ${r.improvement > 0 ? "+" : ""}${r.improvement.toFixed(5)}; better in ${r.seasons_improved} of ${ME?.adoption_rule.of_seasons} seasons). See Methodology.` : "Shown for context; not part of the prediction."} />;
  };
  const nameA = ta?.short ?? "A", nameB = tb?.short ?? "B";
  const seasons = [...(meta?.seasons ?? []), ...(meta?.upcoming_season ? [meta.upcoming_season] : [])].reverse();
  const live = !!meta && season === meta.current_season && !cross;

  return (
    <div className="mx-auto max-w-[1400px]">
      <Header teams={teams ?? []} ta={ta} tb={tb} ca={ca} cb={cb} pa={pa} pb={pb} season={season} seasonB={seasonB} cross={cross} site={site} seasons={seasons} set={set} a={a} b={b} asof={asof} dates={live ? SA.R?.dates : undefined} />
      {cross && <div className="card mb-6 border-accent/40 px-4 py-3 text-[13px] text-muted"><b className="text-accent">Hypothetical:</b> different seasons ({seasonLabel(season)} {nameA} vs {seasonLabel(seasonB)} {nameB}). Ratings are relative to each season&apos;s average, on a neutral floor, at the later season&apos;s pace.</div>}
      {!out ? <div className="skeleton h-72" /> : out.missing ? (
        <div className="card p-8 text-center text-muted">One of these teams has no rating in the chosen season. Pick another season.</div>
      ) : (
        <>
          <section className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[3fr_2fr]">
            <PredictionBlock out={out} nameA={nameA} nameB={nameB} ca={ca} cb={cb} cross={cross} />
            <Waterfall out={out} nameA={nameA} nameB={nameB} />
          </section>
          <section className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
            <OffDef out={out} snapA={SA.snap} snapB={SB.snap} nameA={nameA} nameB={nameB} />
            <Tempo out={out} snapA={SA.snap} snapB={SB.snap} nameA={nameA} nameB={nameB} tag={tag("tempo_clash")} />
          </section>
          {!pa || !pb ? (
            <div className="card mb-6 p-5 text-sm text-muted">Season stats, résumé, form and rotation sections appear once both teams have played games in the chosen season{SA.pre || SB.pre ? " (preseason ratings only so far)" : ""}.</div>
          ) : (
            <>
              <FourFactors pa={pa} pb={pb} nameA={nameA} nameB={nameB} tag={tag("joint")} />
              <section className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                <Shooting pa={pa} pb={pb} nameA={nameA} nameB={nameB} ca={ca} cb={cb} tag={tag("three_point")} season={season} seasonB={seasonB} a={a} b={b} />
                <BallSecurity pa={pa} pb={pb} nameA={nameA} nameB={nameB} ca={ca} cb={cb} tag={tag("turnovers")} />
              </section>
              <section className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                <Systems pa={pa} pb={pb} nameA={nameA} nameB={nameB} ca={ca} cb={cb} tag={tag()} />
                <Resume pa={pa} pb={pb} nameA={nameA} nameB={nameB} map={map} season={season} seasonB={seasonB} tag={tag()} />
              </section>
              <Form pa={pa} pb={pb} nameA={nameA} nameB={nameB} map={map} season={season} seasonB={seasonB} R={SA.R} RB={SB.R} a={a} b={b} ca={ca} cb={cb} tag={tag()} />
            </>
          )}
          <HistoryBlocks a={a} b={b} nameA={nameA} nameB={nameB} map={map} season={season} cross={cross} live={live} tagRest={tag("rest")} tag={tag()} />
          {pa && pb && (
            <>
              <Rotation pa={pa} pb={pb} nameA={nameA} nameB={nameB} season={season} seasonB={seasonB} tag={tag()} />
              <Consistency pa={pa} pb={pb} nameA={nameA} nameB={nameB} tag={tag()} />
            </>
          )}
          <AnalogsBlock out={out} nameA={nameA} nameB={nameB} pa={pa} pb={pb} map={map} tag={tag()} />
          <p className="mb-10 text-xs text-faint">The prediction uses adjusted offense, defense and tempo, the fitted home-court advantage, the tempo-dependent spread and the calibrated win probability (Methodology). Sections tagged &ldquo;context only&rdquo; are not part of the prediction; hover a tag to see whether and how it was tested.</p>
        </>
      )}
    </div>
  );
}

/* ---------------- 1. header and controls ---------------- */
function TeamPicker({ teams, value, onPick, id }: { teams: Team[]; value?: Team; onPick: (id: string) => void; id: string }) {
  const [q, setQ] = useState<string | null>(null);
  return (
    <>
      <input list={id} className="w-full" placeholder="Type a team…" value={q ?? value?.name ?? ""} onFocus={() => setQ("")} onBlur={() => setQ(null)}
        onChange={(e) => { setQ(e.target.value); const t = teams.find((x) => x.name === e.target.value); if (t) { onPick(t.id); setQ(null); e.currentTarget.blur(); } }} aria-label="Pick a team" />
      <datalist id={id}>{teams.map((t) => <option key={t.id} value={t.name} />)}</datalist>
    </>
  );
}

function Header({ teams, ta, tb, ca, cb, pa, pb, season, seasonB, cross, site, seasons, set, a, b, asof, dates }: {
  teams: Team[]; ta?: Team; tb?: Team; ca: string; cb: string; pa?: Profile; pb?: Profile; season: number; seasonB: number; cross: boolean; site: number;
  seasons: number[]; set: (kv: Record<string, string | null>) => void; a: string; b: string; asof: string | null; dates?: string[];
}) {
  const sorted = useMemo(() => [...teams].sort((x, y) => x.name.localeCompare(y.name)), [teams]);
  const side = (t: Team | undefined, p: Profile | undefined, s: number, color: string, right: boolean, key: "a" | "b") => (
    <div className={`flex min-w-0 items-center gap-3 ${right ? "flex-row-reverse text-right" : ""}`}>
      <span className="h-12 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
      <TeamLogo team={t} size={48} />
      <div className="min-w-0 flex-1">
        <TeamPicker teams={sorted} value={t} onPick={(id) => set({ [key]: id })} id={`pick-${key}`} />
        <div className="mt-1 truncate text-xs text-muted">{t?.conf[String(s)] ?? ""}{p ? ` · ${p.rec[0]}-${p.rec[1]} (${p.rec[2]}-${p.rec[3]} conf)` : ""} · {seasonLabel(s)}</div>
      </div>
    </div>
  );
  return (
    <div className="sticky top-[57px] z-20 -mx-2 mb-6 rounded-b-xl border-b border-line bg-bg/95 px-2 pb-3 pt-3 backdrop-blur">
      <div className="mb-2 flex items-baseline gap-2"><h1 className="text-3xl font-semibold">Compare</h1><SeasonChip season={season} note={cross ? `vs ${seasonLabel(seasonB)}` : undefined} /></div>
      <div className="grid grid-cols-1 items-center gap-4 lg:grid-cols-[1fr_auto_1fr]">
        {side(ta, pa, season, ca, false, "a")}
        <span className="text-center text-faint">vs</span>
        {side(tb, pb, seasonB, cb, true, "b")}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-xs uppercase tracking-wider text-muted">Site</span>
        <div className="inline-flex overflow-hidden rounded-md border border-line" role="group" aria-label="Site">
          {[1, 0, -1].map((v) => (
            <button key={v} disabled={cross && v !== 0} onClick={() => set({ site: siteKey(v) })} aria-pressed={site === v}
              className={`px-3 py-1 text-xs ${site === v ? "bg-surface2 text-accent" : "text-muted hover:text-ink"} disabled:opacity-40`}>
              {v === 1 ? `${ta?.short ?? "A"} home` : v === 0 ? "Neutral" : `${tb?.short ?? "B"} home`}
            </button>
          ))}
        </div>
        <span className="ml-3 text-xs uppercase tracking-wider text-muted">Season</span>
        <select value={season} onChange={(e) => set({ season: e.target.value, seasonB: cross ? String(seasonB) : null, asof: null })} aria-label="Season for team A">
          {seasons.map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
        </select>
        <label className="flex items-center gap-1 text-xs text-muted">
          <input type="checkbox" checked={cross} onChange={(e) => set({ seasonB: e.target.checked ? String(seasons.find((s) => s !== season) ?? season) : null, site: e.target.checked ? "n" : null })} />
          different season for {tb?.short ?? "B"}
        </label>
        {cross && <select value={seasonB} onChange={(e) => set({ seasonB: e.target.value })} aria-label="Season for team B">{seasons.map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}</select>}
        {dates && dates.length > 1 && (
          <>
            <span className="ml-3 text-xs uppercase tracking-wider text-muted">Ratings as of</span>
            <select value={asof ?? ""} onChange={(e) => set({ asof: e.target.value || null })} aria-label="Ratings as of date">
              <option value="">latest</option>{dates.slice().reverse().map((d) => <option key={d} value={d}>{prettyDate(d)}</option>)}
            </select>
          </>
        )}
        <button className="ml-auto text-xs text-muted hover:text-ink" onClick={() => set({ a: b, b: a, season: String(seasonB), seasonB: cross ? String(season) : null, site: siteKey(-site) })}>Swap ⇄</button>
      </div>
    </div>
  );
}

/* ---------------- 2-3. prediction and waterfall ---------------- */
function PredictionBlock({ out, nameA, nameB, ca, cb, cross }: { out: Out; nameA: string; nameB: string; ca: string; cb: string; cross: boolean }) {
  const pBy10 = 1 - cdf((10 - out.m) / out.sd), pClose = cdf((3 - out.m) / out.sd) - cdf((-3 - out.m) / out.sd);
  return (
    <div className={card}>
      <h2 className={h2}>Prediction<ContextTag kind="model" /></h2>
      <div className="grid grid-cols-3 items-center text-center">
        <div><div className="num text-6xl font-semibold">{fmtScore(out.sa)}</div><div className="text-sm text-muted">{nameA}</div></div>
        <div className="text-xs text-muted">{out.m >= 0 ? nameA : nameB} by {fmtEff(Math.abs(out.m))}<br />total {fmtScore(out.sa + out.sb)} · {fmtEff(out.poss)} poss.</div>
        <div><div className="num text-6xl font-semibold">{fmtScore(out.sb)}</div><div className="text-sm text-muted">{nameB}</div></div>
      </div>
      <div className="mt-4"><MatchupBar label="Win probability" a={out.p} b={1 - out.p} fmt={(x) => fmtPct(x, 1)} ca={ca} cb={cb} better="high" /></div>
      <MarginDist out={out} nameA={nameA} ca={ca} cb={cb} />
      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs text-muted">
        <span>80% of results land in <b className="text-ink">{nameA} {fmtRating(out.lo, 0)} to {fmtRating(out.hi, 0)}</b></span>
        <span>{nameA} by 10+: <b className="text-ink">{fmtPct(pBy10)}</b></span>
        <span>Within 3 points: <b className="text-ink">{fmtPct(pClose)}</b></span>
      </div>
      {!cross && (
        <div className="mt-4 grid grid-cols-3 gap-2 border-t border-line pt-3 text-center text-xs">
          {[`${nameA} home`, "Neutral", `${nameB} home`].map((l, i) => <div key={l}><div className="text-muted">{l}</div><div className="num text-sm">{nameA} {fmtPct(out.sens[i])}</div></div>)}
        </div>
      )}
    </div>
  );
}

function MarginDist({ out, nameA, ca, cb }: { out: Out; nameA: string; ca: string; cb: string }) {
  const W = 640, H = 120, x0 = out.m - 3.2 * out.sd, x1 = out.m + 3.2 * out.sd;
  const X = (v: number) => ((v - x0) / (x1 - x0)) * W, Y = (d: number) => H - 20 - d * (H - 30);
  const pts = Array.from({ length: 121 }, (_, i) => x0 + ((x1 - x0) * i) / 120);
  const pdf = (v: number) => Math.exp(-0.5 * ((v - out.m) / out.sd) ** 2);
  const area = (lo: number, hi: number) => { const s = pts.filter((v) => v >= lo && v <= hi); return s.length ? `M${X(s[0])},${Y(0)}` + s.map((v) => `L${X(v).toFixed(1)},${Y(pdf(v)).toFixed(1)}`).join("") + `L${X(s[s.length - 1])},${Y(0)}Z` : ""; };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full" role="img" aria-label={`Distribution of ${nameA}'s margin`}>
      <path d={area(0, x1)} fill={ca} opacity={0.35} />
      <path d={area(x0, 0)} fill={cb} opacity={0.35} />
      <rect x={X(out.lo)} y={Y(1) - 4} width={X(out.hi) - X(out.lo)} height={3} fill="var(--muted)" opacity={0.6} />
      <path d={pts.map((v, i) => `${i ? "L" : "M"}${X(v).toFixed(1)},${Y(pdf(v)).toFixed(1)}`).join("")} fill="none" stroke="var(--text)" strokeWidth={1.3} />
      <line x1={X(out.m)} x2={X(out.m)} y1={Y(1) - 8} y2={Y(0)} stroke="var(--accent)" strokeWidth={2} />
      {x0 < 0 && x1 > 0 && <line x1={X(0)} x2={X(0)} y1={8} y2={Y(0)} stroke="var(--border)" strokeDasharray="3 3" />}
      <line x1={0} x2={W} y1={Y(0)} y2={Y(0)} stroke="var(--border)" />
      {x0 < 0 && x1 > 0 && <text x={X(0)} y={H - 4} textAnchor="middle" fontSize={10} fill="var(--muted)">0</text>}
      <text x={X(out.m)} y={H - 4} textAnchor="middle" fontSize={10} fill="var(--accent)">{nameA} {fmtRating(out.m)}</text>
      <text x={4} y={12} fontSize={10} fill="var(--muted)">{nameA} margin → (bar = 80% of results)</text>
    </svg>
  );
}

function Waterfall({ out, nameA, nameB }: { out: Out; nameA: string; nameB: string }) {
  const rows: [string, number][] = out.parts.map(([l, v]) => [l.replace("A ", `${nameA} `).replace("B ", `${nameB} `), v]);
  const cum = rows.reduce<number[]>((acc, [, v]) => [...acc, (acc[acc.length - 1] ?? 0) + v], []);
  const max = Math.max(1, Math.abs(out.m), ...rows.map(([, v]) => Math.abs(v)), ...cum.map(Math.abs));
  const bars = [...rows, ["Predicted margin", out.m] as [string, number]].map(([l, v], i) => {
    const last = i === rows.length, s = last ? 0 : i ? cum[i - 1] : 0, e = last ? v : cum[i];
    return { l, v, last, lo: Math.min(s, e), hi: Math.max(s, e) };
  });
  return (
    <div className={card}>
      <h2 className={h2}>Where the margin comes from<ContextTag kind="model" /></h2>
      {bars.map(({ l, v, last, lo, hi }) => (
        <div key={l} className="grid grid-cols-[9.5rem_1fr_3.5rem] items-center gap-2 py-1 text-[13px]">
          <span className={last ? "font-medium" : "text-muted"}>{l}</span>
          <div className="relative h-3"><div className="absolute inset-y-0 w-px bg-line" style={{ left: "50%" }} />
            <div className="absolute inset-y-0 rounded-sm" style={{ left: `${50 + (lo / max) * 48}%`, width: `${Math.max(((hi - lo) / max) * 48, 0.4)}%`, background: v >= 0 ? "var(--accent-2)" : "var(--bad)", opacity: last ? 1 : 0.75 }} />
          </div>
          <span className="num text-right">{fmtRating(v)}</span>
        </div>
      ))}
      <p className="mt-3 text-xs text-faint">From {nameA}&apos;s side. Margin = possessions/100 × [(offense A − offense B) + (defense B − defense A) + 2 × home court]. {fmtEff(out.poss)} possessions, so each point per 100 possessions is worth {fmtEff(out.k, 2)} points here.</p>
    </div>
  );
}

/* ---------------- 4-5. tempo and offense vs defense ---------------- */
function ratingPcts(S: Snap | null) {
  if (!S) return null;
  const off = S.off.filter((x): x is number => x != null), def = S.def.filter((x): x is number => x != null), tem = S.tempo.filter((x): x is number => x != null);
  return { off: (v: number) => pctOf(off, v), def: (v: number) => pctOf(def, v, false), tempo: (v: number) => pctOf(tem, v) };
}

function OffDef({ out, snapA, snapB, nameA, nameB }: { out: Out; snapA: Snap | null; snapB: Snap | null; nameA: string; nameB: string }) {
  const PA = ratingPcts(snapA), PB = ratingPcts(snapB);
  if (!PA || !PB) return null;
  const r = out.ratings;
  const verdict = (o: number, d: number) => (o >= 0.7 && d >= 0.7 ? "strength vs strength" : Math.abs(o - d) >= 0.4 ? (o > d ? "mismatch: offense" : "mismatch: defense") : o <= 0.3 && d <= 0.3 ? "weakness vs weakness" : "even");
  const row = (label: string, o: number, op: number, d: number, dp: number) => (
    <div className="py-2">
      <div className="mb-1 flex justify-between text-[13px]"><span>{label}</span><span className="chip">{verdict(op, dp)}</span></div>
      {([["offense", o, op, "var(--accent)"], ["defense", d, dp, "var(--accent-2)"]] as [string, number, number, string][]).map(([k, v, p, c]) => (
        <div key={k} className="grid grid-cols-[5rem_1fr_7rem] items-center gap-2 text-xs text-muted">
          <span>{k}</span>
          <div className="relative h-2 rounded-full bg-surface2"><div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${p * 100}%`, background: c }} /></div>
          <span className="num text-right">{fmtEff(v)} · {ordinal(Math.round(p * 100))}</span>
        </div>
      ))}
    </div>
  );
  return (
    <div className={card}>
      <h2 className={h2}>Offense vs defense<ContextTag kind="model" /></h2>
      {row(`${nameA} offense vs ${nameB} defense`, r.oA, PA.off(r.oA), r.dB, PB.def(r.dB))}
      {row(`${nameB} offense vs ${nameA} defense`, r.oB, PB.off(r.oB), r.dA, PA.def(r.dA))}
      <p className="mt-2 text-xs text-faint">Points per 100 possessions against an average D-I team; percentile among D-I teams (higher = better, for defense too).</p>
    </div>
  );
}

function Tempo({ out, snapA, snapB, nameA, nameB, tag }: { out: Out; snapA: Snap | null; snapB: Snap | null; nameA: string; nameB: string; tag: React.ReactNode }) {
  const PA = ratingPcts(snapA), PB = ratingPcts(snapB);
  if (!PA || !PB) return null;
  const pa = PA.tempo(out.ratings.tA), pb = PB.tempo(out.ratings.tB);
  const ctrl = Math.abs(pa - 0.5) > Math.abs(pb - 0.5) ? nameA : nameB;
  const dots: [number, string, string, number][] = [[pa, nameA, "var(--accent)", out.ratings.tA], [pb, nameB, "var(--accent-2)", out.ratings.tB]];
  return (
    <div className={card}>
      <h2 className={h2}>Tempo clash{tag}</h2>
      <div className="relative mx-6 mb-8 mt-9 h-1.5 rounded-full bg-surface2">
        {dots.map(([p, n, c, v], i) => (
          <div key={n + i} className="absolute -top-1.5" style={{ left: `calc(${p * 100}% - 8px)` }}>
            <div className="h-4 w-4 rounded-full border-2 border-bg" style={{ background: c }} />
            <div className={`absolute ${i ? "top-5" : "-top-6"} left-1/2 -translate-x-1/2 whitespace-nowrap text-xs`}>{n} {fmtEff(v)}</div>
          </div>
        ))}
      </div>
      <div className="flex justify-between text-[11px] text-faint"><span>slowest D-I</span><span>fastest D-I</span></div>
      <p className="mt-3 text-sm">Predicted possessions: <b>{fmtEff(out.poss)}</b> (the average of both teams&apos; adjusted tempos, which is part of the model). {ctrl} plays the more extreme pace; whether either team &ldquo;controls&rdquo; pace was tested and does not predict results.</p>
    </div>
  );
}

/* ---------------- 6-8. four factors, shooting, ball security ---------------- */
function FourFactors({ pa, pb, nameA, nameB, tag }: { pa: Profile; pb: Profile; nameA: string; nameB: string; tag: React.ReactNode }) {
  const cells = FF.flatMap((f) => [
    { f, off: nameA, vo: pa.ff[f.k], vd: pb.ff[f.k + "_d"] },
    { f, off: nameB, vo: pb.ff[f.k], vd: pa.ff[f.k + "_d"] },
  ]);
  const gap = (c: (typeof cells)[0]) => Math.abs((c.vo[1] ?? 0.5) - (c.vd[1] ?? 0.5));
  const key = cells.reduce((m, c) => (gap(c) > gap(m) ? c : m), cells[0]);
  return (
    <div className={`${card} mb-6`}>
      <h2 className={h2}>Four factors, both directions{tag}</h2>
      <div className="grid grid-cols-1 gap-x-8 md:grid-cols-2">
        {[nameA, nameB].map((off) => (
          <div key={off}>
            <div className="mb-1 text-xs text-muted">{off} offense vs {off === nameA ? nameB : nameA} defense</div>
            {cells.filter((c) => c.off === off).map((c) => (
              <div key={c.f.k} className="grid grid-cols-[9.5rem_1fr_1fr] items-center gap-2 border-b border-line/50 py-1.5 text-[13px]">
                <span>{c.f.label}{c === key && <span className="chip ml-1 !border-accent !text-accent">key battle</span>}</span>
                <span className="num">{fmtRate((c.vo[0] ?? NaN) * 100)} <span className="text-xs text-muted">({ordinal(Math.round((c.vo[1] ?? 0) * 100))})</span></span>
                <span className="num text-muted">allowed {fmtRate((c.vd[0] ?? NaN) * 100)} <span className="text-xs">({ordinal(Math.round((c.vd[1] ?? 0) * 100))})</span></span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-faint">Percentiles among D-I teams, higher = better for that side (a low turnover rate on offense, a high forced rate on defense). The key battle is the largest percentile gap.</p>
    </div>
  );
}

function Shooting({ pa, pb, nameA, nameB, ca, cb, tag, season, seasonB, a, b }: { pa: Profile; pb: Profile; nameA: string; nameB: string; ca: string; cb: string; tag: React.ReactNode; season: number; seasonB: number; a: string; b: string }) {
  const meta = useMeta();
  const shotsA = !!meta?.shot_seasons?.includes(season), shotsB = !!meta?.shot_seasons?.includes(seasonB);
  const { data: SA } = useJson<{ bins: Bins }>(shotsA ? `shots/${season}/${a}.json` : null);
  const { data: SB } = useJson<{ bins: Bins }>(shotsB ? `shots/${seasonB}/${b}.json` : null);
  const { data: LA } = useJson<{ bins: Bins }>(shotsA ? `shots/${season}/league.json` : null);
  const pct = (x: number | null) => fmtRate(x == null ? null : x * 100);
  const v = (p: Profile, k: string) => p.ff[k]?.[0] ?? null;
  return (
    <div className={card}>
      <h2 className={h2}>Shooting profile{tag}</h2>
      <div className="mb-1 grid grid-cols-[4.5rem_1fr_9rem_1fr_4.5rem] text-xs text-muted"><span className="col-span-2 text-right">{nameA}</span><span /><span className="col-span-2">{nameB}</span></div>
      <MatchupBar label="3PA rate" a={v(pa, "tpar")} b={v(pb, "tpar")} fmt={pct} ca={ca} cb={cb} better="none" />
      <MatchupBar label="3P%" a={v(pa, "tp_pct")} b={v(pb, "tp_pct")} fmt={pct} ca={ca} cb={cb} />
      <MatchupBar label="2P%" a={v(pa, "two_pct")} b={v(pb, "two_pct")} fmt={pct} ca={ca} cb={cb} />
      <MatchupBar label="FT%" a={v(pa, "ft_pct")} b={v(pb, "ft_pct")} fmt={pct} ca={ca} cb={cb} />
      {pa.mix && pb.mix ? (
        <div className="mt-3 text-xs">
          {(["rim", "mid", "three"] as const).map((z) => (
            <div key={z} className="grid grid-cols-[3.5rem_1fr_1fr] items-center gap-2 py-0.5">
              <span className="text-muted">{z}</span>
              <span>{nameA} {pct(pa.mix?.[z] ?? null)} <span className="text-muted">vs {nameB} allows {pct(pb.mix?.[z + "_d"] ?? null)}</span></span>
              <span>{nameB} {pct(pb.mix?.[z] ?? null)} <span className="text-muted">vs {nameA} allows {pct(pa.mix?.[z + "_d"] ?? null)}</span></span>
            </div>
          ))}
        </div>
      ) : <p className="mt-3 text-xs text-faint">Shot locations (rim / mid-range / three mix) are available from 2025-26.</p>}
      {SA && SB && LA && (
        <div className="mt-3 grid grid-cols-2 gap-3">
          <ShotChart bins={SA.bins} league={LA.bins} title={nameA} />
          <ShotChart bins={SB.bins} league={LA.bins} title={nameB} />
        </div>
      )}
    </div>
  );
}

function BallSecurity({ pa, pb, nameA, nameB, ca, cb, tag }: { pa: Profile; pb: Profile; nameA: string; nameB: string; ca: string; cb: string; tag: React.ReactNode }) {
  const pct = (x: number | null) => fmtRate(x == null ? null : x * 100);
  const v = (p: Profile, k: string) => p.ff[k]?.[0] ?? null;
  return (
    <div className={card}>
      <h2 className={h2}>Ball security and fouls{tag}</h2>
      <div className="mb-1 grid grid-cols-[4.5rem_1fr_9rem_1fr_4.5rem] text-xs text-muted"><span className="col-span-2 text-right">{nameA}</span><span /><span className="col-span-2">{nameB}</span></div>
      <MatchupBar label="Turnover %" a={v(pa, "tov")} b={v(pb, "tov")} fmt={pct} ca={ca} cb={cb} better="low" />
      <MatchupBar label="Forced TO %" a={v(pa, "tov_d")} b={v(pb, "tov_d")} fmt={pct} ca={ca} cb={cb} />
      <MatchupBar label="Steal rate" a={v(pa, "stl")} b={v(pb, "stl")} fmt={pct} ca={ca} cb={cb} />
      <MatchupBar label="Fouls per game" a={v(pa, "pf")} b={v(pb, "pf")} fmt={(x) => fmtEff(x)} ca={ca} cb={cb} better="low" />
      <MatchupBar label="Opp. FT rate" a={v(pa, "ftr_d")} b={v(pb, "ftr_d")} fmt={pct} ca={ca} cb={cb} better="low" />
    </div>
  );
}

/* ---------------- 9-11. systems, résumé, form ---------------- */
function Systems({ pa, pb, nameA, nameB, ca, cb, tag }: { pa: Profile; pb: Profile; nameA: string; nameB: string; ca: string; cb: string; tag: React.ReactNode }) {
  const rows = SYS.filter(([k]) => pa.sys[k] || pb.sys[k]);
  const x = (r: number | null) => (r == null ? null : (1 - (r - 1) / 365) * 100);
  return (
    <div className={card}>
      <h2 className={h2}>Every ranking system{tag}</h2>
      <table className="dense">
        <thead><tr><th className="l">System</th><th>{nameA}</th><th className="l" style={{ width: "36%" }}>Rank (right = better)</th><th>{nameB}</th></tr></thead>
        <tbody>{rows.map(([k, l]) => {
          const [va, ra] = pa.sys[k] ?? [null, null], [vb, rb] = pb.sys[k] ?? [null, null];
          const xa = x(ra), xb = x(rb);
          return (
            <tr key={k}><td className="l">{l}</td><td className="num">{k === "sor" ? fmtPct(va, 1) : fmtEff(va)} <span className="text-xs text-muted">#{ra ?? "–"}</span></td>
              <td className="l"><div className="relative h-3">
                <div className="absolute inset-x-0 top-1.5 h-px bg-line" />
                {xa != null && xb != null && <div className="absolute top-1.5 h-px bg-muted" style={{ left: `${Math.min(xa, xb)}%`, width: `${Math.abs(xa - xb)}%` }} />}
                {xa != null && <div className="absolute top-0 h-3 w-3 -translate-x-1/2 rounded-full" style={{ left: `${xa}%`, background: ca }} />}
                {xb != null && <div className="absolute top-0 h-3 w-3 -translate-x-1/2 rounded-full" style={{ left: `${xb}%`, background: cb }} />}
              </div></td>
              <td className="num">{k === "sor" ? fmtPct(vb, 1) : fmtEff(vb)} <span className="text-xs text-muted">#{rb ?? "–"}</span></td></tr>
          );
        })}</tbody>
      </table>
      <p className="mt-2 text-xs text-faint">Dots run from rank 365 (left) to 1 (right). Every system is explained on Methodology.</p>
    </div>
  );
}

function Resume({ pa, pb, nameA, nameB, map, season, seasonB, tag }: { pa: Profile; pb: Profile; nameA: string; nameB: string; map: Map<string, Team>; season: number; seasonB: number; tag: React.ReactNode }) {
  const q = (p: Profile) => (p.res.q ? [0, 2, 4, 6].map((i) => `${p.res.q![i]}-${p.res.q![i + 1]}`) : ["–", "–", "–", "–"]);
  const g = (x: [string, string, number] | null, s: number) => (x ? <ScoreLink id={x[0]} season={s}>{fmtRating(x[2], 0)} vs {map.get(x[1])?.short ?? "Non-D-I"}</ScoreLink> : "–");
  const rows: [string, React.ReactNode, React.ReactNode][] = [
    ["Quadrant 1", q(pa)[0], q(pb)[0]], ["Quadrant 2", q(pa)[1], q(pb)[1]], ["Quadrant 3", q(pa)[2], q(pb)[2]], ["Quadrant 4", q(pa)[3], q(pb)[3]],
    ["vs top 50", `${pa.res.top50[0]}-${pa.res.top50[1]}`, `${pb.res.top50[0]}-${pb.res.top50[1]}`],
    ["SOS", fmtRating(pa.sys.sos?.[0] ?? null), fmtRating(pb.sys.sos?.[0] ?? null)],
    ["Non-conf SOS", fmtRating(pa.sys.ncsos?.[0] ?? null), fmtRating(pb.sys.ncsos?.[0] ?? null)],
    ["Best win", g(pa.res.best, season), g(pb.res.best, seasonB)], ["Worst loss", g(pa.res.worst, season), g(pb.res.worst, seasonB)],
  ];
  return (
    <div className={card}>
      <h2 className={h2}>Résumé and schedule{tag}</h2>
      <table className="dense"><thead><tr><th className="l"></th><th>{nameA}</th><th>{nameB}</th></tr></thead>
        <tbody>{rows.map(([l, xa, xb]) => <tr key={l}><td className="l text-muted">{l}</td><td>{xa}</td><td>{xb}</td></tr>)}</tbody></table>
      <p className="mt-2 text-xs text-faint">Quadrants use NCAA cutoffs with our rating in place of NET. Best win = highest-rated opponent beaten; worst loss = lowest-rated opponent lost to.</p>
    </div>
  );
}

function Form({ pa, pb, nameA, nameB, map, season, seasonB, R, RB, a, b, ca, cb, tag }: { pa: Profile; pb: Profile; nameA: string; nameB: string; map: Map<string, Team>; season: number; seasonB: number; R?: RatingsFile | null; RB?: RatingsFile | null; a: string; b: string; ca: string; cb: string; tag: React.ReactNode }) {
  const spark = (Rf: RatingsFile | null | undefined, id: string) => {
    if (!Rf) return [];
    const i = Rf.teams.indexOf(id);
    return i < 0 ? [] : Rf.dates.map((_, k) => (Rf.off[k][i] == null ? null : (Rf.off[k][i] as number) - (Rf.def[k][i] as number))).filter((v): v is number => v != null);
  };
  const panel = (p: Profile, name: string, s: number, c: string, Rf: RatingsFile | null | undefined, id: string) => {
    const xs = p.form.filter((r) => r[5] != null);
    const max = Math.max(5, ...xs.map((r) => Math.abs(r[4] - (r[5] as number))));
    const avg = xs.length ? xs.reduce((t, r) => t + r[4] - (r[5] as number), 0) / xs.length : null;
    return (
      <div>
        <div className="mb-2 flex items-center justify-between text-xs text-muted"><span>{name}: last {p.form.length} games, result minus pregame prediction</span><Sparkline data={spark(Rf, id)} color={c} /></div>
        {p.form.map((r) => {
          const d = r[5] == null ? null : r[4] - r[5];
          return (
            <div key={r[0]} className="grid grid-cols-[3.2rem_7rem_1fr_3.2rem] items-center gap-2 py-0.5 text-xs">
              <span className="text-muted">{r[1].slice(5)}</span>
              <span className="truncate">{r[3] === "A" ? "@ " : r[3] === "N" ? "vs " : ""}{map.get(r[2])?.short ?? "Non-D-I"}</span>
              <div className="relative h-2"><div className="absolute inset-y-0 w-px bg-line" style={{ left: "50%" }} />
                {d != null && <div className="absolute inset-y-0 rounded-sm" style={{ left: `${50 + Math.min(0, d / max) * 50}%`, width: `${(Math.abs(d) / max) * 50}%`, background: d >= 0 ? "var(--good)" : "var(--bad)" }} />}</div>
              <ScoreLink id={r[0]} season={s} className={`num text-right ${r[4] > 0 ? "text-accent2" : "text-[var(--bad)]"}`}>{r[4] > 0 ? "W" : "L"} {fmtRating(r[4], 0)}</ScoreLink>
            </div>
          );
        })}
        {avg != null && <p className="mt-1 text-xs text-muted">Average vs expectation: <b className="text-ink">{fmtRating(avg)}</b></p>}
      </div>
    );
  };
  return (
    <div className={`${card} mb-6`}>
      <h2 className={h2}>Recent form vs expectation{tag}</h2>
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">{panel(pa, nameA, season, ca, R, a)}{panel(pb, nameB, seasonB, cb, RB, b)}</div>
      <p className="mt-2 text-xs text-faint">Bars: actual margin minus the pregame predicted margin (green = better than expected). Sparkline: adjusted efficiency margin through the season.</p>
    </div>
  );
}

/* ---------------- 12-14. rest, common opponents, head-to-head ---------------- */
function HistoryBlocks({ a, b, nameA, nameB, map, season, cross, live, tagRest, tag }: { a: string; b: string; nameA: string; nameB: string; map: Map<string, Team>; season: number; cross: boolean; live: boolean; tagRest: React.ReactNode; tag: React.ReactNode }) {
  const { data: HA } = useJson<History>(`teamhistory/${a}.json`);
  const { data: HB } = useJson<History>(`teamhistory/${b}.json`);
  if (!HA || !HB) return <div className="skeleton mb-6 h-40" />;
  const inSeason = (h: History) => h.rows.filter((r) => seasonOf(r[1]) === season);
  const h2h = HA.rows.filter((r) => r[2] === b).slice().reverse();
  const ra = inSeason(HA), rb = inSeason(HB);
  const opps = (rows: HRow[]) => { const m = new Map<string, HRow[]>(); rows.forEach((r) => m.set(r[2], [...(m.get(r[2]) ?? []), r])); return m; };
  const oa = opps(ra), ob = opps(rb);
  const common = cross ? [] : [...oa.keys()].filter((k) => ob.has(k) && k !== a && k !== b);
  const vsExp = (rows: HRow[]) => { const xs = rows.filter((r) => r[6] != null).map((r) => r[4] - r[5] - (r[6] as number)); return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null; };
  const sumA = vsExp(common.flatMap((k) => oa.get(k) ?? [])), sumB = vsExp(common.flatMap((k) => ob.get(k) ?? []));
  const res = (r: HRow) => <ScoreLink key={r[0]} id={r[0]} season={seasonOf(r[1])} className={r[4] > r[5] ? "text-accent2" : "text-[var(--bad)]"}>{r[4] > r[5] ? "W" : "L"} {r[4]}-{r[5]}</ScoreLink>;
  const today = new Date().toISOString().slice(0, 10);
  const rest = (rows: HRow[]) => {
    const past = rows.filter((r) => r[1] <= today);
    if (!past.length) return null;
    const days = (d: string) => (Date.parse(today) - Date.parse(d)) / 864e5;
    return { since: Math.round(days(past[past.length - 1][1])), in7: past.filter((r) => days(r[1]) <= 7).length, road10: past.filter((r) => days(r[1]) <= 10 && r[3] === "A").length };
  };
  const rsA = live ? rest(ra) : null, rsB = live ? rest(rb) : null;
  return (
    <section className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[2fr_3fr]">
      <div className="space-y-6">
        <div className={card}>
          <h2 className={h2}>Head-to-head since 2008{tag}</h2>
          {h2h.length ? (
            <table className="dense"><thead><tr><th className="l">Date</th><th className="l">Site</th><th>Score</th><th>Pred</th><th>vs exp</th></tr></thead>
              <tbody>{h2h.slice(0, 12).map((r) => (
                <tr key={r[0]}><td className="l text-muted">{prettyDate(r[1])}</td><td className="l text-muted">{r[3] === "N" ? "Neutral" : r[3] === "H" ? `@ ${nameA}` : `@ ${nameB}`}</td>
                  <td>{res(r)}</td><td>{r[6] == null ? "–" : fmtRating(r[6])}</td><td>{r[6] == null ? "–" : fmtRating(r[4] - r[5] - r[6])}</td></tr>))}</tbody></table>
          ) : <p className="text-sm text-muted">No meetings since 2007-08.</p>}
          <p className="mt-2 text-xs text-faint">From {nameA}&apos;s side. Pred = pregame predicted margin (walk-forward).</p>
        </div>
        {live && (rsA || rsB) && (
          <div className={card}>
            <h2 className={h2}>Rest and schedule{tagRest}</h2>
            <table className="dense"><thead><tr><th className="l"></th><th>{nameA}</th><th>{nameB}</th></tr></thead>
              <tbody>
                <tr><td className="l text-muted">Days since last game</td><td>{rsA?.since ?? "–"}</td><td>{rsB?.since ?? "–"}</td></tr>
                <tr><td className="l text-muted">Games in last 7 days</td><td>{rsA?.in7 ?? "–"}</td><td>{rsB?.in7 ?? "–"}</td></tr>
                <tr><td className="l text-muted">Road games in last 10 days</td><td>{rsA?.road10 ?? "–"}</td><td>{rsB?.road10 ?? "–"}</td></tr>
              </tbody></table>
          </div>
        )}
      </div>
      <div className={card}>
        <h2 className={h2}>Common opponents {cross ? "" : `in ${seasonLabel(season)}`}{tag}</h2>
        {cross ? <p className="text-sm text-muted">Not shown for teams from different seasons.</p> : common.length ? (
          <>
            <table className="dense"><thead><tr><th className="l">Opponent</th><th className="l">{nameA}</th><th className="l">{nameB}</th></tr></thead>
              <tbody>{common.slice(0, 14).map((o) => (
                <tr key={o}><td className="l"><span className="inline-flex items-center gap-2"><TeamLogo team={map.get(o)} size={16} />{map.get(o)?.short ?? "Non-D-I"}</span></td>
                  <td className="l"><span className="inline-flex gap-3">{(oa.get(o) ?? []).map(res)}</span></td>
                  <td className="l"><span className="inline-flex gap-3">{(ob.get(o) ?? []).map(res)}</span></td></tr>))}</tbody></table>
            <p className="mt-2 text-sm">Against {common.length} common opponents, {nameA} averaged <b>{fmtRating(sumA)}</b> and {nameB} <b>{fmtRating(sumB)}</b> points versus the pregame expectation.</p>
          </>
        ) : <p className="text-sm text-muted">No common opponents this season.</p>}
      </div>
    </section>
  );
}

/* ---------------- 15-17. rotation, consistency, analogs ---------------- */
function Rotation({ pa, pb, nameA, nameB, season, seasonB, tag }: { pa: Profile; pb: Profile; nameA: string; nameB: string; season: number; seasonB: number; tag: React.ReactNode }) {
  const panel = (p: Profile, name: string, s: number) => (
    <div>
      <div className="mb-1 text-xs text-muted">{name}: minutes-weighted height {p.rot.ht_in != null ? `${Math.floor(p.rot.ht_in / 12)}′${fmtEff(p.rot.ht_in % 12)}″` : "–"} · experience {p.rot.exp_years != null ? `${fmtEff(p.rot.exp_years)} yrs` : "–"} · returning minutes {fmtPct(p.rot.returning_min_share)}</div>
      <table className="dense"><thead><tr><th className="l">Player</th><th className="l">Class</th><th className="l">Ht</th><th>MPG</th><th>USG</th><th>TS%</th></tr></thead>
        <tbody>{p.rot.players.map((r) => (
          <tr key={String(r[0])}><td className="l"><Link className="hover:text-accent" href={`/player/?id=${r[0]}&season=${s}`}>{r[1]}</Link></td>
            <td className="l text-muted">{r[2] ?? ""}</td><td className="l text-muted">{r[3] ?? ""}</td><td>{fmtEff(r[4] as number)}</td><td>{fmtEff(r[5] as number)}</td><td>{fmtRate(r[6] == null ? null : (r[6] as number) * 100)}</td></tr>))}</tbody></table>
    </div>
  );
  return (
    <div className={`${card} mb-6`}>
      <h2 className={h2}>Rotation and personnel{tag}</h2>
      <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">{panel(pa, nameA, season)}{panel(pb, nameB, seasonB)}</div>
      <p className="mt-3 text-xs text-faint">Plain facts only. Personnel impact (player ratings, depth, star dependence) arrives with the play-by-play RAPM ratings. Returning minutes = share of this season&apos;s minutes played by players who were on the team last season. Height and class come from rosters (2024-25 on).</p>
    </div>
  );
}

function Consistency({ pa, pb, nameA, nameB, tag }: { pa: Profile; pb: Profile; nameA: string; nameB: string; tag: React.ReactNode }) {
  const row = (p: Profile, name: string) => {
    const [ul, ule, uln] = p.cons.upset_losses, [uw, uwe, uwn] = p.cons.upset_wins;
    return (
      <tr key={name}><td className="l">{name}</td><td>{fmtEff(p.cons.resid_sd)} <span className="text-xs text-muted">(more consistent than {fmtPct(p.cons.resid_sd_pc)} of D-I)</span></td>
        <td>{ul} <span className="text-xs text-muted">of {uln}, {fmtEff(ule)} expected</span></td><td>{uw} <span className="text-xs text-muted">of {uwn}, {fmtEff(uwe)} expected</span></td></tr>
    );
  };
  const more = (pa.cons.resid_sd ?? 0) > (pb.cons.resid_sd ?? 0) ? nameA : nameB;
  return (
    <div className={`${card} mb-6`}>
      <h2 className={h2}>Consistency and upset profile{tag}</h2>
      <table className="dense"><thead><tr><th className="l"></th><th>Spread of results vs expectation (points)</th><th>Losses as a 70%+ favorite</th><th>Wins as a 30% underdog or worse</th></tr></thead>
        <tbody>{row(pa, nameA)}{row(pb, nameB)}</tbody></table>
      <p className="mt-2 text-sm text-muted">Context only: {more}&apos;s results have swung more around expectation this season. That describes the past; it is not used to predict this game.</p>
    </div>
  );
}

function AnalogsBlock({ out, nameA, nameB, pa, pb, map, tag }: { out: Out; nameA: string; nameB: string; pa?: Profile; pb?: Profile; map: Map<string, Team>; tag: React.ReactNode }) {
  const { data: AN } = useJson<Analogs>("analogs.json");
  const [want, setWant] = useState(false);
  const { data: AG } = useJson<AnalogGames>(want ? "analog_games.json" : null);
  const fav = out.m >= 0 ? nameA : nameB, dog = out.m >= 0 ? nameB : nameA;
  const cell = useMemo(() => {
    if (!AN) return null;
    const near = (xs: number[], v: number) => xs.reduce((bi, x, i) => (Math.abs(x - v) < Math.abs(xs[bi] - v) ? i : bi), 0);
    return AN.cells[near(AN.grid_margin, Math.abs(out.m)) * AN.grid_poss.length + near(AN.grid_poss, out.poss)];
  }, [AN, out.m, out.poss]);
  const closest = useMemo(() => {
    if (!AG || !pa || !pb) return [];
    const g = (p: Profile, k: string) => p.ff[k]?.[0] ?? 0;
    const me = [g(pa, "efg") - g(pb, "efg_d"), g(pa, "tov") - g(pb, "tov_d"), g(pa, "orb") - g(pb, "orb_d"), g(pa, "ftr") - g(pb, "ftr_d"),
      g(pb, "efg") - g(pa, "efg_d"), g(pb, "tov") - g(pa, "tov_d"), g(pb, "orb") - g(pa, "orb_d"), g(pb, "ftr") - g(pa, "ftr_d")];
    return AG.rows.map((r) => ({ r, d: me.reduce((s, x, i) => s + (x - (r[6 + i] as number)) ** 2, 0) + ((Math.abs(r[4] as number) - Math.abs(out.m)) / 30) ** 2 }))
      .sort((x, y) => x.d - y.d).slice(0, 5).map((x) => x.r);
  }, [AG, pa, pb, out.m]);
  return (
    <div className={`${card} mb-6`}>
      <h2 className={h2}>Historical analogs{tag}</h2>
      {cell ? (
        <p className="text-[15px]">In <b>{fmtInt(cell[0])}</b> past games ({AN ? `${seasonLabel(AN.seasons[0])} to ${seasonLabel(AN.seasons[1])}` : ""}) with a predicted margin within {AN?.window.margin} points of {fmtEff(Math.abs(out.m))} and possessions within {AN?.window.poss} of {fmtEff(out.poss)}, the favorite won <b>{fmtPct(cell[1])}</b>; 80% of margins fell between <b>{fmtRating(cell[2], 0)}</b> and <b>{fmtRating(cell[4], 0)}</b> (favorite&apos;s side; here {fav} over {dog}).</p>
      ) : <p className="text-sm text-muted">Too few past games with a similar predicted margin and pace.</p>}
      <p className="mt-1 text-xs text-faint">A calibration view of how games like this one went, not a second prediction.</p>
      {pa && pb && (
        <div className="mt-4">
          {!want ? <button className="chip hover:text-ink" onClick={() => setWant(true)}>Show the five most similar past matchups by four factors (loads 6 MB)</button>
            : !AG ? <div className="skeleton h-24" /> : (
              <table className="dense"><thead><tr><th className="l">Game</th><th className="l">Season</th><th>Pred (home)</th><th>Result (home)</th></tr></thead>
                <tbody>{closest.map((r) => (
                  <tr key={String(r[0])}><td className="l"><GameLink id={String(r[0])} season={r[1] as number}>{map.get(String(r[3]))?.short ?? "?"} @ {map.get(String(r[2]))?.short ?? "?"}</GameLink></td>
                    <td className="l text-muted">{seasonLabel(r[1] as number)}</td><td>{fmtRating(r[4] as number)}</td>
                    <td><ScoreLink id={String(r[0])} season={r[1] as number}>{fmtRating(r[5] as number, 0)}</ScoreLink></td></tr>))}</tbody></table>
            )}
        </div>
      )}
    </div>
  );
}
