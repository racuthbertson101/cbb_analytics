"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable } from "@tanstack/react-table";
import { Game, Ratings, useJson, useMeta, useTeams } from "@/lib/data";
import { computeRankings, dateIndex, Row } from "@/lib/rankings";
import { fmt, heat, percentiles, prettyDate, seasonLabel, signed } from "@/lib/util";
import TeamLogo from "./TeamLogo";
import site from "@/config/site.json";
import Sparkline from "./Sparkline";

export const shortConf = (c?: string) =>
  (c || "")
    .replace(" Conference", "").replace("Atlantic Coast", "ACC").replace("Southeastern", "SEC")
    .replace("Metro Atlantic Athletic", "MAAC").replace("Mid-American", "MAC").replace("Mid-Eastern Athletic", "MEAC")
    .replace("Southwestern Athletic", "SWAC").replace("Coastal Athletic Association", "CAA").replace("Missouri Valley", "MVC")
    .replace("Mountain West", "MWC").replace("Atlantic Sun", "ASUN").replace("Conference USA", "C-USA")
    .replace("Western Athletic", "WAC").replace("United Athletic", "UAC").replace("West Coast", "WCC");

type Sys = { dates: string[]; teams: string[]; poss: number } & Record<string, (number | null)[][] | string[] | number>;
type R = Row & { conf: string; team: string; heat: Record<string, number | null>; rating: number | null; mrank: number | null; wab: number | null; sor: number | null; ncsos: number | null; q: (number | null)[] };

export const SYSTEMS = site.rankingSystems as [string, string][];

