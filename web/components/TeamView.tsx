"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Game, Ratings, loadJson, useJson, useMeta, useTeams } from "@/lib/data";
import { fmt, heat, pct, percentiles, prettyDate, seasonLabel, signed } from "@/lib/util";
import { shortConf } from "./RankingsView";
import { usePlayers } from "@/lib/players";
import TeamLogo from "./TeamLogo";

type Stats = { rows: Record<string, Record<string, number>> };
type RankRows = { rows: { id: string; conf: string; w: number; l: number; cw: number; cl: number; off: number; def: number; margin: number }[] };
type Pre = { teams: string[]; off: (number | null)[]; def: (number | null)[]; tempo: (number | null)[] };

function Stat({ label, value, sub, pctl }: { label: string; value: string; sub: string; pctl: number | null }) {
  return (
    <div className="card p-4" style={{ boxShadow: `inset 0 -3px 0 ${heat(pctl)}` }}>
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className="num mt-1 text-3xl font-semibold">{value}</div>
      <div className="text-xs text-muted">{sub}</div>
    </div>
  );
}

export default function TeamView({ id }: { id: string }) {
  const meta = useMeta();
  const { map } = useTeams();
  const sp = useSearchParams();
  const router = useRouter();
  const team = map.get(id);
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const upcoming = !!meta && season === meta.upcoming_season;
  const { data: R } = useJson<Ratings>(season && !upcoming ? `ratings/${season}.json` : null);
  const { data: PRE } = useJson<Pre>(upcoming ? "ratings/2027_preseason.json" : null);
  const { data: G } = useJson<{ games: Game[] }>(season ? `games/${season}.json` : null);
  const { data: S } = useJson<Stats>(season && !upcoming ? `teamstats/${season}.json` : null);
  const { data: RK } = useJson<RankRows>(season && !upcoming ? `rankings/${season}.json` : null);

  const snap = useMemo(() => {
    let teams: string[], off: (number | null)[], def: (number | null)[], tempo: (number | null)[];
    if (R) { const i = R.dates.length - 1; teams = R.teams; off = R.off[i]; def = R.def[i]; tempo = R.tempo[i]; }
    else if (PRE) { teams = PRE.teams; off = PRE.off; def = PRE.def; tempo = PRE.tempo; }
    else return null;
    const m = off.map((o, j) => (o != null && def[j] != null ? o - (def[j] as number) : null));
    const pm = percentiles(m), po = percentiles(off), pd = percentiles(def, false), pt = percentiles(tempo);
    const rank = (arr: (number | null)[], higher = true) => {
      const j = teams.indexOf(id);
      if (j < 0 || arr[j] == null) return null;
      return arr.filter((v) => v != null && (higher ? (v as number) > (arr[j] as number) : (v as number) < (arr[j] as number))).length + 1;
    };
    const j = teams.indexOf(id);
    if (j < 0) return null;
    return { off: off[j], def: def[j], tempo: tempo[j], margin: m[j], rM: rank(m), rO: rank(off), rD: rank(def, false), rT: rank(tempo), pm: pm[j], po: po[j], pd: pd[j], pt: pt[j], n: teams.length };
  }, [R, PRE, id]);

  const trend = useMemo(() => {
    if (!R) return [];
    const j = R.teams.indexOf(id);
    if (j < 0) return [];
    return R.dates.map((d, i) => ({ d, margin: R.off[i][j] != null ? (R.off[i][j] as number) - (R.def[i][j] as number) : null, off: R.off[i][j], def: R.def[i][j] }));
  }, [R, id]);

  const games = useMemo(() => (G?.games ?? []).filter((g) => (g.a === id || g.h === id) && g.t !== "exhibition"), [G, id]);
  const rec = useMemo(() => {
    let w = 0, l = 0, cw = 0, cl = 0;
    games.forEach((g) => { if (!g.ok) return; const won = (g.h === id) === ((g.hs as number) > (g.as as number)); won ? w++ : l++; if (g.cg && g.t === "regular") won ? cw++ : cl++; });
    return { w, l, cw, cl };
  }, [games, id]);
  const confName = team?.conf[String(season)] ?? team?.conf[String(season - 1)];
  const confRows = useMemo(() => (RK?.rows ?? []).filter((r) => r.conf === confName).sort((a, b) => b.cw / Math.max(1, b.cw + b.cl) - a.cw / Math.max(1, a.cw + a.cl) || b.margin - a.margin), [RK, confName]);
  const past = useMemo(() => games.filter((g) => g.ok), [games]);
  const rest = useMemo(() => games.filter((g) => !g.ok), [games]);

  const [hist, setHist] = useState<{ s: number; w: number; l: number; cw: number; cl: number; margin: number; rank: number; conf: string }[]>([]);
  useEffect(() => {
    if (!meta) return;
    Promise.all(meta.seasons.map((s) => loadJson<RankRows>(`rankings/${s}.json`).then((d) => ({ s, d })).catch(() => null))).then((all) => {
      const out: typeof hist = [];
      for (const x of all) {
        if (!x) continue;
        const rows = [...x.d.rows].sort((a, b) => b.margin - a.margin);
        const k = rows.findIndex((r) => r.id === id);
        if (k >= 0) out.push({ s: x.s, w: rows[k].w, l: rows[k].l, cw: rows[k].cw, cl: rows[k].cl, margin: rows[k].margin, rank: k + 1, conf: rows[k].conf });
      }
      setHist(out.reverse());
    });
  }, [meta, id]);
  const PL = usePlayers(season && !upcoming ? season : null);
  const roster = useMemo(() => (PL?.rows ?? []).filter((r) => r.tid === id).sort((a, b) => (b.min as number) - (a.min as number)), [PL, id]);
  const seasons = [...(meta?.seasons ?? []), ...(meta ? [meta.upcoming_season] : [])].reverse();
  const stats = S?.rows[id];
  const rankOfStat = (k: string, higher = true) => {
    if (!S || !stats) return "";
    const vals = Object.values(S.rows).map((r) => r[k]).filter((v) => v != null);
    return String(vals.filter((v) => (higher ? v > stats[k] : v < stats[k])).length + 1);
  };
  const cols = trend.filter((_, i) => i % Math.max(1, Math.floor(trend.length / 60)) === 0 || i === trend.length - 1);

  const row = (g: Game) => {
    const home = g.h === id;
    const opp = map.get(home ? g.a : g.h);
    const pw = g.p == null ? null : home ? g.p : 1 - g.p;
    const pmg = g.pm == null ? null : home ? g.pm : -g.pm;
    const act = g.ok ? (home ? (g.hs as number) - (g.as as number) : (g.as as number) - (g.hs as number)) : null;
    const rank = home ? g.ar : g.hr;
    return (
      <tr key={g.id}>
        <td className="l text-muted">{g.d.slice(5)}</td>
        <td className="l"><span className="inline-flex items-center gap-2">
          <span className="w-6 text-center text-xs text-faint">{g.n ? "N" : home ? "vs" : "@"}</span>
          <TeamLogo team={opp} size={20} />
          <Link href={`/team/${opp?.id ?? ""}/?season=${season}`} className="hover:text-accent">{rank != null && <span className="mr-1 text-xs text-faint">{rank}</span>}{opp?.name ?? "Non-D-I"}</Link>
        </span></td>
        <td>{pw == null ? "–" : pct(pw)}</td>
        <td>{signed(pmg, 1)}</td>
        <td className={act == null ? "" : act > 0 ? "text-accent2" : "text-[var(--bad)]"}>
          {act == null ? "" : `${act > 0 ? "W" : "L"} ${home ? g.hs : g.as}-${home ? g.as : g.hs}`}
        </td>
        <td className={act == null || pmg == null ? "" : act - pmg > 0 ? "text-accent2" : "text-[var(--bad)]"}>{act == null || pmg == null ? "" : signed(act - pmg, 1)}</td>
      </tr>
    );
  };

  const th = (t: string, l = false) => <th className={l ? "l" : ""} style={{ cursor: "default" }}>{t}</th>;
  return (
    <div>
      <div className="mb-6 flex items-center gap-5">
        <TeamLogo team={team} size={84} />
        <div className="flex-1">
          <h1 className="text-4xl font-semibold" style={{ textShadow: team?.color ? `0 0 40px #${team.color}55` : undefined }}>{team?.name ?? "Team"}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-muted">
            <span className="chip">{shortConf(confName) || "–"}</span>
            {!upcoming && <span className="num">{rec.w}-{rec.l} ({rec.cw}-{rec.cl} conf)</span>}
            {snap && <span className="chip" style={{ color: "var(--accent)" }}>#{snap.rM} of {snap.n} · AdjEM</span>}
          </div>
        </div>
        <select value={season} onChange={(e) => router.replace(`?season=${e.target.value}`, { scroll: false })}>
          {seasons.map((s) => <option key={s} value={s}>{seasonLabel(s)}{s === meta?.upcoming_season ? " (preview)" : ""}</option>)}
        </select>
      </div>

      {upcoming && <div className="card mb-4 px-4 py-3 text-[13px] text-muted">Preseason projection: ratings come from last season and the fitted prior only (no 2026-27 games played yet).</div>}

      <div className="mb-6 grid grid-cols-4 gap-4">
        {snap ? (<>
          <Stat label="Adj. Efficiency Margin" value={signed(snap.margin, 1)} sub={`#${snap.rM} in D-I`} pctl={snap.pm} />
          <Stat label="Adj. Offense" value={fmt(snap.off, 1)} sub={`#${snap.rO} · pts / 100 poss`} pctl={snap.po} />
          <Stat label="Adj. Defense" value={fmt(snap.def, 1)} sub={`#${snap.rD} · pts allowed / 100`} pctl={snap.pd} />
          <Stat label="Adj. Tempo" value={fmt(snap.tempo, 1)} sub={`#${snap.rT} · possessions / game`} pctl={null} />
        </>) : Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton h-24" />)}
      </div>

      <div className="mb-6 grid grid-cols-3 gap-6">
        <div className="card col-span-2 p-4">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">Rating trend (AdjEM as of each date)</h2>
          {trend.length ? (
            <div className="h-64">
              <ResponsiveContainer>
                <LineChart data={cols} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                  <CartesianGrid stroke="#232c3b" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="d" tick={{ fill: "#8b96aa", fontSize: 11 }} tickFormatter={(d) => d.slice(5)} minTickGap={40} stroke="#232c3b" />
                  <YAxis tick={{ fill: "#8b96aa", fontSize: 11 }} domain={["auto", "auto"]} stroke="#232c3b" width={36} />
                  <Tooltip contentStyle={{ background: "#10151d", border: "1px solid #232c3b", borderRadius: 8 }} formatter={(v) => (typeof v === "number" ? v.toFixed(1) : String(v))} />
                  <Line type="monotone" dataKey="margin" name="AdjEM" stroke="#f2b544" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="flex h-64 items-center justify-center text-muted">{upcoming ? "Trend appears once games are played." : <div className="skeleton h-full w-full" />}</div>}
        </div>
        <div className="card p-4">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">Four factors</h2>
          {stats ? (
            <table className="dense"><thead><tr>{th("", true)}{th("Off")}{th("Rk")}{th("Def")}{th("Rk")}</tr></thead><tbody>
              {([["eFG%", "efg", "efg_d", true], ["TOV%", "tov", "tov_d", false], ["ORB%", "orb", "orb_d", true], ["FT rate", "ftr", "ftr_d", true]] as [string, string, string, boolean][]).map(([l, o, d, hb]) => (
                <tr key={l}><td className="l text-muted">{l}</td><td>{fmt(stats[o] * 100, 1)}</td><td className="text-faint">{rankOfStat(o, hb)}</td><td>{fmt(stats[d] * 100, 1)}</td><td className="text-faint">{rankOfStat(d, !hb)}</td></tr>
              ))}
            </tbody></table>
          ) : <div className="skeleton h-28" />}
          {stats && <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
            <span>3P rate <b className="num text-ink">{fmt(stats.three_rate * 100, 1)}%</b></span><span>3P% <b className="num text-ink">{fmt(stats.three_pct * 100, 1)}%</b></span>
            <span>2P% <b className="num text-ink">{fmt(stats.two_pct * 100, 1)}%</b></span><span>FT% <b className="num text-ink">{fmt(stats.ft_pct * 100, 1)}%</b></span>
          </div>}
        </div>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-6">
        <div className="card col-span-2 overflow-hidden">
          <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">Results</h2>
          <div className="max-h-[520px] overflow-auto p-2">
            <table className="dense"><thead><tr>{th("Date", true)}{th("Opponent", true)}{th("Win %")}{th("Pred")}{th("Result")}{th("vs exp")}</tr></thead>
              <tbody>{past.length ? past.map(row) : <tr><td colSpan={6} className="py-8 text-center text-muted">No completed games yet.</td></tr>}</tbody></table>
          </div>
        </div>
        <div className="flex flex-col gap-6">
          <div className="card overflow-hidden">
            <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">Remaining schedule</h2>
            <div className="max-h-[300px] overflow-auto p-2">
              <table className="dense"><thead><tr>{th("Date", true)}{th("Opponent", true)}{th("Win %")}{th("Pred")}{th("")}{th("")}</tr></thead>
                <tbody>{rest.length ? rest.map(row) : <tr><td colSpan={6} className="py-6 text-center text-muted">No remaining games.</td></tr>}</tbody></table>
            </div>
          </div>
          <div className="card overflow-hidden">
            <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">{shortConf(confName)} standings</h2>
            <div className="max-h-[260px] overflow-auto p-2">
              <table className="dense"><thead><tr>{th("Team", true)}{th("Conf")}{th("AdjEM")}</tr></thead><tbody>
                {confRows.map((r) => (
                  <tr key={r.id} style={r.id === id ? { background: "rgba(242,181,68,.08)" } : undefined}>
                    <td className="l"><span className="inline-flex items-center gap-2"><TeamLogo team={map.get(r.id)} size={18} /><Link href={`/team/${r.id}/?season=${season}`} className="hover:text-accent">{map.get(r.id)?.short}</Link></span></td>
                    <td>{r.cw}-{r.cl}</td><td>{signed(r.margin, 1)}</td></tr>
                ))}
              </tbody></table>
            </div>
          </div>
        </div>
      </div>
      {roster.length > 0 && (
        <div className="card mb-6 overflow-hidden">
          <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">Roster and player stats</h2>
          <div className="p-2"><table className="dense"><thead><tr>{th("Player", true)}{th("Pos", true)}{th("Ht", true)}{th("Cl", true)}{th("GP")}{th("MPG")}{th("PPG")}{th("RPG")}{th("APG")}{th("TS%")}{th("USG")}{th("Impact")}</tr></thead>
            <tbody>{roster.slice(0, 14).map((r) => (
              <tr key={r.id}><td className="l"><Link className="font-medium hover:text-accent" href={`/player/?id=${r.id}&season=${season}`}>{r.name}</Link></td>
                <td className="l text-muted">{String(r.pos ?? "")}</td><td className="l text-muted">{String(r.ht ?? "")}</td><td className="l text-muted">{String(r.cls ?? "")}</td>
                <td>{r.gp}</td><td>{fmt(r.mpg as number, 1)}</td><td>{fmt(r.ppg as number, 1)}</td><td>{fmt(r.rpg as number, 1)}</td><td>{fmt(r.apg as number, 1)}</td>
                <td>{r.ts == null ? "–" : fmt((r.ts as number) * 100, 1)}</td><td>{fmt(r.usg as number, 1)}</td>
                <td><span className="block rounded px-1.5" style={{ background: heat(r.pc_imp as number | null) }}>{signed(r.imp as number, 1)}</span></td></tr>))}</tbody></table></div>
        </div>
      )}
      {hist.length > 0 && (
        <div className="card mb-6 overflow-hidden">
          <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">Previous seasons</h2>
          <div className="p-2"><table className="dense"><thead><tr>{th("Season", true)}{th("Conference", true)}{th("W-L")}{th("Conf")}{th("AdjEM")}{th("Rank")}</tr></thead>
            <tbody>{hist.map((h) => (
              <tr key={h.s}><td className="l"><Link className="hover:text-accent" href={`/team/${id}/?season=${h.s}`}>{seasonLabel(h.s)}</Link></td><td className="l text-muted">{shortConf(h.conf)}</td>
                <td>{h.w}-{h.l}</td><td>{h.cw}-{h.cl}</td><td>{signed(h.margin, 1)}</td><td>{h.rank}</td></tr>))}</tbody></table></div>
        </div>
      )}
      <p className="text-xs text-faint">Predictions shown are the pregame values from the walk-forward model (no knowledge of the result). Player impact is a fitted box-score rating (see Methodology).</p>
    </div>
  );
}
