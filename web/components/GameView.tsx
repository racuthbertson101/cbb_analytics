"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Game, Team, useJson, useMeta, useTeams } from "@/lib/data";
import { fmtEff, fmtInt, fmtMA, fmtPct, fmtRate, fmtRating, fmtScore, seasonLabel } from "@/lib/format";
import { teamColor } from "@/lib/color";
import { cdf, latest, matchup, Pred, Preseason, RatingsFile, sigmaOf } from "@/lib/predict";
import { prettyDate } from "@/lib/util";
import TeamLogo from "./TeamLogo";
import ContextTag from "./ui/ContextTag";
import { ScoreLink } from "./ui/GameLink";
import MatchupBar from "./ui/MatchupBar";
import SeasonChip from "./ui/SeasonChip";

type Cell = string | number | null;
type TLog = { v: number; cols: string[]; rows: Cell[][] };
type PLog = { v: number; cols: string[]; names: Record<string, string>; logs: Record<string, Cell[][]> };
type Logged = { cols: string[]; games: Record<string, [string, string, number, number, number]> };
type WT = { weights: Record<string, number>; stakes_weights: Record<string, number> };
type TS = { rows: Record<string, Record<string, number>> };
type PlayersShard = { cols: string[]; rows: Cell[][] };
type Side = Record<string, number>;

const DEFAULT_PLOG_FIRST = 2017; // site_size.py may raise it (meta.limits)
const TYPE_LABEL: Record<string, string> = { regular: "Regular season", conf_tourney: "Conference tournament", ncaa: "NCAA Tournament", nit: "NIT", other_post: "Postseason", exhibition: "Exhibition" };
const obj = (cols: string[], row: Cell[]) => Object.fromEntries(cols.map((c, i) => [c, row[i]]));
const color = (t?: Team) => teamColor(t);
const card = "card p-5";
const h2 = "mb-3 text-sm font-medium uppercase tracking-wider text-muted";

/** True when the team was D-I in that season (only D-I teams have logs and pages). */
const isD1 = (map: Map<string, Team>, id: string, season: number) => !!map.get(id)?.conf[String(season)];

export default function GameView() {
  const sp = useSearchParams();
  const meta = useMeta();
  const { map } = useTeams();
  const id = sp.get("id") ?? "";
  const season = Number(sp.get("season")) || (meta ? meta.upcoming_season ?? meta.current_season : 0);
  const { data: G, error } = useJson<{ games: Game[] }>(season ? `games/${season}.json` : null);
  const g = useMemo(() => G?.games.find((x) => x.id === id), [G, id]);
  if (error) return <Empty>No games found for {seasonLabel(season)}.</Empty>;
  if (!G || !map.size) return <div className="skeleton h-96 w-full" />;
  if (!g) return <Empty>No game with id {id} in {seasonLabel(season)}. <Link className="text-accent underline" href="/">Back to today&apos;s games</Link></Empty>;
  return g.ok ? <Completed g={g} season={season} map={map} games={G.games} /> : <Upcoming g={g} season={season} map={map} games={G.games} />;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="card mx-auto mt-10 max-w-xl p-8 text-center text-muted">{children}</div>;
}

/* ---------------- header ---------------- */

