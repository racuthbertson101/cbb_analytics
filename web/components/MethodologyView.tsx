"use client";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { useJson, useMeta } from "@/lib/data";
import { seasonRange } from "@/lib/format";
import SeasonChip from "./SeasonChip";

type Sys = { mae?: number; rmse?: number; log_loss: number; brier: number; accuracy: number; n: number };
type BT = {
  test_seasons: number[]; systems: Record<string, Sys>; calibration_chosen: string; calibration_candidates_ll: Record<string, number>;
  sigma_uses_tempo: boolean; sigma_const_ll: number; sigma_tempo_ll: number; ece: number; ece_uncalibrated: number; bias_margin: number;
  reliability: { bin: number; mean_pred: number; obs: number; n: number }[]; buckets: { bucket: string; n: number; mean_conf: number; accuracy: number }[];
  by_season: Record<string, { adjeff: Sys; home: Sys; elo: Sys; prev: Sys }>; seasons_beating_home: number; ncaa_tournament: Sys;
};
type Prod = { config: Record<string, number | null>; sigma_coef: number[]; prior_coefs_current: Record<string, number[]> & { roster?: Record<string, { cols: string[]; beta: number[]; window: number }> }; margin_residual_quantiles: Record<string, number> };
type PlayersP = {
  alpha: number; shrink_k_minutes: number; within_season_r2_offense: number; within_season_r2_defense: number; decision: string;
  model: { offense_coef: Record<string, number>; defense_coef: Record<string, number> };
  prior_evaluation: { rmse_o_base: number; rmse_o_full: number; rmse_d_base: number; rmse_d_full: number; seasons_o_improved: number; seasons_d_improved: number };
};
type Cons = {
  test_seasons: number[]; production: { weights: Record<string, number>; bt_margin_scale: number };
  weights_by_season: Record<string, { weights: Record<string, number> }>;
} & Record<string, { mae: number; rmse: number; log_loss?: number }>;
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
  const meta = useMeta();
  const wt = useJson<{ weights: Record<string, number>; stakes_weights: Record<string, number> }>("params/watchability.json").data;
  const bt = useJson<BT>("params/backtest.json").data;
  const prod = useJson<Prod>("params/adjeff.json").data;
  const poss = useJson<Poss>("params/possessions.json").data;
  const pl = useJson<PlayersP>("params/players.json").data;
  const cs = useJson<Cons>("params/consensus.json").data;
  const rp = useJson<{ pooled: { n: number; corr_net: number; corr_off: number; corr_def: number; spearman_net: number } }>("params/rapm_compare.json").data;
  const el = useJson<Record<string, { K: number; hca: number; carry: number; cap: number }>>("params/elo_mle.json").data;
  return (
    <div className="mx-auto max-w-[1100px]">
      <h1 className="mb-2 text-3xl font-semibold">Methodology<SeasonChip season={meta?.current_season} note="latest fit" /></h1>
      <p className="mb-6 text-muted">Fitted numbers on this page are read from the pipeline&apos;s parameter files, so they match the latest fit. The prose around them is written by hand. Definitions and judgment calls are labeled as such.</p>

      <Section title="Data">
        <p>Game, team box score, player box score and standings data come from the open sportsdataverse / hoopR release files of ESPN men&apos;s college basketball data, refreshed from ESPN&apos;s public JSON endpoints. Seasons 2008 to present are used for ratings: from 2008 at least 98% of games have team and player box scores and a neutral-site flag. Seasons are named by the year they end (2026 = 2025-26). Only Division I vs Division I games enter rating fits; other games appear on schedules.</p>
      </Section>

      <Section title="Adjusted efficiency (the main rating)">
        <p>For each team in each game the response is points per 100 possessions. Predictors are offense dummies for the team, defense dummies for the opponent, and a site term (home +1, neutral 0, away -1), fit by ridge regression toward a preseason prior. Ratings before a game use only games strictly before that date. Adjusted offense = league mean + offense effect; adjusted defense = league mean + defense effect (lower is better); AdjEM = offense minus defense. Tempo is a second ridge model of possessions per game (team effect for each side).</p>
        {prod && (
          <table className="dense prose">
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
              {prod.prior_coefs_current.roster && (["o", "d"] as const).map((k) => (
                <tr key={k}><td className="l">Roster prior ({k === "o" ? "offense" : "defense"}): intercept, last, two-ago, returning impact, incoming impact, returning minutes share, incoming share</td>
                  <td>{prod.prior_coefs_current.roster![k].beta.map((x) => x.toFixed(2)).join(", ")}</td><td className="l">regression on prior seasons, adopted after walk-forward cross validation (see Player impact)</td></tr>))}
              <tr><td className="l">Preseason prior: tempo coefs</td><td>{prod.prior_coefs_current.t.map((x) => x.toFixed(3)).join(", ")}</td><td className="l">same</td></tr>
              <tr><td className="l">Margin spread σ (base, per possession above 68)</td><td>{prod.sigma_coef[0].toFixed(2)}, {prod.sigma_coef[1].toFixed(3)}</td><td className="l">mean absolute historical residual, linear in predicted tempo</td></tr>
              <tr><td className="l">FTA weight in possession estimate</td><td>{poss ? poss.fta_coef.toFixed(3) : "–"}</td><td className="l">value that makes both teams&apos; possession estimates agree ({poss?.n_team_games.toLocaleString()} team-games)</td></tr>
            </tbody>
          </table>
        )}
        <p>Predicted score = predicted possessions × predicted efficiency for each side. Win probability = normal CDF of predicted margin over σ, then calibrated (see below). The 80% interval is an outcome interval on the margin: 80% of historical results landed within {prod ? `${prod.margin_residual_quantiles["0.1"].toFixed(1)} to +${prod.margin_residual_quantiles["0.9"].toFixed(1)}` : "…"} points of the prediction. It describes game-to-game randomness, not uncertainty in the ratings. There is no interval on the win probability itself yet: one based on rating uncertainty is planned and will be shown only after it is validated.</p>
      </Section>

      <Section title="Backtest (walk-forward, no leakage)">
        <p>For every game in {bt ? seasonRange(bt.test_seasons[0], bt.test_seasons[1]) : "…"} the model is refit each game day on earlier games only. Hyperparameters and preseason-prior coefficients for season S are chosen using seasons before S, and the spread and calibration parameters for S are fit on predictions from seasons before S. Two one-time choices were made on pooled results from all test seasons: the spread form (constant or tempo-dependent) and the calibrator type (none, Platt or isotonic). The candidates differ by less than 0.001 in log loss. A test in the repository proves that changing the results of a game (or of any game on the same day or later) does not change earlier predictions.</p>
        {bt ? (
          <>
            <table className="dense prose">
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
                <table className="dense prose">
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

      <Section title="Other ranking systems and the consensus">
        <p><b className="text-ink">Elo (margin-aware).</b> Ratings are in points of margin; expected margin = rating difference + home advantage; each result moves both ratings by K times the surprise, with the observed margin capped, and ratings regress toward zero between seasons. K, home advantage, carryover and the cap are estimated by minimizing squared margin error (Gaussian maximum likelihood) on seasons before each test season.{el && el["2026"] ? ` Latest fit: K ${el["2026"].K.toFixed(3)}, home ${el["2026"].hca.toFixed(2)} pts, carryover ${el["2026"].carry.toFixed(2)}, cap ${el["2026"].cap.toFixed(0)}.` : ""}</p>
        <p><b className="text-ink">Bradley-Terry (results only).</b> Ridge logistic regression on wins and losses, ignoring margin, with a home-court term and a prior from last season&apos;s strengths. Ridge strength and prior weight were chosen by walk-forward log loss; refit weekly.</p>
        <p><b className="text-ink">Player-driven.</b> Team rating built bottom-up from each player&apos;s minutes share times fitted impact (see below). It needs the season&apos;s own minutes, so it is a season-end system and is not part of the consensus weights.</p>
        <p><b className="text-ink">Résumé metrics.</b> Wins above bubble, strength of record and quadrant records, computed with our adjusted-efficiency rating in place of NET. They are definitions: bubble = rank 45, SOR reference = average of the top 25, quadrant cutoffs = NCAA rank bands by site.</p>
        <p><b className="text-ink">Consensus.</b> Non-negative least squares on held-out margin error over adjusted efficiency, Elo, Bradley-Terry and last season&apos;s rating; team ratings are blended with the (renormalized) learned weights, and a mean-rank column averages the systems&apos; ranks.</p>
        {cs && (<>
          <table className="dense prose"><thead><tr><th className="l">System (test seasons {seasonRange(cs.test_seasons[0], cs.test_seasons[1])})</th><th>MAE</th><th>RMSE</th><th>Log loss</th></tr></thead><tbody>
            {[["adjeff", "Adjusted efficiency"], ["elo", "Elo (margin-aware)"], ["bt", "Bradley-Terry (scaled)"], ["prev", "Previous-season rating"], ["cons", "Consensus"]].map(([k, l]) => (
              <tr key={k}><td className="l">{l}</td><td>{cs[k].mae.toFixed(3)}</td><td>{cs[k].rmse.toFixed(3)}</td><td>{cs[k].log_loss ? cs[k].log_loss.toFixed(4) : "–"}</td></tr>))}
          </tbody></table>
          <p>Learned production weights: {Object.entries(cs.production.weights).map(([k, v]) => `${k} ${v.toFixed(3)}`).join(", ")}. Honest note: the margin-aware Elo is close to the ridge model on margin error and the consensus beats both, so the ridge model is the flagship but not dominant.</p>
        </>)}
      </Section>

      <Section title="Conference projections">
        <p>Conference standings are simulated at least 20,000 times: completed conference games are fixed, and each remaining game is sampled as predicted margin plus normal noise (spread from the margin-spread model above) with a sampled total (noise sd from backtest residuals), rounded to integer scores so point-differential rules work. Each simulated final table is ordered with that conference&apos;s own tiebreaker rules (data files in <code>config/tiebreakers</code>), where a partially resolved multi-team tie restarts from the first rule for the teams still tied, and coin flips or draws are random. Steps that use NET or RPI use our adjusted-efficiency rating instead. Each conference is labeled <b className="text-ink">verified</b> (rule text found on an official conference page) or <b className="text-ink">fallback</b> (generic or best-known rules); see each conference page for its source link. Tournament field sizes are configuration values for the 2025-26 format. Best/worst possible finish uses win-count bounds.</p>
      </Section>

      <Section title="Player impact rating (v1, box-score based, experimental)">
        <p>Team adjusted offense and defense (from the model above) are regressed on minutes-weighted player rate features (usage, true shooting, assist/turnover/rebound/steal/block rates, free-throw and three-point rates). The coefficients are learned; a player&apos;s impact is his weighted feature value divided by five, so a player&apos;s minutes share times his impact adds up to the team rating. A low-minutes shrinkage (weight minutes / (minutes + k)) was tested; k is in the table below, and 0 means validation chose none. This rating fails a basic smell test: it rewards rebounding and shot blocking far too much, so backup centers can outrank star guards. The site shows it only on player pages, labeled experimental, and a play-by-play (RAPM) replacement is planned.</p>
        {pl && (<>
          <table className="dense prose"><tbody>
            <tr><td className="l">Ridge strength (leave-one-season-out CV)</td><td>{pl.alpha}</td></tr>
            <tr><td className="l">Low-minutes shrink k (walk-forward evidence)</td><td>{pl.shrink_k_minutes} minutes</td></tr>
            <tr><td className="l">In-sample team-rating R²: offense / defense</td><td>{pl.within_season_r2_offense.toFixed(2)} / {pl.within_season_r2_defense.toFixed(2)}</td></tr>
            <tr><td className="l">Next-season team offense RMSE: prior only vs prior + roster impact</td><td>{pl.prior_evaluation.rmse_o_base.toFixed(3)} vs {pl.prior_evaluation.rmse_o_full.toFixed(3)} (better in {pl.prior_evaluation.seasons_o_improved}/14 seasons)</td></tr>
            <tr><td className="l">Next-season team defense RMSE</td><td>{pl.prior_evaluation.rmse_d_base.toFixed(3)} vs {pl.prior_evaluation.rmse_d_full.toFixed(3)} (better in {pl.prior_evaluation.seasons_d_improved}/14 seasons)</td></tr>
          </tbody></table>
          <p><b className="text-ink">Decision:</b> {pl.decision}</p>
          {rp && <p><b className="text-ink">Versus published NCAA RAPM ({seasonRange(2011, 2020)}, {rp.pooled.n.toLocaleString()} matched players with 300+ minutes):</b> correlation with the box-score impact is {rp.pooled.corr_net.toFixed(2)} overall (offense {rp.pooled.corr_off.toFixed(2)}, defense {rp.pooled.corr_def.toFixed(2)}; Spearman {rp.pooled.spearman_net.toFixed(2)}). Box scores capture only a modest share of what on/off-based RAPM sees, especially on defense. RAPM is a comparison only and is not used in any rating.</p>}
          <p>Caveats: impact is model-relative, its scale is likely overstated for extreme rebounders and shot blockers, and defense is only weakly identified from box scores (R² about 0.45).</p>
        </>)}
      </Section>

      <Section title="Definitions (not fitted)">
        <ul className="list-disc space-y-1 pl-5">
          <li>Season = year the season ends. Division I membership for a season = teams listed in a D-I conference in that season&apos;s standings; for the upcoming season, before standings exist, ESPN&apos;s current conference membership list.</li>
          <li>Game type is derived from ESPN season type, tournament id and event headline; every NCAA tournament game is treated as neutral-site. Conference tournament games with no headline on a non-neutral site are labeled regular season (a known limitation).</li>
          <li>Possessions = FGA - OREB + TO + c · FTA, averaged over the two teams, with c fitted (above).</li>
          <li>SOS = mean AdjEM of D-I opponents faced. Luck = actual wins minus the sum of pregame win probabilities in D-I games.</li>
          <li>Heat colors show percentile among D-I teams (teal = better, orange = worse).</li>
        </ul>
      </Section>

      <Section title="Watchability (judgment call)">
        <p>Each upcoming game gets a 1-10 watchability score. Five components are each scaled to 0-100 by their percentile among historical D-I games (data-derived): quality (average AdjEM of the two teams), competitiveness (small predicted margin), tempo (predicted possessions), star power (best player impact on either team, which inherits the experimental impact rating&apos;s bias toward big men) and stakes (rank proximity, conference-title leverage from the standings simulation, bubble proximity). The weights are <b className="text-ink">chosen by hand, not fitted</b>: there is no ground truth for how watchable a game is. Score = 1 + 9 × weighted average percentile / 100. A component that is unavailable for a game has its weight redistributed.</p>
        {wt && (
          <table className="dense prose"><tbody>
            {Object.entries(wt.weights).map(([k, v]) => <tr key={k}><td className="l">{k.replace("_", " ")}</td><td>{v.toFixed(2)}</td></tr>)}
            {Object.entries(wt.stakes_weights).map(([k, v]) => <tr key={k}><td className="l text-muted">stakes: {k.replace("_", " ")}</td><td>{v.toFixed(2)}</td></tr>)}
          </tbody></table>
        )}
      </Section>

      <Section title="Judgment calls">
        <ul className="list-disc space-y-1 pl-5">
          <li>Seasons before 2008 are excluded from fits for coverage reasons; 2021 (COVID) is kept but was irregular.</li>
          <li>Numerical stabilizer: a penalty equal to one game-row on the league mean, home court and mean tempo keeps them defined before any games are played.</li>
        </ul>
      </Section>
      <p className="text-xs text-faint">Credits: ESPN (game data, team names and logos), the sportsdataverse / hoopR project (bulk data releases).</p>
    </div>
  );
}
