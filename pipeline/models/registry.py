"""Registry of rating systems. New systems register themselves; core files are not edited.

A system is a class with a static `fit(games_before_date, params) -> ratings`, where `ratings.predict(team_a, team_b, site, date)`
returns {margin, total, score_a, score_b, win_prob_a, interval}.
"""
SYSTEMS: dict = {}


def register(key: str):
    def deco(cls):
        SYSTEMS[key] = cls
        return cls
    return deco


def get(key: str):
    return SYSTEMS[key]
