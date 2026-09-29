"""Phase 0 data audit: per-season coverage of the sportsdataverse ESPN mbb release files."""
import pandas as pd, numpy as np
from pathlib import Path
R = Path('data/raw/sdv')
rows = []
for y in range(2003, 2028):
    p = R/'schedules'/f'mbb_schedule_{y}.parquet'
    if not p.exists(): continue
    s = pd.read_parquet(p)
    for c in ['away_non_div1_team','home_conference_id','PBP']:
        if c not in s: s[c]=np.nan
    s = s.drop_duplicates('game_id')
    comp = s[s.status_type_completed.fillna(False) & s.home_score.notna() & s.away_score.notna()]
    tb = pd.read_parquet(R/'team_box'/f'team_box_{y}.parquet', columns=['game_id','team_id','field_goals_attempted','offensive_rebounds','turnovers','team_score']) if (R/'team_box'/f'team_box_{y}.parquet').exists() else None
    pb = pd.read_parquet(R/'player_box'/f'player_box_{y}.parquet', columns=['game_id','minutes','points']) if (R/'player_box'/f'player_box_{y}.parquet').exists() else None
    d1 = comp[~comp.away_non_div1_team.fillna(False).astype(bool)]
    r = dict(season=y, sched_rows=len(s), completed=len(comp), d1_completed=len(d1), neutral_pct=round(100*comp.neutral_site.fillna(False).mean(),1),
             season_types=dict(s.season_type.value_counts()), conf_id_pct=round(100*comp.home_conference_id.notna().mean(),1))
    if tb is not None:
        g = tb.groupby('game_id').size()
        both = set(g[g==2].index)
        r['team_box_pct'] = round(100*len(set(d1.game_id)&both)/max(len(d1),1),1)
        ok = tb.dropna(subset=['field_goals_attempted'])
        r['team_box_fga_nonnull_pct'] = round(100*len(ok)/max(len(tb),1),1)
    else: r['team_box_pct']=0
    if pb is not None:
        r['player_box_pct'] = round(100*len(set(d1.game_id)&set(pb.game_id))/max(len(d1),1),1)
        r['minutes_nonnull_pct'] = round(100*pb.minutes.notna().mean(),1)
    else: r['player_box_pct']=0
    ps = R/'pbp'/f'play_by_play_{y}.parquet'
    rows.append(r)
df = pd.DataFrame(rows)
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
print(df.drop(columns=['season_types']).to_string(index=False))
print(df[['season','season_types']].tail(6).to_string(index=False))
df.to_json('data/raw/audit.json', orient='records')
