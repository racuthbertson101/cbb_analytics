"use client";
import { heat } from "@/lib/util";

export type Bins = [number, number, number, number][]; // bx, by, attempts, makes
const BIN = 3, X0 = -25, Y0 = -6;

/** Half-court shot chart: circle size = attempts, color = FG% versus the league in that cell (shrunk toward the league for small samples). */
export default function ShotChart({ bins, league, title, baseline = "league" }: { bins: Bins; league: Bins; title?: string; baseline?: string }) {
  const lg = new Map(league.map(([x, y, a, m]) => [`${x},${y}`, m / Math.max(1, a)]));
  const maxA = Math.max(1, ...bins.map((b) => b[2]));
  const tot = bins.reduce((s, b) => s + b[2], 0), mk = bins.reduce((s, b) => s + b[3], 0);
  const rim = { three: 0, threeM: 0, close: 0, closeM: 0, mid: 0, midM: 0 };
  bins.forEach(([bx, by, a, m]) => {
    const lat = X0 + (bx + 0.5) * BIN, d = Y0 + (by + 0.5) * BIN, r = Math.hypot(lat, d);
    if (r >= 22.2) { rim.three += a; rim.threeM += m; } else if (r <= 6) { rim.close += a; rim.closeM += m; } else { rim.mid += a; rim.midM += m; }
  });
  const fg = (m: number, a: number) => (a ? `${((100 * m) / a).toFixed(0)}% (${a})` : "–");
  // court is drawn with the hoop at the bottom: svg y = depth flipped
  const sx = (lat: number) => lat, sy = (depth: number) => 35 - depth;
  const arcY = Math.sqrt(22.146 ** 2 - 21.75 ** 2);
  return (
    <div>
      {title && <div className="mb-1 text-xs uppercase tracking-wider text-muted">{title}</div>}
      <svg viewBox="-26 -1 52 42" className="w-full max-w-[420px]" role="img" aria-label="Shot chart">
        <rect x="-25" y="0" width="50" height="41" fill="#0d1219" stroke="#232c3b" strokeWidth="0.3" />
        <g fill="none" stroke="#3a4558" strokeWidth="0.25">
          <rect x={-8} y={sy(13.75)} width={16} height={13.75 + 5.25} />
          <circle cx={0} cy={sy(13.75)} r={6} />
          <path d={`M ${-21.75} ${sy(-5.25)} L ${-21.75} ${sy(arcY)} A 22.146 22.146 0 0 1 21.75 ${sy(arcY)} L 21.75 ${sy(-5.25)}`} />
          <path d={`M -4 ${sy(0)} A 4 4 0 0 1 4 ${sy(0)}`} />
          <line x1={-3} x2={3} y1={sy(-1.25)} y2={sy(-1.25)} />
          <circle cx={0} cy={sy(0)} r={0.75} stroke="#f2b544" />
        </g>
        {bins.map(([bx, by, a, m]) => {
          const cx = sx(X0 + (bx + 0.5) * BIN), cy = sy(Y0 + (by + 0.5) * BIN);
          const l = lg.get(`${bx},${by}`) ?? 0.4;
          const est = (m + 8 * l) / (a + 8);
          const t = 0.5 + Math.max(-1, Math.min(1, (est - l) / 0.14)) * 0.5;
          return <circle key={`${bx},${by}`} cx={cx} cy={cy} r={0.35 + 1.15 * Math.sqrt(a / maxA)} fill={heat(t)} stroke="rgba(255,255,255,0.25)" strokeWidth="0.1" opacity="0.95"><title>{`${a} shots, ${(100 * m / a).toFixed(0)}% (league ${(100 * l).toFixed(0)}%)`}</title></circle>;
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span>FG <b className="num text-ink">{fg(mk, tot)}</b></span>
        <span>Near rim <b className="num text-ink">{fg(rim.closeM, rim.close)}</b></span>
        <span>Mid-range <b className="num text-ink">{fg(rim.midM, rim.mid)}</b></span>
        <span>Three <b className="num text-ink">{fg(rim.threeM, rim.three)}</b></span>
      </div>
      <p className="mt-1 text-[11px] text-faint">Circle size = attempts; teal = above {baseline} FG% in that cell, orange = below. Free throws excluded.</p>
    </div>
  );
}