export default function RankingsView() {
  const meta = useMeta();
  const { teams, map } = useTeams();
  const sp = useSearchParams();
  const router = useRouter();
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const upcoming = !!meta && meta.upcoming_season != null && season === meta.upcoming_season;
  const confSeason = upcoming ? season - 1 : season;
  const { data: R } = useJson<Ratings>(meta && season && !upcoming ? `ratings/${season}.json` : null);
  const { data: G } = useJson<{ games: Game[] }>(meta && season && !upcoming ? `games/${season}.json` : null);
  const { data: SY } = useJson<Sys>(meta && season && !upcoming ? `systems/${season}.json` : null);
  const { data: PRE } = useJson<{ teams: string[]; off: (number | null)[]; def: (number | null)[]; tempo: (number | null)[] }>(upcoming ? `ratings/${season}_preseason.json` : null);
  const sys = sp.get("sys") || "adj";
  const view = sp.get("view") || "ratings";
  const lastDate = R?.dates[R.dates.length - 1];
  const asof = sp.get("asof") || lastDate || "";
  const [conf, setConf] = useState("All");
  const [q, setQ] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: view === "resume" ? "wab" : "rank", desc: view === "resume" }]);
  const sortKey = view + sys;
  const [lastKey, setLastKey] = useState(sortKey);
  if (lastKey !== sortKey) {
    setLastKey(sortKey);
    setSorting([{ id: view === "resume" ? "wab" : "rank", desc: view === "resume" }]);
  }

  const d1 = useMemo(() => new Set((teams ?? []).filter((t) => t.conf[String(confSeason)]).map((t) => t.id)), [teams, confSeason]);
  const rows: R[] = useMemo(() => {
    if (upcoming ? !PRE || !teams : !R || !G || !teams) return [];
    let base: Row[];
    if (upcoming && PRE) {
      const arr = PRE.teams.map((id, j) => ({ id, off: PRE.off[j], def: PRE.def[j], tempo: PRE.tempo[j] })).filter((x) => x.off != null && x.def != null && d1.has(x.id));
      arr.sort((a, b) => (b.off as number) - (b.def as number) - ((a.off as number) - (a.def as number)));
      base = arr.map((x, k) => ({ id: x.id, rank: k + 1, rankPrev: null, w: 0, l: 0, cw: 0, cl: 0, off: x.off as number, def: x.def as number, margin: (x.off as number) - (x.def as number), tempo: (x.tempo ?? NaN) as number, sos: null, luck: null, trend: [] }));
    } else base = computeRankings(R as Ratings, (G as { games: Game[] }).games, asof, d1);
    const si = SY ? dateIndex(SY.dates, asof) : -1;
    const col = (k: string, i: number, id: string) => {
      const j = SY ? SY.teams.indexOf(id) : -1;
      return SY && j >= 0 && i >= 0 ? (SY[k] as (number | null)[][])[i][j] : null;
    };
    if (SY && sys !== "adj" && si >= 0) {
      const rankMap = (i: number) => {
        const a = base.map((r) => [r.id, col(sys, i, r.id)] as const).filter((x) => x[1] != null) as [string, number][];
        a.sort((x, y) => (sys === "mrank" ? x[1] - y[1] : y[1] - x[1]));
        return new Map(a.map(([id], k) => [id, k + 1]));
      };
      const now = rankMap(si);
      const prev = si > 0 ? rankMap(si - 1) : null;
      base = base.filter((r) => now.has(r.id)).map((r) => ({ ...r, rank: now.get(r.id) as number, rankPrev: prev?.get(r.id) ?? null })).sort((a, b) => a.rank - b.rank);
    }
    const ps = {
      off: percentiles(base.map((r) => r.off), true),
      def: percentiles(base.map((r) => r.def), false),
      margin: percentiles(base.map((r) => r.margin), true),
      sos: percentiles(base.map((r) => r.sos), true),
      luck: percentiles(base.map((r) => r.luck), true),
    };
    return base.map((r, i) => ({
      ...r,
      rating: sys === "adj" ? (r.margin * ((SY?.poss as number) ?? 68.5)) / 100 : col(sys, si, r.id),
      mrank: col("mrank", si, r.id), wab: col("wab", si, r.id), sor: col("sor", si, r.id), ncsos: col("ncsos", si, r.id),
      q: ["q1w", "q1l", "q2w", "q2l", "q3w", "q3l", "q4w", "q4l"].map((k) => col(k, si, r.id)),
      conf: shortConf(map.get(r.id)?.conf[String(confSeason)]),
      team: map.get(r.id)?.name ?? r.id,
      heat: { off: ps.off[i], def: ps.def[i], margin: ps.margin[i], sos: ps.sos[i], luck: ps.luck[i] },
    }));
  }, [R, G, PRE, upcoming, teams, asof, d1, map, confSeason, SY, sys]);

  const confs = useMemo(() => ["All", ...Array.from(new Set(rows.map((r) => r.conf))).filter(Boolean).sort()], [rows]);
  const data = useMemo(
    () => rows.filter((r) => (conf === "All" || r.conf === conf) && (!q || r.team.toLowerCase().includes(q.toLowerCase()))),
    [rows, conf, q],
  );

  const setParam = (k: string, v: string | null) => {
    const p = new URLSearchParams(sp.toString());
    if (v) p.set(k, v);
    else p.delete(k);
    router.replace(`?${p.toString()}`, { scroll: false });
  };

  const heatCell = (k: string, digits: number, sign = false, useHeat = true) => {
    const Cell = ({ getValue, row }: { getValue: () => unknown; row: { original: R } }) => {
      const v = getValue() as number | null;
      const h = row.original.heat[k];
      return (
        <span className="block rounded px-1.5 py-[1px]" style={{ background: useHeat ? heat(h) : "transparent" }}>
          {sign ? signed(v, digits) : fmt(v, digits)}
        </span>
      );
    };
    return Cell;
  };

  const columns = useMemo<ColumnDef<R>[]>(
    () => [
      { id: "rank", header: "#", accessorFn: (r) => r.rank, cell: ({ getValue }) => <span className="text-muted">{getValue() as number}</span> },
      {
        id: "chg", header: "Δ7d", accessorFn: (r) => (r.rankPrev == null ? null : r.rankPrev - r.rank),
        cell: ({ getValue }) => {
          const v = getValue() as number | null;
          return v == null || v === 0 ? <span className="text-faint">·</span> : <span className={v > 0 ? "text-accent2" : "text-[var(--bad)]"}>{v > 0 ? "▲" : "▼"}{Math.abs(v)}</span>;
        },
      },
      {
        id: "team", header: "Team", meta: "l", accessorFn: (r) => r.team,
        cell: ({ row }) => (
          <Link href={`/team/${row.original.id}/?season=${season}`} className="flex items-center gap-2 hover:text-accent">
            <TeamLogo team={map.get(row.original.id)} size={22} />
            <span className="font-medium">{row.original.team}</span>
          </Link>
        ),
      },
      { id: "conf", header: "Conf", meta: "l", accessorFn: (r) => r.conf, cell: ({ getValue }) => <span className="text-muted">{getValue() as string}</span> },
      { id: "rec", header: "W-L", accessorFn: (r) => r.w / Math.max(1, r.w + r.l), cell: ({ row }) => `${row.original.w}-${row.original.l}` },
      ...(view === "resume"
        ? ([
            { id: "wab", header: "WAB", accessorFn: (r) => r.wab, cell: heatCell("luck", 1, true, false) },
            {
              id: "sor", header: "SOR", accessorFn: (r) => r.sor, sortDescFirst: false,
              cell: ({ getValue }) => { const v = getValue() as number | null; return v == null ? "–" : v < 0.001 ? "<0.1%" : (v * 100).toFixed(1) + "%"; },
            },
            ...[1, 2, 3, 4].map((q) => ({
              id: `q${q}`, header: `Q${q}`,
              accessorFn: (r: R) => (r.q[2 * (q - 1)] ?? 0) / Math.max(1, (r.q[2 * (q - 1)] ?? 0) + (r.q[2 * (q - 1) + 1] ?? 0)),
              cell: ({ row }: { row: { original: R } }) => `${row.original.q[2 * (q - 1)] ?? "–"}-${row.original.q[2 * (q - 1) + 1] ?? "–"}`,
            })),
            { id: "sos", header: "SOS", accessorFn: (r) => r.sos, cell: heatCell("sos", 1, true) },
            { id: "ncsos", header: "NC SOS", accessorFn: (r) => r.ncsos, cell: ({ getValue }) => <span>{signed(getValue() as number | null, 1)}</span> },
            { id: "luck", header: "Luck", accessorFn: (r) => r.luck, cell: heatCell("luck", 1, true) },
          ] as ColumnDef<R>[])
        : ([
            {
              id: "rating", header: sys === "mrank" ? "Mean rank" : "Rating", accessorFn: (r) => (sys === "mrank" ? r.mrank : r.rating), sortDescFirst: sys !== "mrank",
              cell: ({ getValue }) => <b className="num">{sys === "mrank" ? fmt(getValue() as number | null, 1) : signed(getValue() as number | null, 1)}</b>,
            },
            { id: "margin", header: "AdjEM", accessorFn: (r) => r.margin, cell: heatCell("margin", 1, true) },
            { id: "off", header: "AdjO", accessorFn: (r) => r.off, cell: heatCell("off", 1) },
            { id: "def", header: "AdjD", accessorFn: (r) => r.def, sortDescFirst: false, cell: heatCell("def", 1) },
            { id: "tempo", header: "Tempo", accessorFn: (r) => r.tempo, cell: heatCell("tempo", 1, false, false) },
            { id: "sos", header: "SOS", accessorFn: (r) => r.sos, cell: heatCell("sos", 1, true) },
            { id: "luck", header: "Luck", accessorFn: (r) => r.luck, cell: heatCell("luck", 1, true) },
            { id: "trend", header: "Trend", enableSorting: false, accessorFn: (r) => r.trend, cell: ({ getValue }) => <Sparkline data={getValue() as number[]} /> },
          ] as ColumnDef<R>[])),
    ],
    [map, season, view, sys], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const table = useReactTable({
    data, columns, state: { sorting }, onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), sortDescFirst: true,
  });
  const loading = upcoming ? !PRE || !teams : !R || !G || !teams;
  const histIdx = R && asof ? dateIndex(R.dates, asof) : -1;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Rankings</h1>
          <p className="mt-1 text-muted">
            Adjusted efficiency (points per 100 possessions vs an average D-I team). {seasonLabel(season || 2026)} · {upcoming ? "preseason projection (last two seasons plus roster changes)" : <>as of {asof ? prettyDate(asof) : "…"}</>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={season}
            onChange={(e) => {
              const p = new URLSearchParams(sp.toString());
              p.set("season", e.target.value);
              p.delete("asof");
              router.replace(`?${p}`, { scroll: false });
            }}
          >
            {[...(meta?.seasons ?? []), ...(meta?.upcoming_season ? [meta.upcoming_season] : [])].reverse().map((s) => (
              <option key={s} value={s}>{seasonLabel(s)}{s === meta?.upcoming_season ? " (preseason)" : ""}</option>
            ))}
          </select>
          {!upcoming && (<input
            type="date" value={asof} min={R?.dates[0]} max={lastDate} aria-label="As of date"
            onChange={(e) => setParam("asof", e.target.value && e.target.value !== lastDate ? e.target.value : null)}
          />)}
          {!upcoming && (<>
          <select value={sys} onChange={(e) => setParam("sys", e.target.value === "adj" ? null : e.target.value)} aria-label="Ranking system">
            {SYSTEMS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <div className="flex overflow-hidden rounded-md border border-line text-xs">
            {[["ratings", "Ratings"], ["resume", "Résumé"]].map(([k, l]) => (
              <button key={k} onClick={() => setParam("view", k === "ratings" ? null : k)} className={`px-3 py-1.5 ${view === k ? "bg-surface2 text-ink" : "text-muted"}`}>{l}</button>
            ))}
          </div>
          </>)}
          <select value={conf} onChange={(e) => setConf(e.target.value)}>
            {confs.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input placeholder="Search team" value={q} onChange={(e) => setQ(e.target.value)} className="w-40" />
        </div>
      </div>
      {R && histIdx >= 0 && histIdx < R.dates.length - 1 && (
        <div className="card mb-3 px-3 py-2 text-[13px] text-muted">
          Historical view: ratings use only games before {prettyDate(R.dates[histIdx])}.{" "}
          <button className="text-accent underline" onClick={() => setParam("asof", null)}>Jump to final</button>
        </div>
      )}
      <div className="card overflow-hidden">
        <div className="max-h-[calc(100vh-230px)] overflow-auto">
          <table className="dense">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th key={h.id} className={(h.column.columnDef.meta as string) === "l" ? "l" : ""} onClick={h.column.getToggleSortingHandler()}>
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {{ asc: " ↑", desc: " ↓" }[h.column.getIsSorted() as string] ?? ""}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 18 }).map((_, i) => (
                  <tr key={i}><td colSpan={12}><div className="skeleton h-5 w-full" /></td></tr>
                ))
              ) : data.length === 0 ? (
                <tr><td colSpan={12} className="py-10 text-center text-muted">No teams match. Clear the search or conference filter.</td></tr>
              ) : (
                table.getRowModel().rows.map((r) => (
                  <tr key={r.id}>
                    {r.getVisibleCells().map((c) => (
                      <td key={c.id} className={(c.column.columnDef.meta as string) === "l" ? "l" : ""}>
                        {flexRender(c.column.columnDef.cell, c.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <p className="mt-3 text-xs text-faint">
        AdjO/AdjD: points scored/allowed per 100 possessions against an average opponent (AdjD lower is better). SOS: mean opponent AdjEM.
        Luck: actual wins minus wins expected from pregame win probabilities (D-I games). Heat = percentile among D-I teams.
        Résumé metrics use our adjusted-efficiency rating in place of NET: WAB = wins above a bubble team (rank 45), SOR = chance an average top-25 team matches the record (lower is better), quadrants use NCAA rank cutoffs by site. Other systems and résumé columns update weekly; the player-driven rating is season-end only.
      </p>
    </div>
  );
}
