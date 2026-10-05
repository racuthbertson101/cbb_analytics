/**
 * Mirrored comparison bar: team A's value grows left from the center, team B's grows right, scaled to the larger value.
 * Optional ticks mark each team's season average. `better` says which direction is good (for color only).
 */
export default function MatchupBar({ label, a, b, fmt, ca, cb, tickA, tickB, better = "high" }: {
  label: string; a: number | null; b: number | null; fmt: (x: number | null) => string;
  ca?: string; cb?: string; tickA?: number | null; tickB?: number | null; better?: "high" | "low" | "none";
}) {
  const vals = [a, b, tickA, tickB].filter((x): x is number => x != null && Number.isFinite(x)).map(Math.abs);
  const max = Math.max(...vals, 1e-9);
  const w = (x: number | null | undefined) => (x == null ? 0 : (Math.abs(x) / max) * 100);
  const winA = a != null && b != null && better !== "none" && (better === "high" ? a > b : a < b);
  const winB = a != null && b != null && better !== "none" && (better === "high" ? b > a : b < a);
  return (
    <div className="grid grid-cols-[4.5rem_1fr_9rem_1fr_4.5rem] items-center gap-2 py-1 text-[13px]">
      <span className={`num text-right ${winA ? "font-semibold text-ink" : "text-muted"}`}>{fmt(a)}</span>
      <div className="relative h-2 rounded-l-full bg-surface2">
        <div className="absolute inset-y-0 right-0 rounded-l-full" style={{ width: `${w(a)}%`, background: ca ?? "var(--accent)", opacity: winA ? 0.95 : 0.55 }} />
        {tickA != null && <div className="absolute -inset-y-1 w-0.5 bg-ink/80" style={{ right: `${w(tickA)}%` }} title={`Season average ${fmt(tickA)}`} />}
      </div>
      <span className="text-center text-xs text-muted">{label}</span>
      <div className="relative h-2 rounded-r-full bg-surface2">
        <div className="absolute inset-y-0 left-0 rounded-r-full" style={{ width: `${w(b)}%`, background: cb ?? "var(--accent-2)", opacity: winB ? 0.95 : 0.55 }} />
        {tickB != null && <div className="absolute -inset-y-1 w-0.5 bg-ink/80" style={{ left: `${w(tickB)}%` }} title={`Season average ${fmt(tickB)}`} />}
      </div>
      <span className={`num ${winB ? "font-semibold text-ink" : "text-muted"}`}>{fmt(b)}</span>
    </div>
  );
}
