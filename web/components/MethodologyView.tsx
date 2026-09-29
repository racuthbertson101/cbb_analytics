"use client";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { useJson } from "@/lib/data";

type Sys = { mae?: number; rmse?: number; log_loss: number; brier: number; accuracy: number; n: number };
type BT = {
  test_seasons: number[]; systems: Record<string, Sys>; calibration_chosen: string; calibration_candidates_ll: Record<string, number>;
  sigma_uses_tempo: boolean; sigma_const_ll: number; sigma_tempo_ll: number; ece: number; ece_uncalibrated: number; bias_margin: number;
  reliability: { bin: number; mean_pred: number; obs: number; n: number }[]; buckets: { bucket: string; n: number; mean_conf: number; accuracy: number }[];
  by_season: Record<string, { adjeff: Sys; home: Sys; elo: Sys; prev: Sys }>; seasons_beating_home: number; ncaa_tournament: Sys;
};
type Prod = { config: Record<string, number | null>; sigma_coef: number[]; prior_coefs_current: Record<string, number[]>; margin_residual_quantiles: Record<string, number> };
type Poss = { fta_coef: number; rmse_at_fit: number; n_team_games: number };

const f = (x: number | undefined, d = 3) => (x == null ? "–" : x.toFixed(d));

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card mb-6 p-6">
      <h2 className="mb-3 text-xl font-semibold">{title}</h2>
      <div className="space-y-3 text-[14px] leading-relaxed text-muted">{children}</div>
    </section>
  );
}

