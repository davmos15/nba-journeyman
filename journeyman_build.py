"""Journeyman — NBA: pure, network-free build helpers.

Shared by build_players.py (which supplies data from nba_api) and the tests.
Position is HEURISTIC, derived from the career per-game stat profile — same
philosophy as the AFL builder's infer_pos: coarse buckets, drives only a late
clue, hand-overridable in players.json.
"""

DECADES = [1980, 1990, 2000, 2010, 2020]


def infer_pos(ppg, rpg, apg, bpg):
    """Coarse GUARD / WING / BIG buckets from career per-game averages.
    Deliberately blunt to avoid confident-wrong labels (mirrors AFL infer_pos)."""
    if rpg >= 8.5 or bpg >= 1.2:      return "BIG"
    if apg >= 4.5:                    return "GUARD"
    if apg >= 3.0 and rpg < 5.0:      return "GUARD"
    if rpg >= 6.0:                    return "BIG"
    return "WING"


def primary_team(rows):
    """rows: iterable of (team, games). Returns the team with the most games,
    aggregating duplicates. Collapses a traded season to one team."""
    agg = {}
    for team, gp in rows:
        agg[team] = agg.get(team, 0) + gp
    best, bestgp = None, -1
    for team, gp in agg.items():
        if gp > bestgp:
            best, bestgp = team, gp
    return best


def tag_decades(seasons, min_seasons=3):
    """A decade qualifies if the player has >= min_seasons seasons that STARTED
    in it (the spec's 'more than 2 seasons' rule). Seasons are labelled by end
    year, so the 1989-90 season (y=1990) counts as a 1980s season. Sorted list."""
    counts = {}
    for s in seasons:
        d = ((s["y"] - 1) // 10) * 10
        counts[d] = counts.get(d, 0) + 1
    return sorted(d for d in DECADES if counts.get(d, 0) >= min_seasons)


def assemble_player(name, season_records):
    """season_records: list of per-season dicts {y, team, gp, pts, reb, ast, stl, blk}.
    Returns a player dict WITHOUT the `answer` flag (added later by classify)."""
    seasons = sorted(season_records, key=lambda r: r["y"])
    teams = []
    for s in seasons:
        if s["team"] not in teams:
            teams.append(s["team"])
    games = sum(s["gp"] for s in seasons)
    # career per-game weighted by games played, for position inference
    def wavg(key):
        tot = sum(s[key] * s["gp"] for s in seasons)
        return tot / games if games else 0.0
    pos = infer_pos(wavg("pts"), wavg("reb"), wavg("ast"), wavg("blk"))
    points = round(sum(s["pts"] * s["gp"] for s in seasons))  # career points total
    return {
        "name": name,
        "pos": pos,
        "first": seasons[0]["y"],
        "last": seasons[-1]["y"],
        "teams": teams,
        "games": games,
        "points": points,
        "decades": tag_decades(seasons),
        "seasons": seasons,
    }


def classify(players, answer_min_games, guess_min_games):
    """Set the `answer` flag, drop players below the guess threshold, and trim
    `seasons` from guess-only players. Returns the kept players."""
    out = []
    for p in players:
        answerable = p["games"] >= answer_min_games
        guessable = p["games"] >= guess_min_games
        if not (answerable or guessable):
            continue
        p = dict(p)
        p["answer"] = answerable
        if not answerable:
            p.pop("seasons", None)
        out.append(p)
    return out
