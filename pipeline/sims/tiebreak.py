"""Tiebreaker engine: ordered rule lists (data in config/tiebreakers/*.yaml) applied to conference standings.

A scenario is a `Standing` built from a full set of conference results. `order()` returns teams best-to-worst.

Rule tokens
  h2h            win pct in games among the tied teams (mini-conference); unequal game counts allowed
  vs_standings   win pct vs the highest-placed teams outside the tie, going down the standings (teams with equal records are one group);
                 a level counts only if every tied team played that group
  road_pct       conference road win pct
  road_vs_standings   as vs_standings but road games only
  h2h_point_diff point differential in games among the tied teams
  point_diff     overall conference point differential
  rating         our adjusted-efficiency rating (labeled substitute for NET/RPI/other computer ratings)
  random         coin flip / public draw
After a rule splits a tied group, each remaining tied subgroup restarts from the first rule when `restart_on_partial` (the common
"revert to the beginning" clause), otherwise continues with the next rule.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GENERIC_FALLBACK = ["h2h", "vs_standings", "random"]  # SPEC fallback: h2h, common opponents / top of standings, then random


@dataclass
class Standing:
    n: int
    wins: np.ndarray  # (n,) conference wins
    games: np.ndarray  # (n,) conference games played
    H: np.ndarray  # (n,n) wins of i over j
    PD: np.ndarray  # (n,n) point differential of i vs j (sum over games, i minus j)
    road_w: np.ndarray  # (n,n) road wins of i at j
    road_g: np.ndarray  # (n,n) road games of i at j
    rating: np.ndarray  # (n,) higher = better
    rng: np.random.Generator

    @property
    def G(self):
        return self.H + self.H.T


def _pct(w, g):
    return w / g if g > 0 else None


def _groups_by_key(items, key):
    """Partition items into groups of equal key, best (highest) first."""
    d = {}
    for t in items:
        d.setdefault(key[t], []).append(t)
    return [d[k] for k in sorted(d, reverse=True)]


def _outside_levels(st: Standing, group):
    """Outside teams grouped by conference win pct (collective ties), best first."""
    gs = set(group)
    outside = [t for t in range(st.n) if t not in gs]
    pct = {t: round(st.wins[t] / st.games[t], 9) if st.games[t] else 0.0 for t in outside}
    return _groups_by_key(outside, pct)


def rule_keys(rule: str, group, st: Standing):
    """Return {team: comparable key} (higher better) or None if the rule cannot separate/does not apply."""
    if rule == "h2h":
        k = {}
        for t in group:
            w = sum(st.H[t, o] for o in group if o != t)
            g = sum(st.G[t, o] for o in group if o != t)
            if g == 0:
                return None
            k[t] = round(w / g, 9)
        return k
    if rule in ("vs_standings", "road_vs_standings"):
        for lvl in _outside_levels(st, group):
            if rule == "vs_standings":
                w = {t: sum(st.H[t, o] for o in lvl) for t in group}
                g = {t: sum(st.G[t, o] for o in lvl) for t in group}
            else:
                w = {t: sum(st.road_w[t, o] for o in lvl) for t in group}
                g = {t: sum(st.road_g[t, o] for o in lvl) for t in group}
            if any(g[t] == 0 for t in group):
                continue
            k = {t: round(w[t] / g[t], 9) for t in group}
            if len(set(k.values())) > 1:
                return k
        return None
    if rule == "road_pct":
        k = {}
        for t in group:
            g = st.road_g[t].sum()
            if g == 0:
                return None
            k[t] = round(st.road_w[t].sum() / g, 9)
        return k
    if rule == "h2h_point_diff":
        k = {t: int(sum(st.PD[t, o] for o in group if o != t)) for t in group}
        return k
    if rule == "point_diff":
        return {t: int(st.PD[t].sum()) for t in group}
    if rule == "rating":
        return {t: float(st.rating[t]) for t in group}
    return None


def resolve(group, st: Standing, rules, restart=True, start=0):
    if len(group) == 1:
        return list(group)
    for i in range(start, len(rules)):
        rule = rules[i]
        if rule == "random":
            g = list(group)
            st.rng.shuffle(g)
            return g
        k = rule_keys(rule, group, st)
        if k is None or len(set(k.values())) == 1:
            continue
        out = []
        for part in _groups_by_key(group, k):
            out += resolve(part, st, rules, restart, 0 if restart else i + 1) if len(part) > 1 else part
        return out
    g = list(group)  # rules exhausted without random: coin flip
    st.rng.shuffle(g)
    return g


def order(st: Standing, rules, restart=True):
    """Final order best->worst. Ties in win pct are broken by rules (highest ties first)."""
    pct = {t: round(st.wins[t] / st.games[t], 9) if st.games[t] else 0.0 for t in range(st.n)}
    out = []
    for grp in _groups_by_key(range(st.n), pct):
        out += resolve(grp, st, rules, restart)
    return out


def build_standing(n, results, rating=None, rng=None) -> Standing:
    """results: iterable of (home_idx, away_idx, home_margin) conference games; margin>0 home win. Neutral games: treat 'home' as first team."""
    H = np.zeros((n, n))
    PD = np.zeros((n, n))
    rw = np.zeros((n, n))
    rg = np.zeros((n, n))
    for h, a, m in results:
        if m > 0:
            H[h, a] += 1
            rw[h, a] += 0
        else:
            H[a, h] += 1
            rw[a, h] += 1
        rg[a, h] += 1
        PD[h, a] += m
        PD[a, h] -= m
    wins = H.sum(axis=1)
    games = (H + H.T).sum(axis=1)
    return Standing(n, wins, games, H, PD, rw, rg, np.zeros(n) if rating is None else np.asarray(rating, float), rng or np.random.default_rng(0))
