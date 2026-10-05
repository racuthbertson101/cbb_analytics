"use client";
import { useMemo, useRef, useState } from "react";
import { fmtPct } from "@/lib/format";

export type Detail = {
  wp: [number, number, number, number][]; runs: [number, number, "h" | "a", number][];
  lead_changes: number; ties: number; largest: { h: number; a: number }; excitement: number; excitement_pct: number;
};

const REG = 2400, HALF = 1200, OT = 300;
/** Game clock text for seconds since tip: "1st half 12:34", "2nd half 0:45", "OT 2:10". */
export function clockText(t: number) {
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  if (t <= HALF) return `1st half ${mmss(HALF - t)}`;
  if (t <= REG) return `2nd half ${mmss(REG - t)}`;
  const k = Math.ceil((t - REG) / OT);
  return `${k > 1 ? `${k}OT` : "OT"} ${mmss(REG + k * OT - t)}`;
}

/** Home win probability through the game: 50% midline, fill toward the leader's color, 8-0+ runs shaded, hover for state. */
export default function WinProbChart({ d, home, away, ch, ca }: { d: Detail; home: string; away: string; ch: string; ca: string }) {
  const W = 900, H = 260, P = { l: 44, r: 12, t: 12, b: 26 };
  const end = Math.max(REG, d.wp[d.wp.length - 1][0]);
  const X = (t: number) => P.l + (t / end) * (W - P.l - P.r);
  const Y = (p: number) => P.t + (1 - p) * (H - P.t - P.b);
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const path = useMemo(() => d.wp.map(([t, , , p], i) => `${i ? "L" : "M"}${X(t).toFixed(1)},${Y(p).toFixed(1)}`).join(""), [d]); // eslint-disable-line react-hooks/exhaustive-deps
  const area = `${path}L${X(d.wp[d.wp.length - 1][0])},${Y(0.5)}L${X(0)},${Y(0.5)}Z`;
  const ots = Array.from({ length: Math.round((end - REG) / OT) }, (_, i) => REG + (i + 1) * OT);
  const onMove = (e: React.MouseEvent) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const t = (((e.clientX - r.left) / r.width) * W - P.l) / (W - P.l - P.r) * end;
    let k = 0;
    while (k < d.wp.length - 1 && d.wp[k + 1][0] <= t) k++;
    setHover(k);
  };
  const hv = hover != null ? d.wp[hover] : null;
  return (
    <div>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="w-full" onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img"
        aria-label={`Win probability for ${home}: starts ${fmtPct(d.wp[0][3])}, ${d.lead_changes} lead changes`}>
        <defs>
          <clipPath id="wp-top"><rect x={0} y={0} width={W} height={Y(0.5)} /></clipPath>
          <clipPath id="wp-bot"><rect x={0} y={Y(0.5)} width={W} height={H} /></clipPath>
        </defs>
        {d.runs.map(([s, e, side, pts], i) => (
          <g key={i}>
            <rect x={X(s)} y={P.t} width={Math.max(X(e) - X(s), 2)} height={H - P.t - P.b} fill={side === "h" ? ch : ca} opacity={0.1} />
            <text x={X(s) + 3} y={side === "h" ? P.t + 11 : H - P.b - 4} fontSize={10} fill="var(--muted)">{side === "h" ? home : away} {pts}-0</text>
          </g>
        ))}
        {[0, 0.25, 0.75, 1].map((p) => <line key={p} x1={P.l} x2={W - P.r} y1={Y(p)} y2={Y(p)} stroke="var(--border)" strokeOpacity={0.5} />)}
        <line x1={P.l} x2={W - P.r} y1={Y(0.5)} y2={Y(0.5)} stroke="var(--muted)" strokeDasharray="4 4" />
        {[HALF, REG, ...ots].map((t) => <line key={t} x1={X(t)} x2={X(t)} y1={P.t} y2={H - P.b} stroke="var(--border)" />)}
        <path d={area} fill={ch} opacity={0.35} clipPath="url(#wp-top)" />
        <path d={area} fill={ca} opacity={0.35} clipPath="url(#wp-bot)" />
        <path d={path} fill="none" stroke="var(--text)" strokeWidth={1.6} />
        <text x={4} y={Y(1) + 4} fontSize={10} fill="var(--muted)">{home}</text>
        <text x={4} y={Y(0) + 2} fontSize={10} fill="var(--muted)">{away}</text>
        <text x={4} y={Y(0.5) + 4} fontSize={10} fill="var(--muted)">50%</text>
        {[["Tip", 0], ["Half", HALF], ["End", REG]].map(([l, t]) => <text key={String(l)} x={X(Number(t))} y={H - 8} fontSize={10} textAnchor={t === 0 ? "start" : "middle"} fill="var(--muted)">{l}</text>)}
        {hv && (
          <g>
            <line x1={X(hv[0])} x2={X(hv[0])} y1={P.t} y2={H - P.b} stroke="var(--accent)" />
            <circle cx={X(hv[0])} cy={Y(hv[3])} r={4} fill="var(--accent)" />
          </g>
        )}
      </svg>
      <div className="mt-1 h-5 text-xs text-muted">
        {hv ? <>{clockText(hv[0])} · {away} {hv[2]} – {home} {hv[1]} · {home} {fmtPct(hv[3])}</> : "Hover the chart for the score and win probability at each moment."}
      </div>
    </div>
  );
}
