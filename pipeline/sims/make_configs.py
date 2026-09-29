"""Generate config/tiebreakers/*.yaml from researched rules (sources recorded per conference).

Research date 2026-09-29 via web search of conference sites. status: verified = complete ordered rule text found on an official
conference page (or its search excerpt); fallback = official text not fully retrieved, best-known/generic rules used.
`rating` = our adjusted-efficiency rating, a labeled substitute for NET/RPI final tiebreakers.
"""
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[2] / "config" / "tiebreakers"

H2H_STD = ["h2h", "vs_standings", "random"]
H2H_NET = ["h2h", "vs_standings", "rating", "random"]

C = [
    # name, rules, status, qualifiers, byes, source, note
    ("Atlantic Coast Conference", H2H_STD, "verified", 15, [4], "https://theacc.com/mbbseeding", "Two-team: h2h, record vs highest common opponent down the standings, coin flip. 3+: mini-conference h2h, then vs standings, restart on partial split."),
    ("Big Ten Conference", H2H_NET, "fallback", 18, [4], "https://nextgen.bigten.org/api/media/file/3f04bd9b-4db2-400d-b199-ec297bd5295c-2025_20B1G_20Basketball_20Tournament_20Tiebreakers.pdf", "First two steps (h2h, then record vs highest-placed team down the standings) confirmed from the official PDF excerpt; later steps not retrieved (PDF unreadable)."),
    ("Southeastern Conference", H2H_STD, "verified", 16, [4], "https://www.secsports.com/article/11098238/tournament-tiebreakers", "Two-team: h2h, then vs highest-seeded common opponent down, then coin flip. 3+: h2h among group, then vs #1 seed down; reduce to two-team formula."),
    ("Big 12 Conference", ["h2h", "vs_standings", "road_pct", "road_vs_standings", "random"], "verified", 16, [4], "https://big12sports.com/sports/2011/6/22/1520897.aspx", "Document last updated 2015-16. Final step is a public draw."),
    ("Big East Conference", H2H_STD, "verified", 11, [], "https://www.bigeast.com/sports/2021/2/26/MBB_0226212241.aspx", "Also compares wins totals and record vs teams under the 10-game threshold; with full schedules those steps cannot separate teams, then coin flip."),
    ("Atlantic 10 Conference", H2H_STD, "fallback", 14, [], "https://atlantic10.com/news/2015/2/21/209901106.aspx", "Two-team tie uses record vs highest common opponent down; head-to-head placement for two teams not confirmed. Document dated 2015."),
    ("American Conference", H2H_STD, "verified", 14, [], "https://theamerican.org/documents/2024/3/3/2024_Basketball_Tiebreakers.pdf", "Excerpt: head-to-head, then record vs highest-ranked team outside the tie, descending."),
    ("Mountain West Conference", H2H_NET, "fallback", 12, [], "https://www.si.com/college/boise-state/basketball/mountain-west-men-basketball-tournament-tiebreaker-scenarios", "Source is a media article, not the conference page: h2h, record vs highest seed outside the tie, then NET."),
    ("West Coast Conference", H2H_NET, "fallback", 12, [], "https://wccsports.com/news/2026/2/25/bracket-announced-for-2026-credit-union-1-west-coast-conference-mens-basketball-championship.aspx", "Reported: record vs top seed outside tie, then NET; 3+ teams use a head-to-head pod. Official rule text not retrieved."),
    ("Missouri Valley Conference", ["h2h", "rating", "random"], "verified", 11, [], "https://mvc-sports.com/news/2018/12/18/arch-madness-revises-tiebreaker.aspx", "Two-way: h2h then NET; 3+: cumulative record vs the other tied teams, reduce to two-way."),
    ("America East Conference", ["h2h", "vs_standings", "road_pct", "rating", "random"], "verified", 8, [], "https://americaeast.com/sports/2013/3/1/206563260.aspx", "Partial multi-team resolution restarts at step 1; NET as final step per recent excerpt."),
    ("Atlantic Sun Conference", H2H_NET, "fallback", 12, [], "https://www.aseaofred.com/asun-has-new-tiebreaker-procedures-this-season/", "2025 procedure per media excerpt: h2h, record vs top team(s) descending, NET; partial splits restart."),
    ("Big Sky Conference", H2H_NET, "fallback", 10, [], "https://static.bigskyconf.com/custompages/Code14-15/Basketball%20-%20Men's%20Championship.pdf", "2014-15 policy (RPI then coin flip); RPI replaced by our rating."),
    ("Big South Conference", H2H_STD, "verified", 9, [], "https://bigsouthsports.com/news/2015/7/2/MBB_0703150702844.aspx?path=mbball", "Teams with the same conference record are considered collectively when going down the standings."),
    ("Big West Conference", H2H_STD, "fallback", 8, [], "https://bigwest.org/", "Official tiebreaker text not found; generic fallback."),
    ("Coastal Athletic Association", H2H_NET, "verified", 13, [], "https://caasports.com/sports/2022/2/25/MBB_0225223020.aspx", "3+ teams viewed as a mini-conference; all teams (eligible or not) are seeded."),
    ("Conference USA", H2H_STD, "fallback", 10, [], "https://conferenceusa.com/news/2001/2/16/C_USA_Announces_Basketball_Tiebreaker.aspx", "Only a 2001 divisional-era policy found; generic fallback."),
    ("Horizon League", H2H_NET, "verified", 11, [], "https://horizonleague.org/sports/2019/2/26/MBB_0226194917.aspx", "Ties broken top to bottom; tied teams considered as one entry when comparing records."),
    ("Ivy League", H2H_NET, "verified", 4, [], "https://ivyleague.com/sports/2024/2/13/MBB_0213244341.aspx", "Top four qualify; ties for top four positions use these steps."),
    ("Metro Atlantic Athletic Conference", H2H_STD, "verified", 10, [], "https://maacsports.com/sports/2018/1/31/MBKB_0131185303.aspx", "3+ teams: mini-conference; final step coin toss."),
    ("Mid-American Conference", H2H_STD, "verified", 8, [], "https://getsomemaction.com/sports/2023/2/24/BSK_0224232059.aspx", "Two-team: h2h, winning pct vs ranked common opponents, coin flip; 3+: record among tied teams then two-team procedure."),
    ("Mid-Eastern Athletic Conference", H2H_STD, "fallback", 7, [], "https://en.wikipedia.org/wiki/2026_MEAC_men%27s_basketball_tournament", "Official tiebreaker text not found; generic fallback."),
    ("Northeast Conference", H2H_NET, "fallback", 8, [], "https://en.wikipedia.org/wiki/2026_NEC_men%27s_basketball_tournament", "Official NEC procedure (2021) cited on Wikipedia: h2h, records vs individual teams top down, NET; page not retrieved."),
    ("Ohio Valley Conference", H2H_STD, "verified", 8, [], "https://ovcsports.com/news/2024/1/4/mens-womens-basketball-tiebreaker.aspx", "Ties higher in the standings are broken first; final alternative is a coin toss."),
    ("Patriot League", H2H_NET, "verified", 10, [], "https://patriotleague.org/sports/2022/1/1/GEN_0101223737.aspx?path=general", "After NET: winning pct vs common non-league opponents (not modeled; cannot separate our simulated conference schedule)."),
    ("Southern Conference", H2H_NET, "fallback", 10, [], "http://www.soconsports.com/ViewArticle.dbml?ATCLID=211507238&DB_OEM_ID=4000", "Excerpt only: h2h, records vs individual teams top down, NET."),
    ("Southland Conference", H2H_NET, "verified", 8, [], "https://www.southland.org/sports/2017/1/31/2017_BB_TB.aspx", "Recent seasons replace the RPI step with NET; coin flip last."),
    ("Southwestern Athletic Conference", ["h2h", "h2h_point_diff", "vs_standings", "random"], "verified", 12, [], "https://swac.org/sports/2021/11/10/MBB_1110212613.aspx", "Point differential between the tied teams if the season series is split."),
    ("Summit League", H2H_NET, "verified", 9, [], "http://www.thesummitleague.org/tournaments/sball/2016-17/tiebreakers", "Source text uses RPI as final step; replaced by our rating. Once broken, a tie stays broken."),
    ("Sun Belt Conference", H2H_STD, "verified", 14, [], "https://sunbeltsports.org/news/2024/2/23/mens-basketball-sun-belt-basketball-championship-seeding-tiebreakers.aspx", "Final step is a commissioner draw."),
    ("Western Athletic Conference", H2H_STD, "fallback", 7, [], "https://en.wikipedia.org/wiki/2025_WAC_men%27s_basketball_tournament", "Reported: h2h then WAC resume seeding points / records vs top teams; official text not retrieved."),
]


def slug(name):
    return name.lower().replace(" ", "_").replace("/", "_")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rules, status, q, byes, src, note in C:
        d = {"conference": name, "status": status, "restart_on_partial": True, "rules": rules, "qualifiers": q, "bye_seed_lines": byes,
             "source_url": src, "researched": "2026-09-29", "notes": note,
             "qualifiers_note": "Tournament field size: best known 2025-26 format; verify each season."}
        (OUT / f"{slug(name)}.yaml").write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True), encoding="utf8")
    fb = {"conference": "_fallback", "status": "fallback", "restart_on_partial": True, "rules": ["h2h", "vs_standings", "random"],
          "qualifiers": 8, "bye_seed_lines": [], "source_url": None, "notes": "Generic rules for any conference without a config: head to head, record against the top of the standings in order, then random."}
    (OUT / "_fallback.yaml").write_text(yaml.safe_dump(fb, sort_keys=False), encoding="utf8")
    print(len(C), "configs;", sum(1 for c in C if c[2] == "verified"), "verified")


if __name__ == "__main__":
    main()
