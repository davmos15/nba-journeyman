from journeyman_build import infer_pos, primary_team, tag_decades, assemble_player, DECADES

def test_infer_pos_big_on_rebounds():
    assert infer_pos(ppg=18, rpg=11, apg=1.5, bpg=2.1) == "BIG"

def test_infer_pos_guard_on_assists():
    assert infer_pos(ppg=20, rpg=3.5, apg=8.0, bpg=0.2) == "GUARD"

def test_infer_pos_wing_default():
    assert infer_pos(ppg=16, rpg=5, apg=3, bpg=0.4) == "WING"

def test_primary_team_picks_most_games():
    assert primary_team([("MIN", 20), ("PHI", 45)]) == "PHI"

def test_primary_team_aggregates_duplicates():
    assert primary_team([("LAL", 10), ("LAL", 30), ("HOU", 25)]) == "LAL"

def test_tag_decades_needs_three_seasons():
    seasons = [{"y": y} for y in (1991, 1992, 1993, 1998)] + [{"y": 2001}, {"y": 2002}]
    # 90s has 4 seasons (>=3) -> tagged; 2000s has 2 (<3) -> not tagged
    assert tag_decades(seasons) == [1990]

def test_tag_decades_multiple():
    seasons = [{"y": y} for y in (1988, 1989, 1990, 1991, 1992, 1993)]
    assert tag_decades(seasons) == [1980, 1990]

def test_assemble_player_shape():
    recs = [
        {"y": 1996, "team": "CHI", "gp": 82, "pts": 30.4, "reb": 6.6, "ast": 4.3, "stl": 2.2, "blk": 0.5},
        {"y": 1997, "team": "CHI", "gp": 82, "pts": 28.7, "reb": 5.9, "ast": 3.5, "stl": 1.7, "blk": 0.5, "gs": 82},
        {"y": 1998, "team": "CHI", "gp": 82, "pts": 28.7, "reb": 5.8, "ast": 3.5, "stl": 1.7, "blk": 0.5, "gs": 80},
    ]
    p = assemble_player("Michael Jordan", recs)
    # starts sum only the seasons that carry games-started (1996-97 onwards)
    assert p["starts"] == 162
    assert p["name"] == "Michael Jordan"
    assert p["first"] == 1996 and p["last"] == 1998
    assert p["teams"] == ["CHI"]
    assert p["games"] == 246
    assert p["pos"] in ("GUARD", "WING", "BIG")
    assert p["decades"] == [1990]
    assert p["seasons"][0]["y"] == 1996  # sorted ascending
    assert "answer" not in p  # answer flag added later by classify step

from journeyman_build import classify

def _mk(name, games, last, decades, starts=0, gs_known=True):
    """A one-season stand-in career. gs_known=False models the pre-1996 era,
    where the source has no games-started."""
    season = {"y": last, "team": "X", "gp": 1,
              "pts": 1, "reb": 1, "ast": 1, "stl": 0, "blk": 0}
    if gs_known:
        season["gs"] = starts
    return {"name": name, "pos": "WING", "first": last-3, "last": last,
            "teams": ["X"], "games": games, "starts": starts, "points": games*10,
            "decades": decades, "seasons": [season]}

THRESHOLDS = dict(answer_min_starts=200, answer_min_games=400, guess_min_games=100)

def test_classify_flags_and_trims():
    players = [
        _mk("Star", 900, 2015, [2010], starts=700),       # answerable on starts
        _mk("Journeyman", 200, 2015, [2010], starts=10),  # guess-only
        _mk("Scrub", 20, 2015, [2010]),                   # dropped entirely
    ]
    out = classify(players, **THRESHOLDS)
    names = {p["name"]: p for p in out}
    assert "Scrub" not in names
    assert names["Star"]["answer"] is True
    assert "seasons" in names["Star"]
    assert names["Journeyman"]["answer"] is False
    assert "seasons" not in names["Journeyman"]  # trimmed

def test_classify_bench_career_is_not_answerable():
    # long career, rarely started -> guessable but never the mystery player
    out = classify([_mk("Benchie", 900, 2015, [2010], starts=40)], **THRESHOLDS)
    assert out[0]["answer"] is False

def test_classify_pre_1996_falls_back_to_games():
    # no games-started in the source for this era, so career games decides
    old = _mk("Eighties Great", 900, 1990, [1980], gs_known=False)
    thin = _mk("Eighties Filler", 300, 1990, [1980], gs_known=False)
    out = {p["name"]: p for p in classify([old, thin], **THRESHOLDS)}
    assert out["Eighties Great"]["answer"] is True
    assert out["Eighties Filler"]["answer"] is False

def test_classify_straddling_career_qualifies_on_either_rule():
    # career crosses the 1996 boundary: enough post-1996 starts on its own...
    starter = _mk("Crossover Starter", 500, 2001, [1990, 2000], starts=260)
    starter["seasons"].append({"y": 1994, "team": "X", "gp": 60, "pts": 9,
                               "reb": 3, "ast": 2, "stl": 0, "blk": 0})
    # ...and one that started rarely after 1996 but has the games for the fallback
    veteran = _mk("Crossover Veteran", 800, 2001, [1990, 2000], starts=50)
    veteran["seasons"].append({"y": 1994, "team": "X", "gp": 60, "pts": 9,
                               "reb": 3, "ast": 2, "stl": 0, "blk": 0})
    out = {p["name"]: p for p in classify([starter, veteran], **THRESHOLDS)}
    assert out["Crossover Starter"]["answer"] is True
    assert out["Crossover Veteran"]["answer"] is True