export default function MethodologyView() {
  const bt = useJson<BT>("params/backtest.json").data;
  const prod = useJson<Prod>("params/adjeff.json").data;
  const poss = useJson<Poss>("params/possessions.json").data;
  return (
    <div className="mx-auto max-w-[1100px]">
      <h1 className="mb-2 text-3xl font-semibold">Methodology</h1>
      <p className="mb-6 text-muted">Every fitted number on this page is generated from the pipeline&apos;s parameter files, so it cannot go stale. Definitions and judgment calls are labeled as such.</p>

      <Section title="Data">
        <p>Game, team box score, player box score and standings data come from the open sportsdataverse / hoopR release files of ESPN men&apos;s college basketball data, refreshed from ESPN&apos;s public JSON endpoints. Seasons 2008 to present are used for ratings: from 2008 at least 98% of games have team and player box scores and a neutral-site flag. Seasons are named by the year they end (2026 = 2025-26). Only Division I vs Division I games enter rating fits; other games appear on schedules.</p>
      </Section>

      <Section title="Adjusted efficiency (the main rating)">
        <p>For each team in each game the response is points per 100 possessions. Predictors are offense dummies for the team, defense dummies for the opponent, and a site term (home +1, neutral 0, away -1), fit by ridge regression toward a preseason prior. Ratings before a game use only games strictly before that date. Adjusted offense = league mean + offense effect; adjusted defense = league mean + defense effect (lower is better); AdjEM = offense minus defense. Tempo is a second ridge model of possessions per game (team effect for each side).</p>
        {prod && (
          <table className="dense">
            <thead><tr><th className="l">Parameter</th><th>Value</th><th className="l">How it was chosen</th></tr></thead>
            <tbody>
              <tr><td className="l">Ridge strength (efficiency)</td><td>{prod.config.lam}</td><td className="l">walk-forward grid search on prior seasons</td></tr>
              <tr><td className="l">Recency half-life (days)</td><td>{prod.config.halflife ?? "none"}</td><td className="l">grid included 300 days and none; validation preferred no decay</td></tr>
              <tr><td className="l">Blowout cap (pts/100 poss)</td><td>{prod.config.cap ?? "none"}</td><td className="l">grid: none, 60, 45</td></tr>
              <tr><td className="l">Team-specific home court</td><td>rejected</td><td className="l">shrunken team effects hurt out-of-sample error in every grid setting</td></tr>
              <tr><td className="l">Ridge strength (tempo)</td><td>{prod.config.lam_t}</td><td className="l">walk-forward grid on possession error</td></tr>
              <tr><td className="l">Tempo half-life (days)</td><td>{prod.config.halflife_t}</td><td className="l">walk-forward grid</td></tr>
              <tr><td className="l">Preseason prior: offense coefs (last, two ago)</td><td>{prod.prior_coefs_current.o.map((x) => x.toFixed(3)).join(", ")}</td><td className="l">regression of final ratings on the prior two seasons&apos; finals</td></tr>
              <tr><td className="l">Preseason prior: defense coefs</td><td>{prod.prior_coefs_current.d.map((x) => x.toFixed(3)).join(", ")}</td><td className="l">same</td></tr>
              <tr><td className="l">Preseason prior: tempo coefs</td><td>{prod.prior_coefs_current.t.map((x) => x.toFixed(3)).join(", ")}</td><td className="l">same</td></tr>
              <tr><td className="l">Margin spread σ (base, per possession above 68)</td><td>{prod.sigma_coef[0].toFixed(2)}, {prod.sigma_coef[1].toFixed(3)}</td><td className="l">mean absolute historical residual, linear in predicted tempo</td></tr>
              <tr><td className="l">FTA weight in possession estimate</td><td>{poss ? poss.fta_coef.toFixed(3) : "–"}</td><td className="l">value that makes both teams&apos; possession estimates agree ({poss?.n_team_games.toLocaleString()} team-games)</td></tr>
            </tbody>
          </table>
        )}
        <p>Predicted score = predicted possessions × predicted efficiency for each side. Win probability = normal CDF of predicted margin over σ, then calibrated (see below). Intervals come from historical residual quantiles (80% margin interval: {prod ? `${prod.margin_residual_quantiles["0.1"].toFixed(1)} to +${prod.margin_residual_quantiles["0.9"].toFixed(1)}` : "…"} points around the prediction).</p>
      </Section>

      <Section title="Backtest (walk-forward, no leakage)">
        <p>For every game in {bt ? `${bt.test_seasons[0]}-${bt.test_seasons[1]}` : "…"} the model is refit each game day on earlier games only. Hyperparameters for season S are chosen using seasons before S; the spread model and calibrator for S are fit on predictions from seasons before S. A test in the repository proves that changing the results of a game (or of any game on the same day or later) does not change earlier predictions.</p>
        {bt ? (
          <>
            <table className="dense">
              <thead><tr><th className="l">System</th><th>MAE</th><th>RMSE</th><th>Log loss</th><th>Brier</th><th>Accuracy</th></tr></thead>
              <tbody>
                {Object.entries(bt.systems).map(([k, v]) => (
                  <tr key={k}><td className="l">{k}</td><td>{f(v.mae, 2)}</td><td>{f(v.rmse, 2)}</td><td>{f(v.log_loss, 4)}</td><td>{f(v.brier, 4)}</td><td>{f(v.accuracy, 3)}</td></tr>
                ))}
              </tbody>
            </table>
            <p>The model beat the home-team-wins baseline in {bt.seasons_beating_home} of {Object.keys(bt.by_season).length} test seasons. Bias (predicted minus actual margin): {bt.bias_margin.toFixed(3)} points. Calibration method chosen by walk-forward log loss: <b className="text-ink">{bt.calibration_chosen}</b> ({Object.entries(bt.calibration_candidates_ll).map(([k, v]) => `${k} ${v.toFixed(4)}`).join(", ")}). Expected calibration error {bt.ece.toFixed(4)}. Tempo-dependent spread {bt.sigma_uses_tempo ? "improved" : "did not improve"} log loss ({bt.sigma_tempo_ll.toFixed(4)} vs {bt.sigma_const_ll.toFixed(4)} constant).</p>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <h3 className="mb-1 text-sm font-medium text-ink">Reliability curve</h3>
                <div className="h-72">
                  <ResponsiveContainer>
                    <ScatterChart margin={{ left: 0, right: 12, top: 8, bottom: 8 }}>
                      <CartesianGrid stroke="#232c3b" strokeDasharray="3 3" />
                      <XAxis type="number" dataKey="mean_pred" domain={[0, 1]} tick={{ fill: "#8b96aa", fontSize: 11 }} name="Predicted" stroke="#232c3b" />
                      <YAxis type="number" dataKey="obs" domain={[0, 1]} tick={{ fill: "#8b96aa", fontSize: 11 }} name="Observed" stroke="#232c3b" width={32} />
                      <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#5b667a" strokeDasharray="4 4" />
                      <Tooltip contentStyle={{ background: "#10151d", border: "1px solid #232c3b", borderRadius: 8 }} formatter={(v) => (typeof v === "number" ? v.toFixed(3) : String(v))} />
                      <Scatter data={bt.reliability} fill="#f2b544" line={{ stroke: "#f2b544" }} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div>
                <h3 className="mb-1 text-sm font-medium text-ink">Accuracy by confidence bucket</h3>
                <table className="dense">
                  <thead><tr><th className="l">Bucket</th><th>Games</th><th>Mean confidence</th><th>Accuracy</th></tr></thead>
                  <tbody>{bt.buckets.map((b) => <tr key={b.bucket}><td className="l">{b.bucket}</td><td>{b.n.toLocaleString()}</td><td>{(b.mean_conf * 100).toFixed(1)}%</td><td>{(b.accuracy * 100).toFixed(1)}%</td></tr>)}</tbody>
                </table>
              </div>
            </div>
            <h3 className="mt-2 text-sm font-medium text-ink">By season</h3>
            <div className="h-56">
              <ResponsiveContainer>
                <LineChart data={Object.entries(bt.by_season).map(([s, v]) => ({ s, adjeff: v.adjeff.log_loss, elo: v.elo.log_loss, prev: v.prev.log_loss, home: v.home.log_loss }))} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
                  <CartesianGrid stroke="#232c3b" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="s" tick={{ fill: "#8b96aa", fontSize: 11 }} stroke="#232c3b" />
                  <YAxis domain={[0.45, 0.72]} tick={{ fill: "#8b96aa", fontSize: 11 }} stroke="#232c3b" width={36} />
                  <Tooltip contentStyle={{ background: "#10151d", border: "1px solid #232c3b", borderRadius: 8 }} formatter={(v) => (typeof v === "number" ? v.toFixed(4) : String(v))} />
                  <Line dataKey="adjeff" name="Adjusted efficiency" stroke="#f2b544" strokeWidth={2} dot={false} />
                  <Line dataKey="elo" name="Simple Elo" stroke="#4cc9c0" strokeWidth={1.4} dot={false} />
                  <Line dataKey="prev" name="Prev-season rating" stroke="#8b96aa" strokeWidth={1.4} dot={false} />
                  <Line dataKey="home" name="Home wins" stroke="#e5754f" strokeWidth={1.4} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs">Log loss per test season (lower is better).</p>
          </>
        ) : <div className="skeleton h-40" />}
      </Section>

      <Section title="Definitions (not fitted)">
        <ul className="list-disc space-y-1 pl-5">
          <li>Season = year the season ends. Division I membership for a season = teams listed in a D-I conference in that season&apos;s standings.</li>
          <li>Game type is derived from ESPN season type and event headline. Conference tournament games with no headline on a non-neutral site are labeled regular season (a known limitation).</li>
          <li>Possessions = FGA - OREB + TO + c · FTA, averaged over the two teams, with c fitted (above).</li>
          <li>SOS = mean AdjEM of D-I opponents faced. Luck = actual wins minus the sum of pregame win probabilities in D-I games.</li>
          <li>Heat colors show percentile among D-I teams (teal = better, orange = worse).</li>
        </ul>
      </Section>

      <Section title="Judgment calls">
        <ul className="list-disc space-y-1 pl-5">
          <li>Seasons before 2008 are excluded from fits for coverage reasons; 2021 (COVID) is kept but was irregular.</li>
          <li>Top matchups on the Today page are ordered by the average AdjEM of the two teams; a fuller watchability score arrives later with its own labeled weights.</li>
          <li>Numerical stabilizer: a penalty equal to one game-row on the league mean, home court and mean tempo keeps them defined before any games are played.</li>
        </ul>
      </Section>
      <p className="text-xs text-faint">Credits: ESPN (game data, team names and logos), the sportsdataverse / hoopR project (bulk data releases).</p>
    </div>
  );
}
