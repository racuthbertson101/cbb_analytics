"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { loadJson } from "@/lib/data";

type Idx = { season: number; teams: [string, string, string, string][]; players: [string, string, string, string][] };
type Hit = { kind: "team" | "player"; id: string; label: string; sub: string };

export default function SearchPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState<Idx | null>(null);
  const [sel, setSel] = useState(0);
  const router = useRouter();
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (open) { loadJson<Idx>("search.json").then(setIdx).catch(() => setIdx(null)); setTimeout(() => ref.current?.focus(), 30); }
    else { setQ(""); setSel(0); }
  }, [open]);

  const teamAbbr = useMemo(() => new Map((idx?.teams ?? []).map((t) => [t[0], t[2]])), [idx]);
  const hits: Hit[] = useMemo(() => {
    if (!idx) return [];
    const s = q.trim().toLowerCase();
    if (!s) return idx.teams.slice(0, 8).map((t) => ({ kind: "team" as const, id: t[0], label: t[1], sub: t[3] }));
    const th = idx.teams.filter((t) => t[1].toLowerCase().includes(s) || t[2].toLowerCase() === s).slice(0, 6).map((t) => ({ kind: "team" as const, id: t[0], label: t[1], sub: t[3].replace(" Conference", "") }));
    const ph = idx.players.filter((p) => p[1].toLowerCase().includes(s)).slice(0, 8).map((p) => ({ kind: "player" as const, id: p[0], label: p[1], sub: `${teamAbbr.get(p[2]) ?? ""} · ${p[3] ?? ""}` }));
    return [...th, ...ph];
  }, [q, idx, teamAbbr]);

  const go = (h: Hit) => {
    setOpen(false);
    router.push(h.kind === "team" ? `/team/${h.id}/` : `/player/?id=${h.id}&season=${idx?.season}`);
  };
  return (
    <>
      <button onClick={() => setOpen(true)} className="chip hover:text-ink" aria-label="Search">Search <kbd className="ml-1 rounded border border-line px-1 text-[10px]">Ctrl K</kbd></button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[14vh] backdrop-blur-sm" onClick={() => setOpen(false)}>
          <div className="w-[560px] overflow-hidden rounded-xl border border-line bg-surface shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <input ref={ref} value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} placeholder="Search teams and players…" className="w-full !rounded-none !border-0 !border-b !border-line !bg-transparent px-4 py-3.5 text-[15px]"
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(hits.length - 1, s + 1)); }
                if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
                if (e.key === "Enter" && hits[sel]) go(hits[sel]);
              }} />
            <div className="max-h-[50vh] overflow-auto p-1.5">
              {!idx ? <div className="p-4 text-sm text-muted">Loading index…</div> : hits.length === 0 ? <div className="p-4 text-sm text-muted">No matches for “{q}”.</div> : hits.map((h, i) => (
                <button key={h.kind + h.id} onClick={() => go(h)} onMouseEnter={() => setSel(i)} className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${i === sel ? "bg-surface2" : ""}`}>
                  <span>{h.label}</span><span className="flex items-center gap-2 text-xs text-muted"><span>{h.sub}</span><span className="chip !py-0">{h.kind}</span></span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
