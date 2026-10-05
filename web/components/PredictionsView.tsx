"use client";
import Link from "next/link";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { useJson, useMeta, useTeams } from "@/lib/data";
import { seasonRange } from "@/lib/format";
import { fmt, pct, prettyDate, signed } from "@/lib/util";
import TeamLogo from "./TeamLogo";
import SeasonChip from "./SeasonChip";

type M = { n: number; log_loss: number; brier: number; accuracy: number; mae?: number; rmse?: number };
type Rel = { bin: number; mean_pred: number; obs: number; n: number }[];
type Bucket = { bucket: string; n: number; mean_conf: number; accuracy: number }[];
type Live = { n_logged: number; n_resolved: number; verified: boolean; message?: string; first_logged?: string; last_logged?: string; metrics?: M; reliability?: Rel; buckets?: Bucket; ece?: number };
type BT = { per_season: Record<string, M>; reliability_last3: Rel; ece_last3: number; buckets_last3: Bucket; last3_seasons: number[] };
type Recent = { rows: { d: string; a: string; h: string; pm: number; p: number; m: number; n: boolean }[] };

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-4"><div className="text-xs uppercase tracking-wider text-muted">{label}</div><div className="num mt-1 text-3xl font-semibold">{value}</div>{sub && <div className="text-xs text-muted">{sub}</div>}</div>
  );
}

function Calibration({ rel, title }: { rel: Rel; title: string }) {
  return (
    <div className="card p-4">
      <h3 className="mb-1 text-sm font-medium uppercase tracking-wider text-muted">{title}</h3>
      <div className="h-72">
        <ResponsiveContainer>
          <ScatterChart margin={{ left: 0, right: 12, top: 8, bottom: 8 }}>
            <CartesianGrid stroke="#232c3b" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="mean_pred" domain={[0, 1]} tick={{ fill: "#8b96aa", fontSize: 11 }} name="Predicted" stroke="#232c3b" tickFormatter={(v) => `${Math.round(v * 100)}%`} />
            <YAxis type="number" dataKey="obs" domain={[0, 1]} tick={{ fill: "#8b96aa", fontSize: 11 }} name="Observed" stroke="#232c3b" width={40} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#5b667a" strokeDasharray="4 4" />
            <Tooltip contentStyle={{ background: "#10151d", border: "1px solid #232c3b", borderRadius: 8 }} formatter={(v) => (typeof v === "number" ? v.toFixed(3) : String(v))} />
            <Scatter data={rel} fill="#f2b544" line={{ stroke: "#f2b544" }} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-faint">Dashed line = perfect calibration: a stated 70% should win about 70% of the time.</p>
    </div>
  );
}

function Buckets({ b }: { b: Bucket }) {
  return (
    <div className="card overflow-hidden p-2">
      <table className="dense"><thead><tr><th className="l">Confidence</th><th>Games</th><th>Avg stated</th><th>Actually won</th></tr></thead>
        <tbody>{b.map((r) => <tr key={r.bucket}><td className="l">{r.bucket}</td><td>{r.n.toLocaleString()}</td><td>{pct(r.mean_conf, 1)}</td><td>{pct(r.accuracy, 1)}</td></tr>)}</tbody></table>
    </div>
  );
}

