export default function Sparkline({ data, w = 84, h = 22, color = "var(--accent)" }: { data: number[]; w?: number; h?: number; color?: string }) {
  if (data.length < 2) return <span className="inline-block" style={{ width: w, height: h }} />;
  const min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
  const pts = data.map((v, i) => `${((i / (data.length - 1)) * (w - 2) + 1).toFixed(1)},${(h - 2 - ((v - min) / span) * (h - 4) + 1).toFixed(1)}`);
  const last = pts[pts.length - 1].split(",");
  return (
    <svg width={w} height={h} className="inline-block align-middle" aria-hidden>
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" opacity="0.9" />
      <circle cx={last[0]} cy={last[1]} r="2" fill={color} />
    </svg>
  );
}
