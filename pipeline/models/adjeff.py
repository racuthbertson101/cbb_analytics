"""Adjusted efficiency: ridge regression of points per 100 possessions on offense/defense team dummies plus site.

Convention: eff_a = mu + o_a + d_b + hca*site (+ venue effect); d is points ALLOWED above average (lower is better).
Adjusted offense = mu + o, adjusted defense = mu + d, adjusted margin = o - d (per 100 possessions).
Tempo model: poss = mu_t + t_a + t_b (ridge).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp


GLOBAL_PEN = 1.0  # numerical stabilizer (equivalent to one game-row of weight); negligible after the first days


@dataclass
class SeasonData:
    """Arrays for one season's D-I games, sorted by date."""
    season: int
    teams: np.ndarray  # team ids (str), index = column
    tix: dict
    date: np.ndarray  # int days since epoch
    ia: np.ndarray
    ib: np.ndarray
    site: np.ndarray
    ea: np.ndarray
    eb: np.ndarray
    poss: np.ndarray
    margin: np.ndarray
    game_id: np.ndarray
    frame: pd.DataFrame

    @staticmethod
    def from_frame(G: pd.DataFrame, season: int, team_universe=None) -> "SeasonData":
        g = G[G.season == season].sort_values(["date", "game_id"]).reset_index(drop=True)
        teams = np.array(sorted(set(team_universe) if team_universe is not None else set(g.a) | set(g.b)))
        tix = {t: i for i, t in enumerate(teams)}
        keep = g.a.isin(tix) & g.b.isin(tix)
        g = g[keep].reset_index(drop=True)
        return SeasonData(season, teams, tix, (g.date.values.astype("datetime64[D]").astype(np.int64)),
                          g.a.map(tix).values, g.b.map(tix).values, g.site.values, g.ea.values, g.eb.values,
                          g.poss.values, g.margin.values.astype(float), g.game_id.values, g)


@dataclass
class Ratings:
    teams: np.ndarray
    tix: dict
    o: np.ndarray
    d: np.ndarray
    t: np.ndarray
    mu: float
    hca: float
    mu_t: float
    h: np.ndarray | None  # venue-specific home effects (deviation from league hca), or None
    n_games: np.ndarray
    asof: int  # day number of the fit (games strictly before)
    params: dict = field(default_factory=dict)
    em_sd: np.ndarray | None = None  # posterior sd of each team's efficiency margin (o - d), per 100 possessions (Phase 5c)

    # ---- derived ----
    def adj_off(self):
        return self.mu + self.o

    def adj_def(self):
        return self.mu + self.d

    def adj_margin(self):
        return self.o - self.d

    def table(self) -> pd.DataFrame:
        t = pd.DataFrame({"team_id": self.teams, "adj_off": self.adj_off(), "adj_def": self.adj_def(),
                          "adj_margin": self.adj_margin(), "adj_tempo": self.mu_t + 2 * self.t, "n_games": self.n_games})
        if self.em_sd is not None:
            t["em_sd"] = self.em_sd
        return t

    # ---- prediction (shared interface) ----
    def predict(self, team_a, team_b, site=1.0, date=None) -> dict:
        """site = +1 team_a at home, 0 neutral, -1 team_a away. Returns margin/total/scores (interval and win prob are added
        by the calibrated wrapper in pipeline.models.predictor)."""
        i, j = self.tix[team_a], self.tix[team_b]
        venue = 0.0
        if self.h is not None and site != 0:
            venue = self.h[i] if site > 0 else self.h[j]
        adv = (self.hca + venue) * site
        ea = self.mu + self.o[i] + self.d[j] + adv
        eb = self.mu + self.o[j] + self.d[i] - adv
        poss = self.mu_t + self.t[i] + self.t[j]
        sa, sb = ea * poss / 100, eb * poss / 100
        return {"margin": sa - sb, "total": sa + sb, "score_a": sa, "score_b": sb, "poss": poss}

    def predict_arrays(self, ia, ib, site) -> tuple:
        adv = self.hca * site
        if self.h is not None:
            venue = np.where(site > 0, self.h[ia], np.where(site < 0, self.h[ib], 0.0))
            adv = (self.hca + venue) * site
        ea = self.mu + self.o[ia] + self.d[ib] + adv
        eb = self.mu + self.o[ib] + self.d[ia] - adv
        poss = self.mu_t + self.t[ia] + self.t[ib]
        return ea * poss / 100, eb * poss / 100, poss


def _cap(ea, eb, cap):
    if cap is None or not np.isfinite(cap):
        return ea, eb
    D = ea - eb
    shr = np.where(np.abs(D) > cap, cap / np.maximum(np.abs(D), 1e-9), 1.0)
    m = (ea + eb) / 2
    return m + (ea - m) * shr, m + (eb - m) * shr


