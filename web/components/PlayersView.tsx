"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable } from "@tanstack/react-table";
import { useMeta, useTeams } from "@/lib/data";
import { P, usePlayers } from "@/lib/players";
import { fmt, heat, seasonLabel, signed } from "@/lib/util";
import TeamLogo from "./TeamLogo";
import SeasonChip from "./ui/SeasonChip";

const POS = ["All", "G", "F", "C"];
const posGroup = (p: unknown) => {
  const s = String(p ?? "");
  return s.includes("C") ? "C" : s.includes("F") ? "F" : s.includes("G") ? "G" : "";
};

export default function PlayersView() {
  const meta = useMeta();
  const { map } = useTeams();
  const sp = useSearchParams();
  const router = useRouter();
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const data = usePlayers(season || null);
  const [minMin, setMinMin] = useState(300);
  const [pos, setPos] = useState("All");
  const [q, setQ] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "p40", desc: true }]);

  const rows = useMemo(() => (data?.rows ?? []).filter((r) => (r.min as number) >= minMin && (pos === "All" || posGroup(r.pos) === pos) && (!q || r.name.toLowerCase().includes(q.toLowerCase()))), [data, minMin, pos, q]);

  const stat = (k: string, d: number, pc?: string, sign = false, scale = 1) => ({ row }: { row: { original: P } }) => {
    const v = row.original[k] as number | null;
    const h = pc ? (row.original[pc] as number | null) : null;
    return <span className="block rounded px-1.5 py-[1px]" style={{ background: h == null ? "transparent" : heat(h) }}>{v == null ? "–" : sign ? signed(v * scale, d) : fmt(v * scale, d)}</span>;
  };
  const columns = useMemo<ColumnDef<P>[]>(() => [
    { id: "name", header: "Player", meta: "l", accessorFn: (r) => r.name, cell: ({ row }) => (
      <span className="flex items-center gap-2">
        <TeamLogo team={map.get(row.original.tid)} size={20} />
        <Link className="font-medium hover:text-accent" href={`/player/?id=${row.original.id}&season=${season}`}>{row.original.name}</Link>
        <span className="text-xs text-faint">{map.get(row.original.tid)?.abbr}</span>
      </span>) },
    { id: "pos", header: "Pos", meta: "l", accessorFn: (r) => r.pos, cell: ({ getValue }) => <span className="text-muted">{String(getValue() ?? "")}</span> },
    { id: "gp", header: "GP", accessorFn: (r) => r.gp },
    { id: "mpg", header: "MPG", accessorFn: (r) => r.mpg, cell: stat("mpg", 1) },
    { id: "ppg", header: "PPG", accessorFn: (r) => r.ppg, cell: stat("ppg", 1) },
    { id: "p40", header: "Pts/40", accessorFn: (r) => (r.mpg ? ((r.ppg as number) / (r.mpg as number)) * 40 : null), cell: ({ getValue }) => <span className="block px-1.5">{fmt(getValue() as number | null, 1)}</span> },
    { id: "rpg", header: "RPG", accessorFn: (r) => r.rpg, cell: stat("rpg", 1) },
    { id: "apg", header: "APG", accessorFn: (r) => r.apg, cell: stat("apg", 1) },
    { id: "usg", header: "USG%", accessorFn: (r) => r.usg, cell: stat("usg", 1, "pc_usg") },
    { id: "ts", header: "TS%", accessorFn: (r) => r.ts, cell: stat("ts", 1, "pc_ts", false, 100) },
    { id: "ast_pct", header: "AST%", accessorFn: (r) => r.ast_pct, cell: stat("ast_pct", 1, "pc_ast_pct") },
    { id: "tov_pct", header: "TO%", accessorFn: (r) => r.tov_pct, cell: stat("tov_pct", 1, "pc_tov_pct") },
    { id: "orb_pct", header: "ORB%", accessorFn: (r) => r.orb_pct, cell: stat("orb_pct", 1, "pc_orb_pct") },
    { id: "drb_pct", header: "DRB%", accessorFn: (r) => r.drb_pct, cell: stat("drb_pct", 1, "pc_drb_pct") },
    { id: "stl_pct", header: "STL%", accessorFn: (r) => r.stl_pct, cell: stat("stl_pct", 1, "pc_stl_pct") },
    { id: "blk_pct", header: "BLK%", accessorFn: (r) => r.blk_pct, cell: stat("blk_pct", 1, "pc_blk_pct") },
  ], [map, season]); // eslint-disable-line react-hooks/exhaustive-deps
  const table = useReactTable({ data: rows, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), sortDescFirst: true });
  const shown = table.getRowModel().rows.slice(0, 400);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Players<SeasonChip season={season} /></h1>
          <p className="mt-1 text-muted">{seasonLabel(season || 2026)} leaderboards, sorted by points per 40 minutes. Heat = percentile among D-I players with {data?.refMin ?? 300}+ minutes.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={season} onChange={(e) => router.replace(`?season=${e.target.value}`, { scroll: false })}>
            {(meta?.seasons ?? []).slice().reverse().map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
          </select>
          <select value={pos} onChange={(e) => setPos(e.target.value)}>{POS.map((p) => <option key={p}>{p}</option>)}</select>
          <label className="flex items-center gap-1.5 text-xs text-muted">Min minutes
            <select value={minMin} onChange={(e) => setMinMin(+e.target.value)}>{[50, 150, 300, 500, 800].map((m) => <option key={m}>{m}</option>)}</select></label>
          <input placeholder="Search player" value={q} onChange={(e) => setQ(e.target.value)} className="w-44" />
        </div>
      </div>
      <div className="card overflow-hidden">
        <div className="max-h-[calc(100vh-220px)] overflow-auto">
          <table className="dense">
            <thead>{table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>{hg.headers.map((h) => (
                <th key={h.id} className={(h.column.columnDef.meta as string) === "l" ? "l" : ""} onClick={h.column.getToggleSortingHandler()}>
                  {flexRender(h.column.columnDef.header, h.getContext())}{{ asc: " ↑", desc: " ↓" }[h.column.getIsSorted() as string] ?? ""}
                </th>))}</tr>))}</thead>
            <tbody>
              {!data ? Array.from({ length: 16 }).map((_, i) => <tr key={i}><td colSpan={18}><div className="skeleton h-5" /></td></tr>)
                : shown.length === 0 ? <tr><td colSpan={18} className="py-10 text-center text-muted">No players match these filters.</td></tr>
                : shown.map((r) => (
                  <tr key={r.id}>{r.getVisibleCells().map((c) => (
                    <td key={c.id} className={(c.column.columnDef.meta as string) === "l" ? "l" : ""}>{flexRender(c.column.columnDef.cell, c.getContext())}</td>))}</tr>))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="mt-3 text-xs text-faint">Showing the top {Math.min(400, table.getRowModel().rows.length)} of {rows.length} matching players. The experimental box-score impact rating is shown only on player pages: it overrates rebounders and shot blockers, so it is not used to rank players here.</p>
    </div>
  );
}
