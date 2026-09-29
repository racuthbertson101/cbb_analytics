"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable } from "@tanstack/react-table";
import { Game, Ratings, useJson, useMeta, useTeams } from "@/lib/data";
import { computeRankings, dateIndex, Row } from "@/lib/rankings";
import { fmt, heat, percentiles, prettyDate, seasonLabel, signed } from "@/lib/util";
import TeamLogo from "./TeamLogo";
import Sparkline from "./Sparkline";

export const shortConf = (c?: string) =>
  (c || "")
    .replace(" Conference", "").replace("Atlantic Coast", "ACC").replace("Southeastern", "SEC")
    .replace("Metro Atlantic Athletic", "MAAC").replace("Mid-American", "MAC").replace("Mid-Eastern Athletic", "MEAC")
    .replace("Southwestern Athletic", "SWAC").replace("Coastal Athletic Association", "CAA").replace("Missouri Valley", "MVC")
    .replace("Mountain West", "MWC").replace("Atlantic Sun", "ASUN").replace("Conference USA", "C-USA")
    .replace("Western Athletic", "WAC").replace("West Coast", "WCC");

type R = Row & { conf: string; team: string; heat: Record<string, number | null> };

export default function RankingsView() {
  const meta = useMeta();
  const { teams, map } = useTeams();
  const sp = useSearchParams();
  const router = useRouter();
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const { data: R } = useJson<Ratings>(season ? `ratings/${season}.json` : null);
  const { data: G } = useJson<{ games: Game[] }>(season ? `games/${season}.json` : null);
  const lastDate = R?.dates[R.dates.length - 1];
  const asof = sp.get("asof") || lastDate || "";
  const [conf, setConf] = useState("All");
  const [q, setQ] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "rank", desc: false }]);

  const d1 = useMemo(() => new Set((teams ?? []).filter((t) => t.conf[String(season)]).map((t) => t.id)), [teams, season]);
  const rows: R[] = useMemo(() => {
    if (!R || !G || !teams) return [];
    const base = computeRankings(R, G.games, asof, d1);
    const ps = {
      off: percentiles(base.map((r) => r.off), true),
      def: percentiles(base.map((r) => r.def), false),
      margin: percentiles(base.map((r) => r.margin), true),
      sos: percentiles(base.map((r) => r.sos), true),
      luck: percentiles(base.map((r) => r.luck), true),
    };
    return base.map((r, i) => ({
      ...r,
      conf: shortConf(map.get(r.id)?.conf[String(season)]),
      team: map.get(r.id)?.name ?? r.id,
      heat: { off: ps.off[i], def: ps.def[i], margin: ps.margin[i], sos: ps.sos[i], luck: ps.luck[i] },
    }));
  }, [R, G, teams, asof, d1, map, season]);

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
      { id: "margin", header: "AdjEM", accessorFn: (r) => r.margin, cell: heatCell("margin", 1, true) },
      { id: "off", header: "AdjO", accessorFn: (r) => r.off, cell: heatCell("off", 1) },
      { id: "def", header: "AdjD", accessorFn: (r) => r.def, sortDescFirst: false, cell: heatCell("def", 1) },
      { id: "tempo", header: "Tempo", accessorFn: (r) => r.tempo, cell: heatCell("tempo", 1, false, false) },
      { id: "sos", header: "SOS", accessorFn: (r) => r.sos, cell: heatCell("sos", 1, true) },
      { id: "luck", header: "Luck", accessorFn: (r) => r.luck, cell: heatCell("luck", 1, true) },
      { id: "trend", header: "Trend", enableSorting: false, accessorFn: (r) => r.trend, cell: ({ getValue }) => <Sparkline data={getValue() as number[]} /> },
    ],
    [map, season], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const table = useReactTable({
    data, columns, state: { sorting }, onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), sortDescFirst: true,
  });
  const loading = !R || !G || !teams;
  const histIdx = R && asof ? dateIndex(R.dates, asof) : -1;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Rankings</h1>
          <p className="mt-1 text-muted">
            Adjusted efficiency (points per 100 possessions vs an average D-I team). {seasonLabel(season || 2026)} · as of {asof ? prettyDate(asof) : "…"}
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
            {(meta?.seasons ?? []).slice().reverse().map((s) => (
              <option key={s} value={s}>{seasonLabel(s)}</option>
            ))}
          </select>
          <input
            type="date" value={asof} min={R?.dates[0]} max={lastDate} aria-label="As of date"
            onChange={(e) => setParam("asof", e.target.value && e.target.value !== lastDate ? e.target.value : null)}
          />
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
      </p>
    </div>
  );
}