def fit(sd: SeasonData, n: int, asof_day: int, params: dict) -> Ratings:
    """Fit on the first n games of `sd` (all strictly before asof_day). params: lam, lam_t, halflife, cap, lam_h,
    prior_o, prior_d, prior_t (arrays over sd.teams, default 0)."""
    N = len(sd.teams)
    lam, lam_t = params["lam"], params["lam_t"]
    hl, cap, lam_h = params.get("halflife"), params.get("cap"), params.get("lam_h")
    po = params.get("prior_o", np.zeros(N))
    pd_ = params.get("prior_d", np.zeros(N))
    pt = params.get("prior_t", np.zeros(N))
    ia, ib, site = sd.ia[:n], sd.ib[:n], sd.site[:n]
    age = asof_day - sd.date[:n]
    w = np.ones(n) if not hl else 0.5 ** (age / hl)
    ea, eb = _cap(sd.ea[:n], sd.eb[:n], cap)
    r = np.arange(n)
    o = d = np.zeros(N); hca = 0.0; mu = 100.0; h = None
    if not params.get("skip_eff"):
        use_h = lam_h is not None and np.isfinite(lam_h)
        P = 2 * N + 2 + (N if use_h else 0)
        rows = np.concatenate([r, r, r, r, r + n, r + n, r + n, r + n])
        cols = np.concatenate([ia, N + ib, np.full(n, 2 * N), np.full(n, 2 * N + 1),
                               ib, N + ia, np.full(n, 2 * N), np.full(n, 2 * N + 1)])
        vals = np.concatenate([np.ones(n), np.ones(n), site, np.ones(n), np.ones(n), np.ones(n), -site, np.ones(n)])
        if use_h:
            rows = np.concatenate([rows, r, r + n])
            cols = np.concatenate([cols, 2 * N + 2 + ia, 2 * N + 2 + ia])
            vals = np.concatenate([vals, site, -site])
        X = sp.csr_matrix((vals, (rows, cols)), shape=(2 * n, P))
        y = np.concatenate([ea, eb])
        W = np.concatenate([w, w])
        XtW = X.T.multiply(W).tocsr()
        A = (XtW @ X).toarray()
        rhs = XtW @ y
        pen = np.zeros(P)
        pen[:2 * N] = lam
        pen[2 * N:2 * N + 2] = GLOBAL_PEN  # numerical stabilizer: keeps hca/mu defined before any games exist
        b0 = np.zeros(P)
        b0[:N], b0[N:2 * N] = po, pd_
        b0[2 * N], b0[2 * N + 1] = params.get("prior_hca", 0.0), params.get("prior_mu", 100.0)
        if use_h:
            pen[2 * N + 2:] = lam_h
        A[np.diag_indices(P)] += pen
        rhs = rhs + pen * b0
        # small jitter for numerical safety when a column is empty
        A[np.diag_indices(P)] += 1e-9
        beta = np.linalg.solve(A, rhs)
        o, d, hca, mu = beta[:N], beta[N:2 * N], beta[2 * N], beta[2 * N + 1]
        h = beta[2 * N + 2:] if use_h else None
        if params.get("with_sd"):
            # Gaussian-prior reading of the ridge: posterior Var(beta) = sigma2 * A^-1, with sigma2 the per-row efficiency noise
            # (fitted constant, pipeline/params/rating_sd.json). Var(o_i - d_i) from the 2x2 block of team i.
            Ai = np.linalg.inv(A)
            ii = np.arange(N)
            var_em = Ai[ii, ii] + Ai[N + ii, N + ii] - 2 * Ai[ii, N + ii]
            em_sd = np.sqrt(np.maximum(var_em, 0) * params["sigma2_eff"])

    # tempo
    Xt = sp.csr_matrix((np.ones(3 * n), (np.concatenate([r, r, r]), np.concatenate([ia, ib, np.full(n, N)]))), shape=(n, N + 1))
    hlt = params.get("halflife_t", hl)
    wt = np.ones(n) if not hlt else 0.5 ** (age / hlt)
    XtWt = Xt.T.multiply(wt).tocsr()
    At = (XtWt @ Xt).toarray()
    rt = XtWt @ sd.poss[:n]
    pent = np.zeros(N + 1)
    pent[:N] = lam_t
    pent[N] = GLOBAL_PEN
    At[np.diag_indices(N + 1)] += pent + 1e-9
    rt = rt + pent * np.concatenate([pt, [params.get("prior_mu_t", 68.0)]])
    bt = np.linalg.solve(At, rt)
    ng = np.bincount(ia, minlength=N) + np.bincount(ib, minlength=N)
    return Ratings(sd.teams, sd.tix, o, d, bt[:N], float(mu), float(hca), float(bt[N]), h, ng, asof_day,
                   {k: v for k, v in params.items() if not k.startswith("prior_")},
                   em_sd if params.get("with_sd") and not params.get("skip_eff") else None)
