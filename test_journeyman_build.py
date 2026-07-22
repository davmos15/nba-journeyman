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
        {"y": 1997, "team": "CHI", "gp": 82, "pts": 28.7, "reb": 5.9, "ast": 3.5, "stl": 1.7, "blk": 0.5},
        {"y": 1998, "team": "CHI", "gp": 82, "pts": 28.7, "reb": 5.8, "ast": 3.5, "stl": 1.7, "blk": 0.5},
    ]
    p = assemble_player("Michael Jordan", recs)
    assert p["name"] == "Michael Jordan"
    assert p["first"] == 1996 and p["last"] == 1998
    assert p["teams"] == ["CHI"]
    assert p["games"] == 246
    assert p["pos"] in ("GUARD", "WING", "BIG")
    assert p["decades"] == [1990]
    assert p["seasons"][0]["y"] == 1996  # sorted ascending
    assert "answer" not in p  # answer flag added later by classify step
