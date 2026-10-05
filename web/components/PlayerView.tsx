"use client";
import Link from "next/link";
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useJson, useMeta, useTeams } from "@/lib/data";
import { usePlayers } from "@/lib/players";
import { fmt, heat, prettyDate, seasonLabel, signed } from "@/lib/util";
import TeamLogo from "./TeamLogo";
import ShotChart, { Bins } from "./ShotChart";
import SeasonChip from "./ui/SeasonChip";

const IMP_TIP = "Experimental box-score rating (points per 100 possessions vs an average D-I player). Known bias: it overrates rebounders and shot blockers (centers average about +14, guards about -2), so compare players at the same position only.";

type Logs = { cols: string[]; logs: Record<string, (string | number)[][]> };
type Career = Record<string, (string | number | null)[][]>;

const BARS: [string, string, string, number][] = [
  ["Usage", "usg", "pc_usg", 1], ["True shooting", "ts", "pc_ts", 100], ["eFG%", "efg", "pc_efg", 100], ["Assist rate", "ast_pct", "pc_ast_pct", 1],
  ["Turnover rate", "tov_pct", "pc_tov_pct", 1], ["Off. rebound", "orb_pct", "pc_orb_pct", 1], ["Def. rebound", "drb_pct", "pc_drb_pct", 1],
  ["Steal rate", "stl_pct", "pc_stl_pct", 1], ["Block rate", "blk_pct", "pc_blk_pct", 1], ["FT rate", "ftr", "pc_ftr", 100],
];

