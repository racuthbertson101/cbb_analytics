"""Template for a new ranking system (copy to a new module name without the leading underscore).

KEY = "mysys"                      # short id used in JSON and site.json
def snapshots(season, teams, dates):
    '''Return a list (one per snapshot date, same order as `dates`) of lists (one per team in `teams`) of ratings in points of
    margin vs an average team (None where unavailable). Must only use games strictly before each snapshot date.'''
    raise NotImplementedError
"""
