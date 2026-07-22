import json, os, pytest

DATA = "players.json"
pytestmark = pytest.mark.skipif(not os.path.exists(DATA), reason="players.json not built")

def load():
    return json.load(open(DATA, encoding="utf-8"))

def test_nonempty_and_has_answers():
    players = load()
    assert len(players) > 200
    answers = [p for p in players if p.get("answer")]
    assert len(answers) > 100

def test_answer_players_have_seasons():
    for p in load():
        if p.get("answer"):
            assert p.get("seasons"), p["name"]
            s = p["seasons"][0]
            assert set(s) >= {"y", "team", "gp", "pts", "reb", "ast", "stl", "blk"}

def test_every_decade_has_a_pool():
    answers = [p for p in load() if p.get("answer")]
    for d in (1980, 1990, 2000, 2010, 2020):
        pool = [p for p in answers if d in p.get("decades", [])]
        assert len(pool) >= 20, f"decade {d} only has {len(pool)} answerable players"

def test_years_within_range():
    for p in load():
        assert 1981 <= p["first"] <= p["last"] <= 2027