function Header({ g, season, map, ot }: { g: Game; season: number; map: Map<string, Team>; ot?: number }) {
  const a = map.get(g.a), h = map.get(g.h);
  const tip = g.dt ? new Date(g.dt.replace("Z", ":00Z")) : null;
  // ESPN schedules unannounced tip times at midnight Eastern: show the date with "time TBA" instead of a fake 12:00 AM
  const etClock = tip?.toLocaleString("en-US", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "America/New_York" });
  const tipText = !tip ? null : etClock === "00:00" ? `${prettyDate(g.d)} · time TBA`
    : tip.toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York", timeZoneName: "short" });
  const side = (t: Team | undefined, id: string, name: string | null | undefined, rank: number | null, score: number | null, won: boolean, right: boolean) => (
    <div className={`flex items-center gap-4 ${right ? "flex-row-reverse text-right" : ""}`}>
      <TeamLogo team={t} size={64} />
      <div className="min-w-0">
        {t && isD1(map, id, season) ? (
          <Link href={`/team/${id}/?season=${season}`} className="display block truncate text-2xl font-semibold hover:text-accent">
            {rank != null && <span className="mr-1.5 text-sm text-faint">{rank}</span>}{t.name}
          </Link>
        ) : <span className="display block truncate text-2xl font-semibold text-muted">{name ?? t?.name ?? "Non-D-I opponent"}</span>}
        <span className="text-xs text-muted">{g.n ? "Neutral site" : right ? "Home" : "Away"}</span>
      </div>
      {score != null && <span className={`num ml-auto text-6xl font-semibold ${right ? "ml-0 mr-auto" : ""} ${won ? "" : "text-muted"}`}>{score}</span>}
    </div>
  );
  const done = g.ok && g.as != null && g.hs != null;
  return (
    <div className="card mb-6 overflow-hidden">
      <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${color(a)} 0 50%, ${color(h)} 50% 100%)` }} />
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-6 p-6">
        {side(a, g.a, g.an, g.ar, done ? g.as : null, done && (g.as as number) > (g.hs as number), false)}
        <div className="text-center">
          <div className="text-xs uppercase tracking-wider text-muted">{done ? `Final${ot ? (ot > 1 ? ` · ${ot}OT` : " · OT") : ""}` : "Upcoming"}</div>
          <div className="mt-1 text-sm text-muted">{g.n ? "vs" : "@"}</div>
        </div>
        {side(h, g.h, g.hn, g.hr, done ? g.hs : null, done && (g.hs as number) > (g.as as number), true)}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-6 py-3 text-xs text-muted">
        <span>{done || !tipText ? prettyDate(g.d) : tipText}</span>
        <SeasonChip season={season} />
        <span>{g.note || TYPE_LABEL[g.t] || g.t}{g.cg && g.t === "regular" ? " · Conference game" : ""}</span>
        {g.v && <span>{g.v}{g.n ? " (neutral)" : ""}</span>}
        {g.att ? <span>Attendance {fmtInt(g.att)}</span> : null}
        {g.tv && <span>TV: {g.tv}</span>}
      </div>
    </div>
  );
}

/* ---------------- completed game ---------------- */

function sideOf(log: TLog | null | undefined, gameId: string, own: boolean): Side | null {
  if (!log) return null;
  const r = log.rows.find((x) => x[0] === gameId);
  if (!r) return null;
  const o = obj(log.cols, r) as Record<string, number>;
  const keys = ["fgm", "fga", "tpm", "tpa", "ftm", "fta", "orb", "drb", "ast", "stl", "blk", "tov", "pf", "pip", "fbp", "top", "ll"];
  const s: Side = { pts: own ? o.pts : o.opp_pts, opp_drb: own ? o.o_drb : o.drb };
  keys.forEach((k) => (s[k] = own ? o[k] : o["o_" + k]));
  return s;
}

function derived(s: Side, ftaCoef: number) {
  const poss = s.fga - s.orb + s.tov + ftaCoef * s.fta;
  return { poss, ppp: s.pts / poss, efg: (s.fgm + 0.5 * s.tpm) / s.fga, tovr: s.tov / poss, orbr: s.orb / (s.orb + s.opp_drb), ftr: s.fta / s.fga };
}

function seasonAvg(log: TLog | null | undefined, ftaCoef: number) {
  if (!log || !log.rows.length) return null;
  const xs = log.rows.map((r) => { const o = obj(log.cols, r) as Record<string, number>; return { ...o, opp_drb: o.o_drb } as Record<string, number>; })
    .filter((o) => o.fga != null && o.opp_drb != null);
  if (!xs.length) return null;
  const sum = (k: string) => xs.reduce((t, o) => t + ((o as Record<string, number>)[k] ?? 0), 0);
  const tot: Side = { pts: sum("pts"), opp_drb: sum("opp_drb") };
  ["fgm", "fga", "tpm", "tpa", "ftm", "fta", "orb", "drb", "tov", "pip", "fbp", "top", "ll"].forEach((k) => (tot[k] = sum(k)));
  const d = derived(tot, ftaCoef), n = xs.length;
  return { ...d, poss: d.poss / n, pip: tot.pip / n, fbp: tot.fbp / n, top: tot.top / n, ll: tot.ll / n };
}

function Completed({ g, season, map, games }: { g: Game; season: number; map: Map<string, Team>; games: Game[] }) {
  const meta = useMeta();
  const PLOG_FIRST = meta?.limits?.playerlog_first ?? DEFAULT_PLOG_FIRST, TLOG_FIRST = meta?.limits?.teamlog_first ?? 2010;
  const aD1 = isD1(map, g.a, season) && season >= TLOG_FIRST, hD1 = isD1(map, g.h, season) && season >= TLOG_FIRST;
  const { data: TA } = useJson<TLog>(aD1 ? `teamlogs/${season}/${g.a}.json` : null);
  const { data: TH } = useJson<TLog>(hD1 ? `teamlogs/${season}/${g.h}.json` : null);
  const { data: PA } = useJson<PLog>(aD1 && season >= PLOG_FIRST ? `playerlogs/${season}/${g.a}.json` : null);
  const { data: PH } = useJson<PLog>(hD1 && season >= PLOG_FIRST ? `playerlogs/${season}/${g.h}.json` : null);
  const { data: PP } = useJson<Pred>("params/predict.json");
  const { data: POSS } = useJson<{ fta_coef: number }>("params/possessions.json");
  const { data: LIVE } = useJson<{ logged_seasons?: number[] }>("accuracy/live.json");
  const { data: LOG } = useJson<Logged>(LIVE?.logged_seasons?.includes(season) ? `accuracy/logged/${season}.json` : null);
  const ftaCoef = POSS?.fta_coef ?? 0.4856;

  const home = sideOf(TH, g.id, true) ?? sideOf(TA, g.id, false);
  const away = sideOf(TA, g.id, true) ?? sideOf(TH, g.id, false);
  const lines = (P: PLog | null | undefined): Line[] | null => P ? Object.entries(P.logs).flatMap(([pid, rows]) => rows.filter((r) => r[0] === g.id).map((r) => ({ ...obj(P.cols, r), pid, name: P.names[pid] }) as unknown as Line)) : null;
  const la = useMemo(() => lines(PA), [PA]); // eslint-disable-line react-hooks/exhaustive-deps
  const lh = useMemo(() => lines(PH), [PH]); // eslint-disable-line react-hooks/exhaustive-deps
  const teamMin = (l: { min: number }[] | null) => (l && l.length ? l.reduce((t, x) => t + x.min, 0) : null);
  const tm = teamMin(lh) ?? teamMin(la);
  const ot = tm != null && tm >= 215 ? Math.round((tm - 200) / 25) : 0; // regulation = 5 x 40 = 200 player-minutes; each OT adds 25

  return (
    <div>
      <Header g={g} season={season} map={map} ot={ot} />
      {PP && g.pm != null && <PredictionStrip g={g} PP={PP} map={map} logged={LOG?.games[g.id]} hasLog={!!LIVE?.logged_seasons?.length} />}
      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        {[{ t: g.a, l: la, s: away, d1: aD1, name: g.an }, { t: g.h, l: lh, s: home, d1: hD1, name: g.hn }].map((x) => (
          <BoxScore key={x.t} team={map.get(x.t)} fallbackName={x.name} lines={x.l} totals={x.s} season={season} d1={x.d1} plogFirst={PLOG_FIRST} />
        ))}
      </div>
      {home && away && (
        <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[3fr_2fr]">
          <TeamStats a={map.get(g.a)} h={map.get(g.h)} an={g.an} hn={g.hn} away={away} home={home} avgA={seasonAvg(TA, ftaCoef)} avgH={seasonAvg(TH, ftaCoef)} ftaCoef={ftaCoef} />
          <ExpectedVsActual plogFirst={PLOG_FIRST} rows={[...(la ?? []).map((r) => ({ ...r, tid: g.a })), ...(lh ?? []).map((r) => ({ ...r, tid: g.h }))]} map={map} />
        </div>
      )}
      <MoreGames g={g} season={season} games={games} map={map} />
    </div>
  );
}

function PredictionStrip({ g, PP, map, logged, hasLog }: { g: Game; PP: Pred; map: Map<string, Team>; logged?: [string, string, number, number, number]; hasLog: boolean }) {
  const pm = g.pm as number, p = g.p as number, act = (g.hs as number) - (g.as as number);
  const favHome = pm >= 0;
  const nm = (id: string, n?: string | null) => map.get(id)?.short ?? n ?? "Non-D-I";
  const fav = favHome ? nm(g.h, g.hn) : nm(g.a, g.an), win = act > 0 ? nm(g.h, g.hn) : nm(g.a, g.an);
  const sd = sigmaOf(PP, g.pp ?? 68);
  const diff = (favHome ? 1 : -1) * (act - pm); // result vs expectation, from the favorite's side
  const pctile = cdf((favHome ? act - pm : pm - act) / sd);
  return (
    <div className={`${card} mb-6 grid grid-cols-1 items-center gap-6 lg:grid-cols-[1fr_360px]`}>
      <div>
        <h2 className={h2}>Prediction vs result</h2>
        <p className="text-[15px] leading-relaxed">
          Pregame: <b>{fav} by {fmtEff(Math.abs(pm))}</b> ({fmtPct(favHome ? p : 1 - p)}) · Final: <b>{win} by {Math.abs(act)}</b> ·
          Result vs expectation <b className={diff >= 0 ? "text-accent2" : "text-[var(--bad)]"}>{fmtRating(diff)}</b> for {fav}
          <span className="text-muted"> ({ordinal(Math.round(pctile * 100))} percentile of the model&apos;s outcome distribution)</span>
        </p>
        <p className="mt-2 text-xs text-muted">80% of results land in {fav} {fmtRating(Math.abs(pm) + PP.q10)} to {fmtRating(Math.abs(pm) + PP.q90)}. This is an outcome interval (game-to-game randomness), not uncertainty in the ratings.</p>
        <p className="mt-2 text-xs">
          {logged ? (
            <span className="chip" title={`Hash-chained row ${logged[1]}…; made ${logged[4]} day(s) before the game`}>Logged {new Date(logged[0]).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York", timeZoneName: "short" })} · hash {logged[1]}</span>
          ) : (
            <span className="text-faint">{hasLog ? "Not in the live prediction log." : "Walk-forward backtest prediction (ratings from earlier games only); the live log starts in 2026-27."}</span>
          )}
        </p>
      </div>
      <MarginCurve pm={pm} sd={sd} act={act} lo={pm + PP.q10} hi={pm + PP.q90} home={map.get(g.h)?.short ?? g.hn ?? "Home"} />
    </div>
  );
}

const ordinal = (n: number) => `${n}${["th", "st", "nd", "rd"][(n % 100 >= 11 && n % 100 <= 13) || n % 10 > 3 ? 0 : n % 10]}`;

/** The model's distribution of home margins (normal with the tempo-dependent sigma), 80% band shaded, result marked. */
function MarginCurve({ pm, sd, act, lo, hi, home }: { pm: number; sd: number; act: number; lo: number; hi: number; home: string }) {
  const W = 360, H = 110, x0 = Math.min(pm - 3 * sd, act - 4), x1 = Math.max(pm + 3 * sd, act + 4);
  const X = (m: number) => ((m - x0) / (x1 - x0)) * W;
  const pdf = (m: number) => Math.exp(-0.5 * ((m - pm) / sd) ** 2);
  const pts = Array.from({ length: 81 }, (_, i) => x0 + ((x1 - x0) * i) / 80);
  const Y = (v: number) => H - 22 - v * (H - 34);
  const path = pts.map((m, i) => `${i ? "L" : "M"}${X(m).toFixed(1)},${Y(pdf(m)).toFixed(1)}`).join("");
  const band = pts.filter((m) => m >= lo && m <= hi);
  const bandPath = band.length ? `M${X(band[0])},${Y(0)}` + band.map((m) => `L${X(m).toFixed(1)},${Y(pdf(m)).toFixed(1)}`).join("") + `L${X(band[band.length - 1])},${Y(0)}Z` : "";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Model margin distribution for ${home}, result ${act}`}>
      <path d={bandPath} fill="var(--accent-2)" opacity={0.18} />
      <path d={path} fill="none" stroke="var(--accent-2)" strokeWidth={1.5} />
      <line x1={X(0)} x2={X(0)} y1={8} y2={Y(0)} stroke="var(--border)" strokeDasharray="3 3" />
      <line x1={X(act)} x2={X(act)} y1={4} y2={Y(0)} stroke="var(--accent)" strokeWidth={2} />
      <text x={X(act)} y={12} textAnchor={X(act) > W - 60 ? "end" : "start"} dx={X(act) > W - 60 ? -4 : 4} fontSize={10} fill="var(--accent)">final {fmtRating(act, 0)}</text>
      <line x1={0} x2={W} y1={Y(0)} y2={Y(0)} stroke="var(--border)" />
      <text x={0} y={H - 6} fontSize={10} fill="var(--muted)">{home} margin →</text>
      <text x={X(pm)} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--muted)">pred {fmtRating(pm)}</text>
    </svg>
  );
}