export default function PredictionsView() {
  const { map } = useTeams();
  const live = useJson<Live>("accuracy/live.json").data;
  const bt = useJson<BT>("accuracy/backtest.json").data;
  const meta = useMeta();
  const btSeasons = bt ? Object.keys(bt.per_season).map(Number).sort((a, b) => a - b) : [];
  const recent = useJson<Recent>("accuracy/recent.json").data;
  const all = useJson<{ systems: Record<string, M>; ece: number }>("params/backtest.json").data;
  const cal = all?.systems["adjeff (calibrated)"];
  return (
    <div>
      <h1 className="text-3xl font-semibold">Predictions &amp; accuracy<SeasonChip season={meta?.current_season} /></h1>
      <p className="mb-6 mt-1 max-w-3xl text-muted">Every prediction is logged before the game starts in an append-only, hash-chained log and never edited. The first logged prediction for a game is the one that is scored.</p>

      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold">Live scoreboard</h2>
        {!live ? <div className="skeleton h-28" /> : live.n_logged === 0 ? (
          <div className="card p-6 text-muted">{live.message} Until then, the walk-forward backtest below shows how the same model would have done.</div>
        ) : (
          <>
            <div className="mb-4 grid grid-cols-5 gap-4">
              <Stat label="Predictions logged" value={live.n_logged.toLocaleString()} sub={`${live.n_resolved} resolved`} />
              <Stat label="Accuracy" value={live.metrics ? pct(live.metrics.accuracy, 1) : "–"} />
              <Stat label="Log loss" value={live.metrics ? fmt(live.metrics.log_loss, 4) : "–"} />
              <Stat label="MAE (margin)" value={live.metrics?.mae ? fmt(live.metrics.mae, 2) : "–"} />
              <Stat label="Log integrity" value={live.verified ? "Verified" : "BROKEN"} sub="hash chain check" />
            </div>
            {live.reliability && live.buckets && <div className="grid grid-cols-2 gap-4"><Calibration rel={live.reliability} title="Live calibration" /><Buckets b={live.buckets} /></div>}
          </>
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-1 text-xl font-semibold">Walk-forward backtest{btSeasons.length ? ` (${seasonRange(btSeasons[0], btSeasons[btSeasons.length - 1])})` : ""}</h2>
        <p className="mb-3 text-sm text-muted">Each game predicted from ratings using only earlier games; parameters chosen on earlier seasons only. See Methodology for the baselines.</p>
        <div className="mb-4 grid grid-cols-4 gap-4">
          <Stat label="Win/loss accuracy" value={cal ? pct(cal.accuracy, 1) : "–"} sub={cal ? `${cal.n.toLocaleString()} games` : ""} />
          <Stat label="Log loss" value={cal ? fmt(cal.log_loss, 4) : "–"} sub="home-wins baseline 0.654" />
          <Stat label="Margin MAE" value={cal ? fmt(cal.mae, 2) : "–"} sub="points" />
          <Stat label="Calibration error" value={all ? fmt(all.ece, 4) : "–"} sub="expected, 10 bins" />
        </div>
        {bt && (
          <div className="mb-4 grid grid-cols-2 gap-4">
            <Calibration rel={bt.reliability_last3} title={`Calibration, ${seasonRange(bt.last3_seasons[0], bt.last3_seasons[1])}`} />
            <div>
              <Buckets b={bt.buckets_last3} />
              <div className="card mt-4 max-h-64 overflow-auto p-2">
                <table className="dense"><thead><tr><th className="l">Season</th><th>Games</th><th>Acc</th><th>Log loss</th><th>MAE</th></tr></thead>
                  <tbody>{Object.entries(bt.per_season).reverse().map(([s, m]) => <tr key={s}><td className="l">{s}</td><td>{m.n}</td><td>{pct(m.accuracy, 1)}</td><td>{fmt(m.log_loss, 4)}</td><td>{fmt(m.mae, 2)}</td></tr>)}</tbody></table>
              </div>
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-xl font-semibold">Recent games (last completed regular-season days, pregame predictions)</h2>
        <div className="card overflow-auto p-2">
          <table className="dense"><thead><tr><th className="l">Date</th><th className="l">Matchup</th><th>Home win %</th><th>Pred margin</th><th>Actual</th><th>Pick</th></tr></thead>
            <tbody>{(recent?.rows ?? []).map((r, i) => {
              const ok = (r.p > 0.5) === (r.m > 0);
              return (
                <tr key={i}><td className="l text-muted">{prettyDate(r.d)}</td>
                  <td className="l"><span className="inline-flex items-center gap-2"><TeamLogo team={map.get(r.a)} size={18} />{map.get(r.a)?.short}<span className="text-faint">@</span><TeamLogo team={map.get(r.h)} size={18} />{map.get(r.h)?.short}</span></td>
                  <td>{pct(r.p)}</td><td>{signed(r.pm, 1)}</td><td>{signed(r.m, 0)}</td><td className={ok ? "text-accent2" : "text-[var(--bad)]"}>{ok ? "✓" : "✗"}</td></tr>
              );
            })}</tbody></table>
        </div>
        <p className="mt-3 text-xs text-faint">Home/away here follows the data source (neutral-site games list one team as home). <Link className="text-accent underline" href="/methodology/">Methodology</Link></p>
      </section>
    </div>
  );
}
