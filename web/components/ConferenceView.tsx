"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useJson, useMeta, useTeams } from "@/lib/data";
import { fmt, pct, prettyDate, seasonLabel, signed } from "@/lib/util";
import { shortConf } from "./RankingsView";
import TeamLogo from "./TeamLogo";
import type { ConfRow } from "./ConferencesView";
import SeasonChip from "./ui/SeasonChip";

type SRow = { id: string; exp_w: number; cw: number; cg: number; exp_finish: number; finish: number[]; p_title: number; p_share: number; p_qual: number; p_bye: Record<string, number>; best: number; worst: number };
type Snap = { asof: string; nsim: number; conferences: Record<string, { name: string; n_remaining: number; config: { status: string; rules: string[]; qualifiers: number; bye_seed_lines: number[]; source_url: string | null }; rows: SRow[] }> };
type TB = { rows: { id: string; conference: string; status: string; rules: string[]; qualifiers: number; source_url: string | null; notes: string | null; researched: string }[] };
type RK = { asof?: string; rows: { id: string; conf: string; w: number; l: number; cw: number; cl: number; off: number; def: number; margin: number; tempo: number; sos: number | null }[] };

const RULE_TEXT: Record<string, string> = {
  h2h: "Head-to-head record among the tied teams", vs_standings: "Record vs the highest-placed teams outside the tie, going down the standings",
  road_pct: "Conference road winning percentage", road_vs_standings: "Road record vs highest-placed teams, going down",
  h2h_point_diff: "Point differential in games among the tied teams", point_diff: "Conference point differential",
  rating: "Our adjusted-efficiency rating (substitute for NET / RPI)", random: "Coin flip / draw",
};

function probHeat(p: number) {
  const a = Math.min(1, p * 1.15);
  return `rgba(76, 201, 192, ${(0.06 + a * 0.6).toFixed(3)})`;
}