type Line = { pid: string; name: string; tid?: string; st: number; min: number; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number; pf: number;
  fgm: number; fga: number; tpm: number; tpa: number; ftm: number; fta: number; orb: number; drb: number; xpts: number; xreb: number };
const val = (r: Line, k: string) => (r as unknown as Record<string, number>)[k] ?? 0;
const BOX_COLS: [string, string, (r: Line) => string | number][] = [
  ["MIN", "min", (r) => r.min], ["PTS", "pts", (r) => r.pts], ["FG", "fga", (r) => fmtMA(r.fgm, r.fga)], ["3P", "tpa", (r) => fmtMA(r.tpm, r.tpa)],
  ["FT", "fta", (r) => fmtMA(r.ftm, r.fta)], ["ORB", "orb", (r) => r.orb], ["DRB", "drb", (r) => r.drb], ["REB", "reb", (r) => r.reb],
  ["AST", "ast", (r) => r.ast], ["STL", "stl", (r) => r.stl], ["BLK", "blk", (r) => r.blk], ["TO", "tov", (r) => r.tov], ["PF", "pf", (r) => r.pf],
];

function BoxScore({ team, fallbackName, lines, totals, season, d1, plogFirst }: { team?: Team; fallbackName?: string | null; lines: Line[] | null; totals: Side | null; season: number; d1: boolean; plogFirst: number }) {
  const [sort, setSort] = useState<string | null>(null);
  const rows = useMemo(() => {
    if (!lines) return [];
    const xs = [...lines];
    return sort ? xs.sort((a, b) => val(b, sort) - val(a, sort)) : xs.sort((a, b) => b.st - a.st || b.min - a.min);
  }, [lines, sort]);
  const name = team?.name ?? fallbackName ?? "Non-D-I opponent";
  return (
    <div className="card overflow-hidden">
      <h2 className={`${h2} flex items-center gap-2 px-4 pt-4`}><TeamLogo team={team} size={20} />{name}</h2>
      {!d1 ? <p className="px-4 pb-4 text-sm text-muted">Box scores are kept for Division I teams only.</p>
        : season < plogFirst ? <p className="px-4 pb-4 text-sm text-muted">Player box scores are kept from {seasonLabel(plogFirst)} on; team totals are below.</p>
        : !lines ? <div className="skeleton m-4 h-40" />
        : (
          <div className="overflow-x-auto p-2">
            <table className="dense">
              <thead><tr><th className="l" onClick={() => setSort(null)} title="Starters first">Player</th>{BOX_COLS.map(([l, k]) => <th key={l} onClick={() => setSort(k)} aria-sort={sort === k ? "descending" : "none"}>{l}</th>)}</tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.pid} className={!sort && i > 0 && rows[i - 1].st === 1 && r.st === 0 ? "border-t-2 border-line" : ""}>
                    <td className="l"><Link className="hover:text-accent" href={`/player/?id=${r.pid}&season=${season}`}>{r.name}</Link>{r.st ? <span className="ml-1.5 text-[10px] text-faint">S</span> : null}</td>
                    {BOX_COLS.map(([l, , f]) => <td key={l} className={l === "PTS" ? "font-medium" : ""}>{f(r)}</td>)}
                  </tr>
                ))}
                {totals && (
                  <tr className="font-medium">
                    <td className="l text-muted">Team</td><td></td><td>{totals.pts}</td><td>{fmtMA(totals.fgm, totals.fga)}</td><td>{fmtMA(totals.tpm, totals.tpa)}</td>
                    <td>{fmtMA(totals.ftm, totals.fta)}</td><td>{totals.orb}</td><td>{totals.drb}</td><td>{totals.orb + totals.drb}</td><td>{totals.ast}</td>
                    <td>{totals.stl}</td><td>{totals.blk}</td><td>{totals.tov}</td><td>{totals.pf}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

function TeamStats({ a, h, an, hn, away, home, avgA, avgH, ftaCoef }: { a?: Team; h?: Team; an?: string | null; hn?: string | null; away: Side; home: Side; avgA: ReturnType<typeof seasonAvg>; avgH: ReturnType<typeof seasonAvg>; ftaCoef: number }) {
  const da = derived(away, ftaCoef), dh = derived(home, ftaCoef);
  const pct = (x: number | null) => fmtRate(x == null ? null : x * 100);
  const rows: [string, number | null, number | null, (x: number | null) => string, "high" | "low" | "none", number | null | undefined, number | null | undefined][] = [
    ["Possessions", da.poss, dh.poss, (x) => fmtEff(x), "none", avgA?.poss, avgH?.poss],
    ["Points per possession", da.ppp, dh.ppp, (x) => fmtEff(x, 2), "high", avgA?.ppp, avgH?.ppp],
    ["eFG%", da.efg, dh.efg, pct, "high", avgA?.efg, avgH?.efg],
    ["Turnover %", da.tovr, dh.tovr, pct, "low", avgA?.tovr, avgH?.tovr],
    ["Off. rebound %", da.orbr, dh.orbr, pct, "high", avgA?.orbr, avgH?.orbr],
    ["FT rate", da.ftr, dh.ftr, pct, "high", avgA?.ftr, avgH?.ftr],
    ["Paint points", away.pip, home.pip, (x) => fmtInt(x), "high", avgA?.pip, avgH?.pip],
    ["Fast-break points", away.fbp, home.fbp, (x) => fmtInt(x), "high", avgA?.fbp, avgH?.fbp],
    ["Points off turnovers", away.top, home.top, (x) => fmtInt(x), "high", avgA?.top, avgH?.top],
    ["Largest lead", away.ll, home.ll, (x) => fmtInt(x), "high", avgA?.ll, avgH?.ll],
  ];
  return (
    <div className={card}>
      <h2 className={h2}>Team stats</h2>
      <div className="mb-2 grid grid-cols-[4.5rem_1fr_9rem_1fr_4.5rem] gap-2 text-xs text-muted"><span className="col-span-2 text-right">{a?.short ?? an ?? "Away"}</span><span /><span className="col-span-2">{h?.short ?? hn ?? "Home"}</span></div>
      {rows.map(([l, x, y, f, b, ta, th]) => <MatchupBar key={l} label={l} a={x} b={y} fmt={f} better={b} ca={color(a)} cb={color(h)} tickA={ta ?? null} tickB={th ?? null} />)}
      <p className="mt-3 text-xs text-faint">Ticks mark each team&apos;s season average. Possessions = FGA − ORB + TO + {fmtEff(ftaCoef, 3)} × FTA.</p>
    </div>
  );
}

function ExpectedVsActual({ rows, map, plogFirst }: { rows: Line[]; map: Map<string, Team>; plogFirst: number }) {
  const xs = rows.filter((r) => r.min >= 10 && r.xpts != null).sort((a, b) => (b.pts - b.xpts) - (a.pts - a.xpts));
  const max = Math.max(10, ...xs.flatMap((r) => [r.pts, r.xpts]));
  const tip = "Expected = the player's season-to-date points (or rebounds) per minute from games BEFORE this one, times the minutes he played in it. Players with fewer than 30 earlier minutes have no expectation.";
  return (
    <div className={card}>
      <h2 className={h2} title={tip}>Expected vs actual points <span className="cursor-help normal-case">ⓘ</span></h2>
      {!xs.length ? <p className="text-sm text-muted">No pre-game expectations: a player needs at least 30 minutes in earlier games this season (player logs start in {seasonLabel(plogFirst)}).</p> : (
        <div className="space-y-1">
          {xs.map((r) => {
            const good = r.pts >= r.xpts;
            return (
              <div key={r.pid + r.tid} className="grid grid-cols-[10rem_1fr_6.5rem] items-center gap-3 text-[13px]" title={`${r.name}: ${r.pts} pts (expected ${fmtEff(r.xpts)}), ${r.reb} reb (expected ${fmtEff(r.xreb)}) in ${r.min} min`}>
                <span className="flex items-center gap-1.5 truncate"><TeamLogo team={map.get(r.tid ?? "")} size={14} />{r.name}</span>
                <svg viewBox="0 0 100 10" preserveAspectRatio="none" className="h-3 w-full">
                  <line x1={(r.xpts / max) * 100} x2={(r.pts / max) * 100} y1={5} y2={5} stroke={good ? "var(--good)" : "var(--bad)"} strokeWidth={2} vectorEffect="non-scaling-stroke" />
                  <circle cx={(r.xpts / max) * 100} cy={5} r={2.2} fill="none" stroke="var(--muted)" vectorEffect="non-scaling-stroke" />
                  <circle cx={(r.pts / max) * 100} cy={5} r={2.2} fill={good ? "var(--good)" : "var(--bad)"} />
                </svg>
                <span className="num text-right text-xs"><b>{r.pts}</b> <span className="text-muted">vs {fmtEff(r.xpts)}</span></span>
              </div>
            );
          })}
          <p className="pt-2 text-xs text-faint">Hollow dot = expected, filled dot = actual. Players with 10+ minutes.</p>
        </div>
      )}
    </div>
  );
}

/* ---------------- upcoming game ---------------- */

function Upcoming({ g, season, map, games }: { g: Game; season: number; map: Map<string, Team>; games: Game[] }) {
  const meta = useMeta();
  const pre = !!meta && meta.upcoming_season === season;
  const { data: R } = useJson<RatingsFile>(meta && !pre ? `ratings/${season}.json` : null);
  const { data: PRE } = useJson<Preseason>(pre ? `ratings/${season}_preseason.json` : null);
  const { data: PP } = useJson<Pred>("params/predict.json");
  const { data: WTS } = useJson<WT>("params/watchability.json");
  const S = latest(R, PRE);
  const m = S ? matchup(S, g.h, g.a, g.n ? 0 : 1) : null;
  const h = map.get(g.h), a = map.get(g.a);
  const nm = (id: string, n?: string | null) => map.get(id)?.short ?? n ?? "Non-D-I";
  return (
    <div>
      <Header g={g} season={season} map={map} />
      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[3fr_2fr]">
        <div className={card}>
          <h2 className={h2}>Prediction</h2>
          {g.p == null || g.pm == null || !PP ? <p className="text-sm text-muted">No prediction: one of the teams is not in Division I.</p> : (
            <>
              <div className="grid grid-cols-3 items-center text-center">
                <div><div className="num text-5xl font-semibold">{fmtScore(g.pa)}</div><div className="text-sm text-muted">{nm(g.a, g.an)}</div><div className="num mt-1 text-accent2">{fmtPct(1 - g.p)}</div></div>
                <div className="text-xs text-muted">predicted score<br />{fmtEff(g.pp)} possessions</div>
                <div><div className="num text-5xl font-semibold">{fmtScore(g.ph)}</div><div className="text-sm text-muted">{nm(g.h, g.hn)}</div><div className="num mt-1 text-accent2">{fmtPct(g.p)}</div></div>
              </div>
              <div className="relative mt-4 h-3 overflow-hidden rounded-full bg-surface2">
                <div className="absolute inset-y-0 left-0" style={{ width: `${(1 - g.p) * 100}%`, background: color(a) }} />
                <div className="absolute inset-y-0 right-0" style={{ width: `${g.p * 100}%`, background: color(h) }} />
              </div>
              <p className="mt-3 text-sm">{g.pm >= 0 ? nm(g.h, g.hn) : nm(g.a, g.an)} by {fmtEff(Math.abs(g.pm))} · 80% of results land in {nm(g.h, g.hn)} {fmtRating(g.pm + PP.q10, 0)} to {fmtRating(g.pm + PP.q90, 0)}</p>
              {m && <Waterfall parts={m.parts} home={nm(g.h, g.hn)} total={m.margin} />}
              <Link className="mt-4 inline-block text-sm text-accent hover:underline" href={`/compare/?a=${g.h}&b=${g.a}&site=${g.n ? 0 : 1}&season=${season}`}>Full comparison →</Link>
            </>
          )}
        </div>
        {g.w != null && g.wc && WTS && <WatchBreakdown w={g.w} wc={g.wc} wts={WTS} />}
      </div>
      <KeyBattles g={g} season={season} map={map} />
      <Rotations g={g} season={season} map={map} />
      <MoreGames g={g} season={season} games={games} map={map} />
    </div>
  );
}

function Waterfall({ parts, home, total }: { parts: { offense: number; defense: number; home: number }; home: string; total: number }) {
  const items: [string, number][] = [["Offense edge", parts.offense], ["Defense edge", parts.defense], ["Home court", parts.home]];
  const cum = items.reduce<number[]>((acc, [, v]) => [...acc, (acc[acc.length - 1] ?? 0) + v], []);
  const max = Math.max(Math.abs(total), ...items.map(([, v]) => Math.abs(v)), ...cum.map(Math.abs), 1); // running totals stay inside the track
  let run = 0;
  return (
    <div className="mt-5">
      <div className="mb-1 text-xs text-muted">Where the predicted margin comes from ({home}&apos;s side, latest ratings)</div>
      {[...items, ["Predicted margin", total] as [string, number]].map(([l, v], i) => {
        const start = i < 3 ? run : 0, end = i < 3 ? run + v : v;
        if (i < 3) run += v;
        const lo = Math.min(start, end), hi = Math.max(start, end);
        return (
          <div key={l} className="grid grid-cols-[9rem_1fr_4rem] items-center gap-2 py-0.5 text-[13px]">
            <span className={i === 3 ? "font-medium" : "text-muted"}>{l}</span>
            <div className="relative h-3">
              <div className="absolute inset-y-0 w-px bg-line" style={{ left: "50%" }} />
              <div className="absolute inset-y-0 rounded-sm" style={{ left: `${50 + (lo / max) * 48}%`, width: `${Math.max(((hi - lo) / max) * 48, 0.4)}%`, background: v >= 0 ? "var(--accent-2)" : "var(--bad)", opacity: i === 3 ? 1 : 0.7 }} />
            </div>
            <span className="num text-right">{fmtRating(v)}</span>
          </div>
        );
      })}
    </div>
  );
}

const WLABELS: [string, string][] = [["quality", "Quality"], ["competitiveness", "Closeness"], ["tempo", "Tempo"], ["star_power", "Star power"], ["stakes", "Stakes"]];

function WatchBreakdown({ w, wc, wts }: { w: number; wc: (number | null)[]; wts: WT }) {
  return (
    <div className={card}>
      <h2 className={h2}>Watchability {fmtEff(w)} / 10</h2>
      {WLABELS.map(([k, l], i) => (
        <div key={k} className="grid grid-cols-[7rem_1fr_3rem_4rem] items-center gap-2 py-1 text-[13px]">
          <span>{l}{k === "star_power" && <ContextTag kind="experimental" title="Uses the experimental box-score impact rating, which overrates big men." />}</span>
          <span className="relative h-1.5 rounded-full bg-surface2"><span className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${wc[i] ?? 0}%` }} /></span>
          <span className="num text-right">{wc[i] ?? "–"}</span>
          <span className="text-right text-xs text-muted">× {fmtEff(wts.weights[k], 2)}</span>
        </div>
      ))}
      <p className="mt-3 text-xs text-faint">Each component is a percentile among historical D-I games; the weights are a <Link className="underline" href="/methodology/">judgment call</Link>, not fitted. Stakes = rank proximity {fmtEff(wts.stakes_weights.rank_proximity, 2)}, title leverage {fmtEff(wts.stakes_weights.title_leverage, 2)}, bubble proximity {fmtEff(wts.stakes_weights.bubble_proximity, 2)}.</p>
    </div>
  );
}

const FACTORS: { k: string; label: string; offHigh: boolean }[] = [
  { k: "efg", label: "effective FG%", offHigh: true }, { k: "tov", label: "turnover rate", offHigh: false },
  { k: "orb", label: "offensive rebounding", offHigh: true }, { k: "ftr", label: "free-throw rate", offHigh: true },
];

function KeyBattles({ g, season, map }: { g: Game; season: number; map: Map<string, Team> }) {
  const meta = useMeta();
  const statSeason = meta && meta.upcoming_season === season ? season - 1 : season;
  const { data: T } = useJson<TS>(meta ? `teamstats/${statSeason}.json` : null); // wait for meta: preseason games use last season
  const battles = useMemo(() => {
    if (!T) return [];
    const all = Object.values(T.rows);
    const pctOf = (k: string, v: number, highGood: boolean) => { const xs = all.map((r) => r[k]).filter((x) => x != null); const below = xs.filter((x) => (highGood ? x < v : x > v)).length; return below / xs.length; };
    const out: { off: string; def: string; f: (typeof FACTORS)[0]; po: number; pd: number; vo: number; vd: number }[] = [];
    for (const [o, d] of [[g.h, g.a], [g.a, g.h]]) {
      const ro = T.rows[o], rd = T.rows[d];
      if (!ro || !rd) continue;
      for (const f of FACTORS) {
        const vo = ro[f.k], vd = rd[f.k + "_d"];
        out.push({ off: o, def: d, f, vo, vd, po: pctOf(f.k, vo, f.offHigh), pd: pctOf(f.k + "_d", vd, !f.offHigh) });
      }
    }
    return out.sort((x, y) => Math.abs(y.po - y.pd) - Math.abs(x.po - x.pd)).slice(0, 2);
  }, [T, g]);
  if (!battles.length) return null;
  return (
    <div className={`${card} mb-6`}>
      <h2 className={h2}>Key battles {statSeason !== season && <span className="normal-case text-faint">(last season&apos;s team stats)</span>}<ContextTag kind="context" /></h2>
      <ul className="space-y-2 text-[14px]">
        {battles.map((b) => (
          <li key={b.off + b.f.k}>
            <b>{map.get(b.off)?.short}</b>&apos;s {b.f.label} ({fmtRate(b.vo * 100)}, better than {fmtPct(b.po)} of D-I) against <b>{map.get(b.def)?.short}</b>&apos;s defense ({fmtRate(b.vd * 100)} allowed, better than {fmtPct(b.pd)}).
            <span className="text-muted"> {b.po > b.pd ? `Edge ${map.get(b.off)?.short}.` : `Edge ${map.get(b.def)?.short}.`}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Rotations({ g, season, map }: { g: Game; season: number; map: Map<string, Team> }) {
  const meta = useMeta();
  const pre = !!meta && meta.upcoming_season === season;
  const { data: P } = useJson<PlayersShard>(meta && !pre ? `players/${season}.json` : null);
  if (pre) return <div className={`${card} mb-6 text-sm text-muted`}>Rotations appear once this season&apos;s games have been played.</div>;
  if (!P) return null;
  const c = (k: string) => P.cols.indexOf(k);
  const top = (tid: string) => P.rows.filter((r) => r[c("tid")] === tid).sort((x, y) => (y[c("min")] as number) - (x[c("min")] as number)).slice(0, 8);
  return (
    <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
      {[g.a, g.h].filter((t) => isD1(map, t, season)).map((tid) => (
        <div key={tid} className="card overflow-hidden">
          <h2 className={`${h2} flex items-center gap-2 px-4 pt-4`}><TeamLogo team={map.get(tid)} size={18} />{map.get(tid)?.short} rotation</h2>
          <div className="p-2"><table className="dense"><thead><tr><th className="l">Player</th><th className="l">Pos</th><th className="l">Ht</th><th className="l">Class</th><th>MPG</th><th>PPG</th><th>RPG</th><th>APG</th></tr></thead>
            <tbody>{top(tid).map((r) => (
              <tr key={String(r[c("id")])}><td className="l"><Link className="hover:text-accent" href={`/player/?id=${r[c("id")]}&season=${season}`}>{r[c("name")]}</Link></td>
                <td className="l text-muted">{r[c("pos")] ?? ""}</td><td className="l text-muted">{r[c("ht")] ?? ""}</td><td className="l text-muted">{r[c("cls")] ?? ""}</td>
                <td>{fmtEff(r[c("mpg")] as number)}</td><td>{fmtEff(r[c("ppg")] as number)}</td><td>{fmtEff(r[c("rpg")] as number)}</td><td>{fmtEff(r[c("apg")] as number)}</td></tr>))}</tbody></table></div>
        </div>
      ))}
    </div>
  );
}

/* ---------------- shared: rest, head-to-head, common opponents ---------------- */

function MoreGames({ g, season, games, map }: { g: Game; season: number; games: Game[]; map: Map<string, Team> }) {
  const meta = useMeta();
  const prevSeason = meta?.seasons.includes(season - 1) ? season - 1 : null;
  const { data: GP } = useJson<{ games: Game[] }>(prevSeason ? `games/${prevSeason}.json` : null);
  const nm = (id: string, fallback?: string | null) => map.get(id)?.short ?? fallback ?? "Non-D-I";
  const before = (x: Game) => x.d < g.d; // strictly earlier dates: rest days and common opponents use only games before this one
  const pair = (x: Game) => (x.h === g.h && x.a === g.a) || (x.h === g.a && x.a === g.h);
  const h2h = [...(GP?.games ?? []).map((x) => ({ x, s: season - 1 })), ...games.map((x) => ({ x, s: season }))].filter(({ x }) => x.ok && x.id !== g.id && pair(x));
  const rest = (tid: string) => {
    const prev = games.filter((x) => x.ok && before(x) && (x.h === tid || x.a === tid)).map((x) => x.d).sort().pop();
    return prev ? Math.round((Date.parse(g.d) - Date.parse(prev)) / 864e5) : null;
  };
  const opps = (tid: string) => {
    const m = new Map<string, Game[]>();
    games.filter((x) => x.ok && before(x) && (x.h === tid || x.a === tid)).forEach((x) => { const o = x.h === tid ? x.a : x.h; m.set(o, [...(m.get(o) ?? []), x]); });
    return m;
  };
  const oa = opps(g.a), oh = opps(g.h);
  const common = [...oa.keys()].filter((k) => oh.has(k) && k !== g.a && k !== g.h).slice(0, 8);
  const res = (tid: string, x: Game) => {
    const mine = x.h === tid ? (x.hs as number) : (x.as as number), theirs = x.h === tid ? (x.as as number) : (x.hs as number);
    return <ScoreLink key={x.id} id={x.id} season={season} className={mine > theirs ? "text-accent2" : "text-[var(--bad)]"}>{mine > theirs ? "W" : "L"} {mine}-{theirs}</ScoreLink>;
  };
  const ra = rest(g.a), rh = rest(g.h);
  if (!h2h.length && !common.length && ra == null && rh == null) return null;
  return (
    <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
      <div className={card}>
        <h2 className={h2}>Rest and head-to-head<ContextTag kind="context" /></h2>
        {(ra != null || rh != null) && <p className="mb-3 text-sm">Days since last game: {nm(g.a, g.an)} {ra ?? "–"} · {nm(g.h, g.hn)} {rh ?? "–"}</p>}
        {h2h.length ? (
          <ul className="space-y-1 text-sm">{h2h.map(({ x, s }) => (
            <li key={x.id} className="flex justify-between gap-2"><span className="text-muted">{prettyDate(x.d)}</span>
              <ScoreLink id={x.id} season={s}>{nm(x.a, x.an)} {x.as} @ {nm(x.h, x.hn)} {x.hs}</ScoreLink></li>))}</ul>
        ) : <p className="text-sm text-muted">No meetings this season or last.</p>}
      </div>
      <div className={`${card} xl:col-span-2`}>
        <h2 className={h2}>Common opponents this season<ContextTag kind="context" /></h2>
        {common.length ? (
          <table className="dense"><thead><tr><th className="l">Opponent</th><th className="l">{nm(g.a)}</th><th className="l">{nm(g.h)}</th></tr></thead>
            <tbody>{common.map((o) => (
              <tr key={o}><td className="l"><span className="inline-flex items-center gap-2"><TeamLogo team={map.get(o)} size={16} />{nm(o)}</span></td>
                <td className="l"><span className="inline-flex gap-3">{(oa.get(o) ?? []).map((x) => res(g.a, x))}</span></td>
                <td className="l"><span className="inline-flex gap-3">{(oh.get(o) ?? []).map((x) => res(g.h, x))}</span></td></tr>))}</tbody></table>
        ) : <p className="text-sm text-muted">No common opponents before this game.</p>}
      </div>
    </div>
  );
}
