/** Client-side prediction engine shared by Compare and Game (same formulas as pipeline/models/production.py). */
export type Pred = { sigma_coef: number[]; cal_x: number[]; cal_y: number[]; q10: number; q90: number; score_q10: number; score_q90: number };
export type RatingsFile = { teams: string[]; dates: string[]; off: (number | null)[][]; def: (number | null)[][]; tempo: (number | null)[][]; mu: number[]; hca: number[] };
export type Preseason = { teams: string[]; off: (number | null)[]; def: (number | null)[]; tempo: (number | null)[]; mu: number; hca: number };
export type Snapshot = { teams: string[]; off: (number | null)[]; def: (number | null)[]; tempo: (number | null)[]; mu: number; hca: number };

const erf = (x: number) => {
  const s = Math.sign(x), a = Math.abs(x), t = 1 / (1 + 0.3275911 * a);
  return s * (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a));
};
export const cdf = (z: number) => 0.5 * (1 + erf(z / Math.SQRT2));
export const interp = (x: number, xs: number[], ys: number[]) => {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) return ys[i - 1] + ((ys[i] - ys[i - 1]) * (x - xs[i - 1])) / (xs[i] - xs[i - 1]);
  return ys[ys.length - 1];
};
/** Margin spread (points) for a game with `poss` predicted possessions: the tempo-dependent sigma, floored at 3. */
export const sigmaOf = (PP: Pred, poss: number) => Math.max(PP.sigma_coef[0] + PP.sigma_coef[1] * (poss - 68), 3);
/** Calibrated win probability for a predicted margin. */
export const winProb = (PP: Pred, margin: number, poss: number) => interp(cdf(margin / sigmaOf(PP, poss)), PP.cal_x, PP.cal_y);

/** Latest ratings: the last date of an in-season ratings file, or the preseason file. */
export function latest(R?: RatingsFile | null, PRE?: Preseason | null): Snapshot | null {
  if (R) { const i = R.dates.length - 1; return { teams: R.teams, off: R.off[i], def: R.def[i], tempo: R.tempo[i], mu: R.mu[i], hca: R.hca[i] }; }
  return PRE ?? null;
}

/** Matchup of team a vs team b; site = +1 a at home, 0 neutral, -1 a away. Margin is from a's side, with its parts. */
export function matchup(S: Snapshot, a: string, b: string, site: number) {
  const i = S.teams.indexOf(a), j = S.teams.indexOf(b);
  if (i < 0 || j < 0 || S.off[i] == null || S.off[j] == null) return null;
  const [oa, ob, da, db] = [S.off[i] as number, S.off[j] as number, S.def[i] as number, S.def[j] as number];
  const adv = S.hca * site;
  const ea = oa + db - S.mu + adv, eb = ob + da - S.mu - adv;
  const poss = ((S.tempo[i] as number) + (S.tempo[j] as number)) / 2;
  const k = poss / 100;
  return { ea, eb, poss, margin: (ea - eb) * k, sa: ea * k, sb: eb * k, parts: { offense: (oa - ob) * k, defense: (db - da) * k, home: 2 * adv * k } };
}