export default function ConferenceView({ id }: { id: string }) {
  const meta = useMeta();
  const { map } = useTeams();
  const sp = useSearchParams();
  const router = useRouter();
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const { data: RKD } = useJson<RK>(season ? `rankings/${season}.json` : null);
  const { data: ST } = useJson<{ snapshots: Snap[] }>(season ? `standings/${season}.json` : null);
  const { data: TB } = useJson<TB>("tiebreakers.json");
  const { data: CS } = useJson<{ rows: ConfRow[] }>(season ? `conferences/${season}.json` : null);
  const [snapIdx, setSnapIdx] = useState<number | null>(null);

  const tb = TB?.rows.find((r) => r.id === id);
  const confName = tb?.conference ?? "";
  const cstat = CS?.rows.find((r) => r.id === id);
  const teams = useMemo(() => (RKD?.rows ?? []).filter((r) => r.conf === confName).sort((a, b) => b.margin - a.margin), [RKD, confName]);
  const snaps = ST?.snapshots ?? [];
  const idx = snapIdx ?? Math.max(0, snaps.length - 2 >= 0 && snaps.length > 1 ? snaps.length - 2 : snaps.length - 1);
  const snap = snaps[idx];
  const sc = snap?.conferences[id];
  const isFinal = !!sc && sc.n_remaining === 0;
  const nTeams = sc?.rows.length ?? 0;
  const srows = useMemo(() => [...(sc?.rows ?? [])].sort((a, b) => a.exp_finish - b.exp_finish), [sc]);
  const q = sc?.config.qualifiers ?? 0;

  const flag = (r: SRow) => {
    if (!sc) return "";
    const f: string[] = [];
    if (r.worst === 1) f.push("Clinched title");
    else if (r.best > 1) f.push("Out of title race");
    if (q < nTeams) {
      if (r.worst <= q && r.worst > 1) f.push("Clinched berth");
      if (r.best > q) f.push("Eliminated");
    }
    return f.join(" · ");
  };

  return (
    <div>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <Link href="/conferences/" className="text-xs text-muted hover:text-accent">← All conferences</Link>
          <h1 className="text-4xl font-semibold">{confName || "Conference"}<SeasonChip season={season} /></h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-muted">
            {cstat && <span className="chip">#{cstat.rank} of {CS?.rows.length} by avg AdjEM</span>}
            {cstat && <span className="chip">Avg AdjEM {signed(cstat.em, 1)}</span>}
            {cstat && <span className="chip">Non-conf {cstat.nc_w}-{cstat.nc_l} ({signed(cstat.nc_over, 1)} vs expected)</span>}
            {tb && <span className="chip" style={{ color: tb.status === "verified" ? "var(--accent-2)" : "var(--accent)" }}>Tiebreakers: {tb.status}</span>}
          </div>
        </div>
        <select value={season} onChange={(e) => router.replace(`?season=${e.target.value}`, { scroll: false })}>
          {(meta?.seasons ?? []).slice().reverse().map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
        </select>
      </div>

      <div className="card mb-6 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-4">
          <h2 className="text-sm font-medium uppercase tracking-wider text-muted">
            {isFinal ? "Final standings (tiebreakers applied)" : "Projected standings"}{snap ? ` · as of ${prettyDate(snap.asof)}` : ""}
          </h2>
          {snaps.length > 1 && (
            <select value={idx} onChange={(e) => setSnapIdx(+e.target.value)} aria-label="Snapshot date">
              {snaps.map((s, i) => <option key={s.asof} value={i}>{prettyDate(s.asof)}{s.conferences[id]?.n_remaining === 0 ? " (final)" : ""}</option>)}
            </select>
          )}
        </div>
        {!sc ? (
          <div className="p-8 text-center text-muted">
            {ST ? "No simulation snapshot for this conference and season yet." : season >= 2026 ? "Loading…" : "Standings simulations are generated for the current season and replay dates."}
          </div>
        ) : (
          <div className="overflow-auto p-2">
            <table className="dense">
              <thead>
                <tr>
                  <th className="l">Team</th><th>Conf</th><th>Exp W</th><th>Exp finish</th><th>Title</th>{q < nTeams && <th>Top {q}</th>}
                  {sc.config.bye_seed_lines.map((b) => <th key={b}>Top {b}</th>)}<th>Range</th>
                  {Array.from({ length: nTeams }).map((_, i) => <th key={i} style={{ cursor: "default" }}>{i + 1}</th>)}
                  <th className="l">Status</th>
                </tr>
              </thead>
              <tbody>
                {srows.map((r) => {
                  const t = map.get(r.id);
                  return (
                    <tr key={r.id}>
                      <td className="l"><span className="inline-flex items-center gap-2"><TeamLogo team={t} size={20} /><Link className="font-medium hover:text-accent" href={`/team/${r.id}/?season=${season}`}>{t?.short ?? r.id}</Link></span></td>
                      <td>{r.cw}-{r.cg - r.cw}</td>
                      <td>{fmt(r.exp_w, 1)}</td><td>{fmt(r.exp_finish, 1)}</td>
                      <td style={{ background: probHeat(r.p_title) }}>{pct(r.p_title, r.p_title < 0.1 && r.p_title > 0 ? 1 : 0)}</td>
                      {q < nTeams && <td style={{ background: probHeat(r.p_qual) }}>{pct(r.p_qual, 0)}</td>}
                      {sc.config.bye_seed_lines.map((b) => <td key={b} style={{ background: probHeat(r.p_bye[String(b)] ?? 0) }}>{pct(r.p_bye[String(b)] ?? 0, 0)}</td>)}
                      <td className="text-muted">{r.best}-{r.worst}</td>
                      {r.finish.map((p, i) => <td key={i} style={{ background: probHeat(p * 2), color: p < 0.005 ? "var(--faint)" : undefined }}>{p < 0.005 ? "" : (p * 100).toFixed(0)}</td>)}
                      <td className="l text-xs text-muted">{flag(r)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="px-2 pb-1 pt-3 text-xs text-faint">
              {snap?.nsim.toLocaleString()} simulations of the {sc.n_remaining} remaining conference games (predicted margin plus noise; known results fixed; real tiebreaker rules).
              Finish columns show the probability of each finishing place (%). Range = best-worst possible finish by win-count bounds (ties assumed favorable / unfavorable). Field size {q} and bye lines are per-league config values.
            </p>
          </div>
        )}
      </div>

      <div className="mb-6 grid grid-cols-3 gap-6">
        <div className="card col-span-2 overflow-hidden">
          <h2 className="px-4 pt-4 text-sm font-medium uppercase tracking-wider text-muted">Power ranking · ratings as of {RKD?.asof ? prettyDate(RKD.asof) : seasonLabel(season || 2026)}</h2>
          <div className="p-2">
            <table className="dense">
              <thead><tr><th>#</th><th className="l">Team</th><th>W-L</th><th>Conf</th><th>AdjEM</th><th>AdjO</th><th>AdjD</th><th>Tempo</th><th>SOS</th></tr></thead>
              <tbody>
                {teams.map((r, i) => (
                  <tr key={r.id}>
                    <td className="text-muted">{i + 1}</td>
                    <td className="l"><span className="inline-flex items-center gap-2"><TeamLogo team={map.get(r.id)} size={20} /><Link className="font-medium hover:text-accent" href={`/team/${r.id}/?season=${season}`}>{map.get(r.id)?.name}</Link></span></td>
                    <td>{r.w}-{r.l}</td><td>{r.cw}-{r.cl}</td><td className="font-medium">{signed(r.margin, 1)}</td><td>{fmt(r.off, 1)}</td><td>{fmt(r.def, 1)}</td><td>{fmt(r.tempo, 1)}</td><td>{signed(r.sos, 1)}</td>
                  </tr>
                ))}
                {!RKD && <tr><td colSpan={9}><div className="skeleton h-24" /></td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card p-5">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">Tiebreaker rules</h2>
          {tb ? (
            <>
              <ol className="mb-3 list-decimal space-y-1 pl-5 text-[13px]">{tb.rules.map((r) => <li key={r}>{RULE_TEXT[r] ?? r}</li>)}</ol>
              <p className="text-xs text-muted">Partial splits of 3+ team ties restart from step 1 for the teams still tied. Tournament field: {tb.qualifiers} teams.</p>
              <p className="mt-2 text-xs text-muted">{tb.notes}</p>
              <p className="mt-2 text-xs">
                Status: <b style={{ color: tb.status === "verified" ? "var(--accent-2)" : "var(--accent)" }}>{tb.status}</b>
                {tb.status === "verified" ? " (rule text found on an official conference page)" : " (official text not fully found; best-known or generic rules used)"}
              </p>
              {tb.source_url && <a className="mt-1 block truncate text-xs text-accent underline" href={tb.source_url} target="_blank" rel="noreferrer">Source ({tb.researched})</a>}
            </>
          ) : <div className="skeleton h-32" />}
          <p className="mt-3 text-xs text-faint">{shortConf(confName)} teams with the same conference record are ordered by these rules.</p>
        </div>
      </div>
    </div>
  );
}
