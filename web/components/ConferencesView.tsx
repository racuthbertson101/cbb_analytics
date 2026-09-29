"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable } from "@tanstack/react-table";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { loadJson, useJson, useMeta, useTeams } from "@/lib/data";
import { fmt, heat, percentiles, seasonLabel, signed } from "@/lib/util";
import { shortConf } from "./RankingsView";
import TeamLogo from "./TeamLogo";

export type ConfRow = {
  id: string; name: string; n: number; em: number; off: number; def: number; tempo: number; top_em: number; median_em: number; top4_em: number;
  nc_w: number; nc_l: number; nc_exp_w: number; nc_over: number | null; teams: string[]; rank: number;
};
type Row = ConfRow & { heat: Record<string, number | null> };
const COLORS = ["#f2b544", "#4cc9c0", "#e5754f", "#8b96aa", "#b58cf2", "#6fa8ff", "#f27ca8", "#9be564"];

export default function ConferencesView() {
  const meta = useMeta();
  const sp = useSearchParams();
  const router = useRouter();
  const { map } = useTeams();
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const { data } = useJson<{ rows: ConfRow[] }>(season ? `conferences/${season}.json` : null);
  const { data: tb } = useJson<{ rows: { id: string; status: string }[] }>("tiebreakers.json");
  const known = useMemo(() => new Set((tb?.rows ?? []).map((r) => r.id)), [tb]);
  const [sorting, setSorting] = useState<SortingState>([{ id: "em", desc: true }]);
  const [hist, setHist] = useState<{ season: number; [k: string]: number | null }[]>([]);

  useEffect(() => {
    if (!meta) return;
    Promise.all(meta.seasons.map((s) => loadJson<{ rows: ConfRow[] }>(`conferences/${s}.json`).then((d) => ({ s, d })))).then((all) =>
      setHist(all.map(({ s, d }) => ({ season: s, ...Object.fromEntries(d.rows.map((r) => [r.id, r.em])) }))),
    );
  }, [meta]);

  const rows: Row[] = useMemo(() => {
    const r = data?.rows ?? [];
    const ps = {
      em: percentiles(r.map((x) => x.em)), off: percentiles(r.map((x) => x.off)), def: percentiles(r.map((x) => x.def), false),
      top4: percentiles(r.map((x) => x.top4_em)), over: percentiles(r.map((x) => x.nc_over)),
    };
    return r.map((x, i) => ({ ...x, heat: { em: ps.em[i], off: ps.off[i], def: ps.def[i], top4: ps.top4[i], over: ps.over[i] } }));
  }, [data]);

  const cell = (d: number, hk: string, sign = false) => {
    const C = ({ getValue, row }: { getValue: () => unknown; row: { original: Row } }) => (
      <span className="block rounded px-1.5 py-[1px]" style={{ background: heat(row.original.heat[hk]) }}>
        {sign ? signed(getValue() as number, d) : fmt(getValue() as number, d)}
      </span>
    );
    return C;
  };
  const columns = useMemo<ColumnDef<Row>[]>(
    () => [
      { id: "rank", header: "#", accessorFn: (r) => r.rank, cell: ({ getValue }) => <span className="text-muted">{getValue() as number}</span> },
      {
        id: "name", header: "Conference", meta: "l", accessorFn: (r) => r.name,
        cell: ({ row }) => known.has(row.original.id)
          ? <Link className="font-medium hover:text-accent" href={`/conference/${row.original.id}/?season=${season}`}>{shortConf(row.original.name)}</Link>
          : <span className="font-medium">{shortConf(row.original.name)}</span>,
      },
      { id: "top", header: "Best teams", meta: "l", enableSorting: false, accessorFn: (r) => r.teams, cell: ({ getValue }) => <span className="flex gap-1">{(getValue() as string[]).map((t) => <TeamLogo key={t} team={map.get(t)} size={20} />)}</span> },
      { id: "n", header: "Teams", accessorFn: (r) => r.n },
      { id: "em", header: "Avg AdjEM", accessorFn: (r) => r.em, cell: cell(1, "em", true) },
      { id: "off", header: "AdjO", accessorFn: (r) => r.off, cell: cell(1, "off") },
      { id: "def", header: "AdjD", accessorFn: (r) => r.def, sortDescFirst: false, cell: cell(1, "def") },
      { id: "tempo", header: "Tempo", accessorFn: (r) => r.tempo, cell: ({ getValue }) => fmt(getValue() as number, 1) },
      { id: "top4", header: "Top-4 AdjEM", accessorFn: (r) => r.top4_em, cell: cell(1, "top4", true) },
      { id: "nc", header: "Non-conf W-L", accessorFn: (r) => r.nc_w / Math.max(1, r.nc_w + r.nc_l), cell: ({ row }) => `${row.original.nc_w}-${row.original.nc_l}` },
      { id: "over", header: "NC wins vs exp", accessorFn: (r) => r.nc_over, cell: cell(1, "over", true) },
    ],
    [map, season, known], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const table = useReactTable({ data: rows, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), sortDescFirst: true });

  const top = useMemo(() => [...(data?.rows ?? [])].sort((a, b) => b.em - a.em).slice(0, 8), [data]);
  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Conferences</h1>
          <p className="mt-1 text-muted">Conference strength from members&apos; adjusted efficiency, and how each league did against the others. Membership is as of each season.</p>
        </div>
        <select value={season} onChange={(e) => router.replace(`?season=${e.target.value}`, { scroll: false })}>
          {(meta?.seasons ?? []).slice().reverse().map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
        </select>
      </div>
      <div className="card mb-6 overflow-hidden">
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
            {!data
              ? Array.from({ length: 12 }).map((_, i) => <tr key={i}><td colSpan={11}><div className="skeleton h-5" /></td></tr>)
              : table.getRowModel().rows.map((r) => (
                <tr key={r.id}>
                  {r.getVisibleCells().map((c) => (
                    <td key={c.id} className={(c.column.columnDef.meta as string) === "l" ? "l" : ""}>{flexRender(c.column.columnDef.cell, c.getContext())}</td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <div className="card p-4">
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">Average AdjEM by season (top conferences of {seasonLabel(season || 2026)})</h2>
        <div className="h-72">
          <ResponsiveContainer>
            <LineChart data={hist} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
              <CartesianGrid stroke="#232c3b" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="season" tick={{ fill: "#8b96aa", fontSize: 11 }} stroke="#232c3b" />
              <YAxis tick={{ fill: "#8b96aa", fontSize: 11 }} stroke="#232c3b" width={36} />
              <Tooltip contentStyle={{ background: "#10151d", border: "1px solid #232c3b", borderRadius: 8 }} formatter={(v) => (typeof v === "number" ? v.toFixed(1) : String(v))} />
              <Legend />
              {top.map((c, i) => <Line key={c.id} dataKey={c.id} name={shortConf(c.name)} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} connectNulls />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