export default function PlayerView() {
  const sp = useSearchParams();
  const router = useRouter();
  const meta = useMeta();
  const { map } = useTeams();
  const id = sp.get("id") || "";
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const pl = usePlayers(season || null);
  const p = useMemo(() => pl?.rows.find((r) => r.id === id) ?? null, [pl, id]);
  const { data: L } = useJson<Logs>(p && meta && season > meta.current_season - 3 ? `playerlogs/${season}/${p.tid}.json` : null);
  const { data: C } = useJson<Career>(id ? `playercareer/${Number(id) % 100}.json` : null);
  const hasShots = !!p && !!season && !!meta?.shot_seasons?.includes(season);
  const { data: SH } = useJson<{ players: Record<string, Bins> }>(hasShots ? `shots/${season}/${p?.tid}.json` : null);
  const { data: SHL } = useJson<{ bins: Bins }>(hasShots ? `shots/${season}/league.json` : null);
  const team = p ? map.get(p.tid as string) : undefined;
  const career = C?.[id] ?? [];
  const log = (L?.logs[id] ?? []).slice().reverse();

  if (pl && !p) {
    return <div className="card mx-auto mt-10 max-w-xl p-8 text-center text-muted">No player with at least 50 minutes matches that ID in {seasonLabel(season)}. <Link className="text-accent underline" href="/players/">Browse players</Link></div>;
  }
  return (
    <div>
      <div className="mb-6 flex items-center gap-5">
        <TeamLogo team={team} size={72} />
        <div className="flex-1">
          <h1 className="text-4xl font-semibold">{p?.name ?? "…"}<SeasonChip season={season} /></h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-muted">
            {team && <Link href={`/team/${team.id}/?season=${season}`} className="chip hover:text-ink">{team.name}</Link>}
            {p?.pos && <span className="chip">{p.pos}</span>}
            {p?.ht && <span className="chip">{String(p.ht)}</span>}
            {p?.cls && <span className="chip">{String(p.cls)}</span>}
            {p && <span className="num">{p.gp} GP · {fmt(p.mpg as number, 1)} MPG</span>}
          </div>
        </div>
        <select value={season} onChange={(e) => router.replace(`?id=${id}&season=${e.target.value}`, { scroll: false })}>
          {(career.length ? career.map((c) => c[0] as number) : [season]).slice().reverse().map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
        </select>
      </div>
      {p && (
        <>
          <div className="mb-6 grid grid-cols-5 gap-4">
            {[["PPG", fmt(p.ppg as number, 1)], ["RPG", fmt(p.rpg as number, 1)], ["APG", fmt(p.apg as number, 1)], ["TS%", fmt((p.ts as number) * 100, 1)], ["Box impact (experimental)", signed(p.imp as number, 1)]].map(([l, v], i) => (
              <div key={l} className="card p-4" style={i === 4 ? { boxShadow: `inset 0 -3px 0 ${heat(p.pc_imp as number | null)}` } : undefined}>
                <div className="text-xs uppercase tracking-wider text-muted" title={i === 4 ? IMP_TIP : undefined}>{l}{i === 4 && <span className="ml-1 cursor-help normal-case">ⓘ</span>}</div><div className="num mt-1 text-3xl font-semibold">{v}</div>
                {i === 4 && <div className="text-xs text-muted">off {signed(p.imp_o as number, 1)} · def {signed(p.imp_d as number, 1)}</div>}
              </div>))}
          </div>
          <div className="mb-6 grid grid-cols-3 gap-6">
            <div className="card p-5">
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted">Percentile vs D-I ({pl?.refMin}+ min)</h2>
              {p.pc_usg == null ? <p className="text-sm text-muted">Fewer than {pl?.refMin} minutes: no percentile ranks.</p> : (
                <div className="space-y-2">{BARS.map(([l, k, pc, sc]) => {
                  const v = p[pc] as number | null;
                  return (
                    <div key={k} className="flex items-center gap-3 text-[13px]">
                      <span className="w-28 text-muted">{l}</span>
                      <div className="relative h-3 flex-1 rounded-full bg-surface2"><div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${(v ?? 0) * 100}%`, background: heat(v == null ? null : Math.max(v, 0.03)) === "transparent" ? "#39445a" : heat(0.5 + (v as number) / 2) }} /></div>
                      <span className="num w-10 text-right">{p[k] == null ? "–" : fmt((p[k] as number) * sc, 1)}</span>
                      <span className="num w-8 text-right text-xs text-faint">{v == null ? "" : Math.round(v * 100)}</span>
                    </div>);
                })}</div>)}
            </div>
            <div className="card col-span-2 overflow-hidden">
              <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">Career</h2>
              <div className="p-2"><table className="dense"><thead><tr><th className="l">Season</th><th className="l">Team</th><th>GP</th><th>MPG</th><th>PPG</th><th>RPG</th><th>APG</th><th>TS%</th><th>USG</th><th title={IMP_TIP}>Box impact (exp.)</th></tr></thead>
                <tbody>{career.map((c) => (
                  <tr key={String(c[0])}><td className="l"><Link className="hover:text-accent" href={`?id=${id}&season=${c[0]}`}>{seasonLabel(c[0] as number)}</Link></td>
                    <td className="l">{map.get(c[1] as string)?.short}</td><td>{c[2]}</td><td>{c[3]}</td><td>{c[4]}</td><td>{c[5]}</td><td>{c[6]}</td>
                    <td>{c[7] == null ? "–" : fmt((c[7] as number) * 100, 1)}</td><td>{c[8] ?? "–"}</td><td>{signed(c[9] as number, 1)}</td></tr>))}</tbody></table></div>
            </div>
          </div>
          {SH?.players[id] && SHL && (
            <div className="card mb-6 p-4"><h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted">Shot chart</h2><ShotChart bins={SH.players[id]} league={SHL.bins} /></div>
          )}
          <div className="card overflow-hidden">
            <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">Game log</h2>
            <div className="max-h-[480px] overflow-auto p-2">
              {L ? <table className="dense"><thead><tr><th className="l">Date</th><th className="l">Opp</th><th>Result</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TO</th><th>FG</th><th>3P</th><th>FT</th></tr></thead>
                <tbody>{log.map((g) => (
                  <tr key={String(g[0])}><td className="l text-muted">{prettyDate(g[1] as string).replace(/, \d{4}$/, "")}</td>
                    <td className="l"><span className="inline-flex items-center gap-2"><span className="w-4 text-xs text-faint">{g[3]}</span><TeamLogo team={map.get(g[2] as string)} size={18} />{map.get(g[2] as string)?.short ?? "Non-D-I"}</span></td>
                    <td className={(g[4] as number) > 0 ? "text-accent2" : "text-[var(--bad)]"}>{(g[4] as number) > 0 ? "W" : "L"} {signed(g[4] as number, 0)}</td>
                    <td>{g[5]}</td><td className="font-medium">{g[6]}</td><td>{g[7]}</td><td>{g[8]}</td><td>{g[9]}</td><td>{g[10]}</td><td>{g[11]}</td>
                    <td>{g[13]}-{g[14]}</td><td>{g[15]}-{g[16]}</td><td>{g[17]}-{g[18]}</td></tr>))}</tbody></table>
                : <p className="p-6 text-center text-muted">{season > (meta?.current_season ?? 0) - 3 ? "Loading game log…" : "Game logs are kept for the three most recent seasons."}</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
