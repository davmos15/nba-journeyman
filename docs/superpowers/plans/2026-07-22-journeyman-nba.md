# Journeyman — NBA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an NBA copy of the AFL "Journeyman" daily guessing game, adding an All-Time daily game and per-decade (80s/90s/2000s/2010s/2020s) daily games.

**Architecture:** Single static site — one `index.html` (all logic + styles + a small embedded fallback set) reading a generated `players.json`. A Python builder (`build_players.py`) fetches season data from `nba_api` via testable, network-free helper functions in `journeyman_build.py`. Frontend has no unit-test harness (mirroring the AFL original, which is a single static file), so frontend tasks are verified in a browser; the Python builder and the `players.json` data contract get automated tests.

**Tech Stack:** Static HTML/CSS/vanilla JS; Python 3 + `nba_api` + `pandas` for the builder; `pytest` for builder tests; Netlify static hosting; GitHub Actions for weekly data refresh.

**Source reference:** The AFL original is cloned at `C:\Users\davmo\Desktop\Coding\git\footy-journeyman-src` (files: `index.html`, `players.json`, `build_players.py`, `netlify.toml`, `.github/workflows/refresh-data.yml`, `README.md`). Read it alongside this plan — most frontend tasks are transformations of identified functions in that `index.html`.

**Target repo:** `C:\Users\davmo\Desktop\Coding\git\journeyman-nba` (currently contains only `docs/`).

**Key data-model change (per season):** AFL `{y, club, g, gl, b, d, m, h}` → NBA `{y, team, gp, pts, reb, ast, stl, blk}`. Per-player: AFL `{name,pos,first,last,clubs,games,goals,answer,seasons}` → NBA `{name,pos,first,last,teams,games,points,decades,answer,seasons}`. Season year `y` = season **end year** (1996-97 → 1997), Basketball-Reference convention.

---

## Task 1: Scaffold repo & copy static assets

**Files:**
- Create: `.gitignore`, `requirements.txt`
- Copy from AFL src: `netlify.toml`
- Create dir: `.github/workflows/`

- [ ] **Step 1: Init git repo**

Run:
```bash
cd "C:\Users\davmo\Desktop\Coding\git\journeyman-nba"
git init
```
Expected: `Initialized empty Git repository`.

- [ ] **Step 2: Create `.gitignore`**

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.rda
```

- [ ] **Step 3: Copy `netlify.toml` from AFL src (change cache path comment only — file is identical)**

`netlify.toml`:
```toml
# Static site — nothing to build, just publish the folder.
[build]
  publish = "."
  command = ""

[[headers]]
  for = "/players.json"
  [headers.values]
    Cache-Control = "public, max-age=3600"
```

- [ ] **Step 4: Create `requirements.txt`**

`requirements.txt`:
```
nba_api>=1.4
pandas>=2.0
pytest>=8.0
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt netlify.toml
git commit -m "chore: scaffold journeyman-nba repo"
```

---

## Task 2: Builder helper module (`journeyman_build.py`) — TDD

Pure, network-free functions the builder and tests share. This is where position inference, decade tagging, primary-team selection, and player assembly live.

**Files:**
- Create: `journeyman_build.py`
- Test: `test_journeyman_build.py`

- [ ] **Step 1: Write the failing test**

`test_journeyman_build.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_journeyman_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'journeyman_build'`.

- [ ] **Step 3: Write the implementation**

`journeyman_build.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_journeyman_build.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add journeyman_build.py test_journeyman_build.py
git commit -m "feat: builder helpers (position, decades, assembly) with tests"
```

---

## Task 3: `classify` — answer/guess pools — TDD

Splits players into the mystery-answer pool and the broader guess pool, and trims `seasons` from guess-only players to keep the file small (AFL trick). Per-decade answerability is derived from `decades` + the answer flag at runtime in the frontend, so `classify` only needs a global answer flag.

**Files:**
- Modify: `journeyman_build.py`
- Modify: `test_journeyman_build.py`

- [ ] **Step 1: Write the failing test**

Append to `test_journeyman_build.py`:
```python
from journeyman_build import classify

def _mk(name, games, last, decades):
    return {"name": name, "pos": "WING", "first": last-3, "last": last,
            "teams": ["X"], "games": games, "points": games*10,
            "decades": decades, "seasons": [{"y": last, "team": "X", "gp": 1,
            "pts": 1, "reb": 1, "ast": 1, "stl": 0, "blk": 0}]}

def test_classify_flags_and_trims():
    players = [
        _mk("Star", 900, 2015, [2010]),      # answerable
        _mk("Journeyman", 200, 2015, [2010]),# guess-only
        _mk("Scrub", 20, 2015, [2010]),      # dropped entirely
    ]
    out = classify(players, answer_min_games=400, guess_min_games=100)
    names = {p["name"]: p for p in out}
    assert "Scrub" not in names
    assert names["Star"]["answer"] is True
    assert "seasons" in names["Star"]
    assert names["Journeyman"]["answer"] is False
    assert "seasons" not in names["Journeyman"]  # trimmed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_journeyman_build.py::test_classify_flags_and_trims -v`
Expected: FAIL — `ImportError: cannot import name 'classify'`.

- [ ] **Step 3: Implement `classify`**

Append to `journeyman_build.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_journeyman_build.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add journeyman_build.py test_journeyman_build.py
git commit -m "feat: classify answer/guess pools with season trimming"
```

---

## Task 4: `build_players.py` CLI (nba_api fetch)

> **Implementation note (deviation from original code block below):** `LeagueDashPlayerStats` only returns data from **1996-97 onward** (empty frames for older seasons). The builder therefore uses a **hybrid**: `LeagueDashPlayerStats` for 1996-97→present and **`LeagueLeaders` (PerGame)** for 1980-81→1995-96 (earliest per-season endpoint reaching back to 1980; qualified players only). `PLAYER_ID` matches across both endpoints so cross-era careers merge. See the committed `build_players.py` for the actual hybrid implementation (`fetch_rows` dispatches by era; `DASH_START_YEAR = 1996`).

Thin CLI: fetch per-season league stats from `nba_api`, normalize to per-season records, group by player, call the Task 2/3 helpers, write `players.json`. Network-dependent, so it is not unit-tested; it is exercised by a real run in Task 5.

**Files:**
- Create: `build_players.py`

- [ ] **Step 1: Write `build_players.py`**

`build_players.py`:
```python
#!/usr/bin/env python3
"""Journeyman — NBA dataset builder.

Fetches per-season player stats from nba_api (official stats.nba.com) and writes
the season-aggregated players.json the game consumes. One LeagueDashPlayerStats
call per season (~45 total) rather than per-player — far fewer requests.

Run:  python3 build_players.py players.json

Season year stored (`y`) = season END year (1996-97 -> 1997), matching
Basketball-Reference. Traded players: this endpoint returns one combined row per
player per season, so the team shown is the endpoint's assignment for that season.
"""
import sys, json, os, time
from datetime import date
from nba_api.stats.endpoints import leaguedashplayerstats
from journeyman_build import assemble_player, classify

OUT = sys.argv[1] if len(sys.argv) > 1 else "players.json"

# Tunables -------------------------------------------------------------
START_SEASON_YEAR = 1980   # first season's starting year -> "1980-81"
ANSWER_MIN_GAMES  = 400    # career games to be a possible mystery answer
GUESS_MIN_GAMES   = 100    # career games to appear in autocomplete
REQUEST_PAUSE     = 0.6    # polite delay between season calls (seconds)
MAX_RETRIES       = 4


def season_strings(start_year=START_SEASON_YEAR):
    today = date.today()
    # An NBA season starting in year Y ends ~June Y+1. Latest fully-startable
    # season start year: this year if we're past September, else last year.
    last_start = today.year if today.month >= 10 else today.year - 1
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(start_year, last_start + 1)]


def fetch_season(season):
    """Return the LeagueDashPlayerStats PerGame dataframe for one season, with
    retries — stats.nba.com intermittently times out / rate-limits."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            ep = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                per_mode_detailed="PerGame",
                season_type_all_star="Regular Season",
                timeout=60,
            )
            return ep.get_data_frames()[0]
        except Exception as e:  # noqa: BLE001 - network flakiness
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {season}: {last_err}")


def main():
    per_player = {}  # pid -> {"name":..., "records":[...]}
    for season in season_strings():
        end_year = int(season[:4]) + 1
        print("Fetching", season, "…", flush=True)
        df = fetch_season(season)
        for _, row in df.iterrows():
            pid = int(row["PLAYER_ID"])
            rec = {
                "y": end_year,
                "team": str(row["TEAM_ABBREVIATION"]),
                "gp": int(row["GP"]),
                "pts": round(float(row["PTS"]), 1),
                "reb": round(float(row["REB"]), 1),
                "ast": round(float(row["AST"]), 1),
                "stl": round(float(row["STL"]), 1),
                "blk": round(float(row["BLK"]), 1),
            }
            slot = per_player.setdefault(pid, {"name": str(row["PLAYER_NAME"]), "records": []})
            slot["records"].append(rec)
        time.sleep(REQUEST_PAUSE)

    players = [assemble_player(v["name"], v["records"]) for v in per_player.values()]

    # disambiguate duplicate display names (rare) by first team + debut year
    name_counts = {}
    for p in players:
        name_counts[p["name"]] = name_counts.get(p["name"], 0) + 1
    for p in players:
        if name_counts[p["name"]] > 1:
            p["name"] = f'{p["name"]} ({p["teams"][0]}, {p["first"]})'

    kept = classify(players, ANSWER_MIN_GAMES, GUESS_MIN_GAMES)
    kept.sort(key=lambda p: -p["games"])
    answers = [p for p in kept if p["answer"]]
    print(f"{len(kept)} guessable, {len(answers)} answerable")

    # sanity: report per-decade answerable counts
    from collections import Counter
    dc = Counter(d for p in answers for d in p["decades"])
    print("answerable per decade:", dict(sorted(dc.items())))

    json.dump(kept, open(OUT, "w"), separators=(",", ":"))
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Byte-compile check (no network)**

Run: `python -c "import ast; ast.parse(open('build_players.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add build_players.py
git commit -m "feat: nba_api dataset builder CLI"
```

---

## Task 5: Generate `players.json` + data-contract test

**Files:**
- Create: `players.json` (generated)
- Test: `test_players_json.py`

- [ ] **Step 1: Install deps and run the builder**

Run:
```bash
pip install -r requirements.txt
python build_players.py players.json
```
Expected: prints per-season "Fetching …" lines, then `N guessable, M answerable`, an `answerable per decade:` line with all of 1980/1990/2000/2010/2020 present, and `wrote players.json (… KB)`.

> **If stats.nba.com blocks the request** (common on cloud/CI IPs): run from the local Windows machine (residential IP usually works). If it still fails, increase `REQUEST_PAUSE`/`MAX_RETRIES`. Do not fabricate data — the data-contract test below must run against a real `players.json`.

- [ ] **Step 2: Write the data-contract test**

`test_players_json.py`:
```python
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
```

- [ ] **Step 3: Run the contract test**

Run: `pytest test_players_json.py -v`
Expected: PASS. If `test_every_decade_has_a_pool` fails for the 2020s (short decade), lower `ANSWER_MIN_GAMES` in `build_players.py`, rebuild, and re-run.

- [ ] **Step 4: Commit**

```bash
git add players.json test_players_json.py
git commit -m "feat: generate players.json + data-contract test"
```

---

## Task 6: `index.html` base copy — branding, copy, table headers

Bring the AFL `index.html` over and make the non-logic cosmetic changes. Logic changes come in later tasks.

**Files:**
- Create: `index.html` (copy of `footy-journeyman-src/index.html`, then edit)

- [ ] **Step 1: Copy the AFL index.html verbatim**

Run:
```bash
cp "C:\Users\davmo\Desktop\Coding\git\footy-journeyman-src\index.html" "C:\Users\davmo\Desktop\Coding\git\journeyman-nba\index.html"
```

- [ ] **Step 2: Title & headline copy**

- Line ~6 `<title>`: `Journeyman — Footy` → `Journeyman — NBA`.
- About/help text (~lines 290–296): replace AFL phrasing:
  - "A mystery player's **career record** is revealed one season at a time…" (keep).
  - "shared club, position, and whether…" → "shared team, position, and whether…".
  - "**Normal:** 8 guesses. **Hard mode:** 5 guesses, teams hidden, no clue chips."
  - "One daily player for everyone…" → "Daily All-Time and per-decade games, or Practice for unlimited random players."

- [ ] **Step 3: Table headers (thead, ~lines 250–258)**

Replace the AFL columns (Year/Club/Games/Goals/Behinds/Disposals/Marks/Hit-outs) with:
```html
<th data-info="The season (shown by its end year, e.g. 1997 = 1996-97)." title="Season (end year).">Year</th>
<th data-info="Team that season (tap for full name)." title="Team that season.">Team</th>
<th data-info="Games played that season." title="Games played that season."><span class="hlong">Games</span><span class="hshort">GP</span></th>
<th data-info="Points per game that season." title="Points per game."><span class="qual">avg</span><span class="hlong">Points</span><span class="hshort">PPG</span></th>
<th data-info="Rebounds per game that season." title="Rebounds per game."><span class="qual">avg</span><span class="hlong">Rebounds</span><span class="hshort">RPG</span></th>
<th data-info="Assists per game that season." title="Assists per game."><span class="qual">avg</span><span class="hlong">Assists</span><span class="hshort">APG</span></th>
<th data-info="Steals per game that season." title="Steals per game."><span class="qual">avg</span><span class="hlong">Steals</span><span class="hshort">SPG</span></th>
<th data-info="Blocks per game that season." title="Blocks per game."><span class="qual">avg</span><span class="hlong">Blocks</span><span class="hshort">BPG</span></th>
```
(Eight columns → matches the eight season fields. Keep the existing `qual`/`hlong`/`hshort` span classes.)

- [ ] **Step 4: Attribution & COFFEE_URL**

- COFFEE_URL (~line 354): leave the existing value (carried over from AFL).
- Footer/attribution (~lines 768–770): replace the AFL Tables/fitzRoy credit with:
```js
$("dataYears").innerHTML = POOL.length + " players · seasons " + lo + "–" + hi +
  '<br>Stats via <a href="https://www.nba.com/stats" target="_blank" rel="noopener">NBA.com</a> ' +
  '(<a href="https://github.com/swar/nba_api" target="_blank" rel="noopener">nba_api</a>). Not affiliated with the NBA.';
```

- [ ] **Step 5: Verify it loads (fallback set still AFL — replaced in Task 10)**

Run:
```bash
python -m http.server 8000
```
Open `http://localhost:8000`. Expected: page renders with NBA title and the new column headers. (Data/logic still AFL-shaped — full behaviour verified after later tasks.) Stop the server.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat: NBA branding, copy, and stat table headers"
```

---

## Task 7: `index.html` — NBA team colours, abbreviations, season fields

Swap AFL club colours/abbreviations for NBA teams and rename the per-season data fields throughout the render path.

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Replace `CLUB_COLOURS` / `CLUB_ABBR` with NBA maps (~lines 358–373)**

Replace the AFL `CLUB_COLOURS` object and `CLUB_ABBR`/`clubAbbr` with NBA equivalents keyed by the 3-letter abbreviation the data uses (`TEAM_ABBREVIATION`). Because the data already stores abbreviations as `team`, the abbreviation map is identity and only colours are needed:
```js
const TEAM_COLOURS = {
  ATL:"#E03A3E", BOS:"#007A33", BKN:"#000000", CHA:"#1D1160", CHI:"#CE1141",
  CLE:"#860038", DAL:"#00538C", DEN:"#0E2240", DET:"#C8102E", GSW:"#1D428A",
  HOU:"#CE1141", IND:"#002D62", LAC:"#C8102E", LAL:"#552583", MEM:"#5D76A9",
  MIA:"#98002E", MIL:"#00471B", MIN:"#0C2340", NOP:"#0C2340", NYK:"#006BB6",
  OKC:"#007AC1", ORL:"#0077C0", PHI:"#006BB6", PHX:"#1D1160", POR:"#E03A3E",
  SAC:"#5A2D81", SAS:"#C4CED4", TOR:"#CE1141", UTA:"#002B5C", WAS:"#002B5C",
  // legacy/relocated franchises that appear in 1980-present data
  SEA:"#00653A", VAN:"#00B2A9", NJN:"#002A60", CHH:"#00778B", NOH:"#0C2340",
  NOK:"#0C2340", WSB:"#002B5C", SDC:"#C8102E", KCK:"#5A2D81", PHW:"#006BB6",
};
const teamAbbr = t => t; // data already stores abbreviations
```

- [ ] **Step 2: Rename `clubCell` → `teamCell` and update it (~lines 468–472)**

```js
function teamCell(team, hard, hardIdx){
  if (hard) return '<span class="clubdot" style="background:var(--line)"></span>Team ' + String.fromCharCode(65+hardIdx);
  const c = TEAM_COLOURS[team] || "#666";
  return '<span class="clubdot" style="background:'+c+'"></span><span title="'+team+'">' + teamAbbr(team) + '</span>';
}
```

- [ ] **Step 3: Update `render()` season-row cells (~lines 480–505)**

In `render()`, the AFL code reads `s.club`, `s.g`, `s.gl`, `s.b`, `s.d`, `s.m`, `s.h` and calls `clubCell`. Change the season variable `s` cell output to the NBA fields and the eight columns from Task 6:
```js
'<td>' + s.y + '</td>' +
'<td>' + teamCell(s.team, G.hard, clubOrder.indexOf(s.team)) + '</td>' +
'<td>' + s.gp + '</td>' +
'<td>' + s.pts.toFixed(1) + '</td>' +
'<td>' + s.reb.toFixed(1) + '</td>' +
'<td>' + s.ast.toFixed(1) + '</td>' +
'<td>' + s.stl.toFixed(1) + '</td>' +
'<td>' + s.blk.toFixed(1) + '</td>'
```
Also rename the `clubOrder` array build (~line 476–477) to track `s.team` instead of `s.club`:
```js
const clubOrder = [];
seasons.forEach(s => { if(!clubOrder.includes(s.team)) clubOrder.push(s.team); });
```

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: NBA team colours and per-season stat fields in render"
```

---

## Task 8: `index.html` — data model, clues, career blurb

Update the data-load, clue chips, autocomplete blurb, and result-sheet text for the NBA fields (`teams`, `points`, `team`, position clue "shared team").

**Files:**
- Modify: `index.html`

- [ ] **Step 1: `careerBlurb` (~line 400)**

```js
function careerBlurb(p){ return p.games+' games · '+p.points.toLocaleString()+' pts · '+p.first+'–'+p.last; }
```

- [ ] **Step 2: `renderChips` — shared team clue (~lines 528–541)**

The AFL version uses `guessed.clubs` and `a.seasons.map(s=>s.club)`. Update to NBA `teams`/`team`:
```js
function renderChips(guessed){
  if (G.hard){ chipsEl.innerHTML=""; return; }
  const a = G.player;
  const aTeams = new Set(a.seasons.map(s=>s.team));
  const shared = (guessed.teams||[]).some(t => aTeams.has(t));
  const samePos = guessed.pos === a.pos;
  const aDebut = a.seasons[0].y;
  const dir = aDebut === guessed.first ? "same year" :
              (aDebut > guessed.first ? "debuted later ↓" : "debuted earlier ↑");
  chipsEl.innerHTML =
    '<span class="chip '+(shared?'yes':'no')+'">'+(shared?'✔':'✘')+' shared team</span>' +
    '<span class="chip '+(samePos?'yes':'no')+'">'+(samePos?'✔':'✘')+' position</span>' +
    '<span class="chip">vs your guess: '+dir+'</span>';
}
```

- [ ] **Step 3: Result sheet uses `pos` + blurb (already generic)**

Confirm `showResult` line `$("resCareer").textContent = p.pos+" · "+careerBlurb(p);` needs no change (positions now GUARD/WING/BIG, blurb updated). No edit required — just verify.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: NBA data model in clues and career blurb"
```

---

## Task 9: `index.html` — mode system (All-Time + decades + practice)

The core new logic. Generalize the single "daily/practice" mode into: a `modeKey` (`alltime` / `d1980` / `d1990` / `d2000` / `d2010` / `d2020`) plus an `isDaily` flag, per-mode answer pools, per-mode daily seeds, per-mode saved state and stats, and a tab UI with a decade picker.

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Tab markup — replace the two AFL tabs (~lines 239–240)**

Replace:
```html
<button class="tab on" id="tabDaily">Daily<span class="sub" id="dailyNo">#1</span></button>
<button class="tab" id="tabPractice">Practice<span class="sub">unlimited</span></button>
```
with:
```html
<button class="tab on" id="tabAll">All-Time<span class="sub" id="dailyNo">#1</span></button>
<button class="tab" id="tabDecades">Decades<span class="sub" id="decadeSub">pick</span></button>
<button class="tab" id="tabPractice">Practice<span class="sub">unlimited</span></button>
</div>
<div class="decadebar" id="decadeBar" style="display:none">
  <button class="dchip" data-d="1980">80s</button>
  <button class="dchip" data-d="1990">90s</button>
  <button class="dchip" data-d="2000">2000s</button>
  <button class="dchip" data-d="2010">2010s</button>
  <button class="dchip" data-d="2020">2020s</button>
```
(The trailing `</div>` closes the existing `.tabs` row; the new `.decadebar` sits directly under it. Add matching CSS near the `.tab` styles: `.decadebar{display:flex;gap:6px;justify-content:center;margin:6px 0}` and `.dchip{padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--felt2);color:var(--dim);font-size:12px}` and `.dchip.on{color:var(--fg);border-color:var(--accent)}`.)

- [ ] **Step 2: Mode constants + pool helper (add near `let ANSWERS = []`, ~line 387)**

```js
const DECADES = [1980,1990,2000,2010,2020];
const DECADE_LABELS = {1980:"80s",1990:"90s",2000:"2000s",2010:"2010s",2020:"2020s"};
let currentMode = "alltime";   // active modeKey
let isDailyMode = true;        // daily vs practice within the active pool

function poolFor(modeKey){
  if (modeKey === "alltime") return ANSWERS;
  const d = parseInt(modeKey.slice(1),10);
  return ANSWERS.filter(p => (p.decades||[]).includes(d));
}
function modeLabel(modeKey){
  return modeKey === "alltime" ? "All-Time" : DECADE_LABELS[parseInt(modeKey.slice(1),10)];
}
// stable per-mode salt so each mode's daily picks a different player & order
function modeSalt(modeKey){
  let h = 2166136261 >>> 0;
  for (let i=0;i<modeKey.length;i++){ h ^= modeKey.charCodeAt(i); h = Math.imul(h,16777619) >>> 0; }
  return h >>> 0;
}
```

- [ ] **Step 3: Per-mode daily selection + `newGame` (replace ~lines 414–462)**

Keep `dailyIndex()`, `seededRng()`, `shuffledOrder()` unchanged. Replace `dailyPlayerIdx` and `newGame`:
```js
function dailyPlayerIdx(n, pool, salt){
  let x = ((n * 2654435761) >>> 0) ^ (salt >>> 0);
  x = ((x >>> 13) ^ x) >>> 0;
  return x % pool.length;
}
function todayKey(modeKey){ return "daily-" + modeKey + "-" + dailyIndex(); }

function newGame(modeKey, isDaily){
  const pool = poolFor(modeKey);
  const salt = modeSalt(modeKey);
  let idx;
  if (isDaily){
    idx = dailyPlayerIdx(dailyIndex(), pool, salt);
  } else {
    idx = Math.floor(Math.random()*pool.length);
    if (G && pool[idx].name === G.player.name) idx = (idx+1) % pool.length;
  }
  const player = pool[idx];
  const rand = isDaily ? seededRng((((dailyIndex()*2654435761) >>> 0) ^ 0x9e3779b9 ^ salt) >>> 0) : Math.random;
  const revealOrder = shuffledOrder(player.seasons.length, rand);
  return {
    modeKey, isDaily, hard: settings.hard, player,
    maxGuesses: settings.hard ? HARD_GUESSES : NORMAL_GUESSES,
    guesses: [], revealed: 1, over:false, won:false, revealOrder
  };
}
```

- [ ] **Step 4: Per-mode stats (replace the single `stats` object, ~line 411)**

```js
let allStats = {}; // modeKey -> {played,wins,streak,maxStreak,dist}
function statsFor(k){
  return allStats[k] || (allStats[k] = {played:0, wins:0, streak:0, maxStreak:0, dist:{}});
}
```
In `finishGame` (~lines 618–631) replace the `G.mode === "daily"` block:
```js
if (G.isDaily){
  const already = await sGet(todayKey(G.modeKey));
  if (!already){
    const st = statsFor(G.modeKey);
    st.played++;
    if (G.won){
      st.wins++; st.streak++; st.maxStreak = Math.max(st.maxStreak, st.streak);
      st.dist[G.guesses.length] = (st.dist[G.guesses.length]||0)+1;
    } else st.streak = 0;
    await sSet("stats", allStats);
    await sSet(todayKey(G.modeKey), {won:G.won, n:G.guesses.length, hard:G.hard, guesses:G.guesses});
  }
}
```
In `init` (~line 762) load per-mode stats: `const st = await sGet("stats"); if (st) allStats = st;`
In `renderStats` (~lines 698–706) read `const stats = statsFor(currentMode);` at the top so the stats panel reflects the active mode. Update the panel heading "GUESS DISTRIBUTION (DAILY)" to include `modeLabel(currentMode)`.

- [ ] **Step 5: `metaRight`, `showResult`, `shareText` per mode**

- `metaRight` (~line 509):
```js
$("metaRight").innerHTML = G.hard ? '<b>HARD</b>' : (G.isDaily ? (modeLabel(G.modeKey).toUpperCase()+' <b>#'+(dailyIndex()+1)+'</b>') : 'PRACTICE');
```
- `showResult` resTag (~line 637):
```js
$("resTag").textContent = G.isDaily ? ("JOURNEYMAN NBA — "+modeLabel(G.modeKey)+" #"+(dailyIndex()+1)) : "PRACTICE";
```
- `shareText` (~lines 651–657):
```js
function shareText(){
  const n = G.won ? G.guesses.length : "X";
  const grid = G.guesses.map(g => g.skip ? "⬜" : (g.correct ? "🟩" : "🟥")).join("");
  const label = G.isDaily ? (modeLabel(G.modeKey)+" #"+(dailyIndex()+1)) : "practice";
  const url = shareUrl();
  return "Journeyman NBA — "+label+" "+n+"/"+G.maxGuesses+(G.hard?" (hard)":"")+"\n"+grid+
    (url ? "\n🏀 Play: "+url : "\n🏀 playjourneyman");
}
```

- [ ] **Step 6: `startGame` + tab wiring (replace ~lines 736–756)**

```js
const tabAll = $("tabAll"), tabDecades = $("tabDecades"), tabPractice = $("tabPractice");
const decadeBar = $("decadeBar");

function updateTabs(){
  tabAll.classList.toggle("on", isDailyMode && currentMode==="alltime");
  tabDecades.classList.toggle("on", isDailyMode && currentMode!=="alltime");
  tabPractice.classList.toggle("on", !isDailyMode);
  decadeBar.style.display = (currentMode!=="alltime" || tabDecades.classList.contains("open")) ? "flex" : "none";
  document.querySelectorAll(".dchip").forEach(c =>
    c.classList.toggle("on", currentMode === "d"+c.dataset.d));
  $("decadeSub").textContent = currentMode==="alltime" ? "pick" : DECADE_LABELS[parseInt(currentMode.slice(1),10)];
}

async function startGame(modeKey, isDaily){
  currentMode = modeKey; isDailyMode = isDaily;
  updateTabs();
  chipsEl.innerHTML = "";
  if (isDaily){
    const done = await sGet(todayKey(modeKey));
    if (done){
      G = newGame(modeKey, true);
      G.hard = done.hard; G.maxGuesses = done.hard?HARD_GUESSES:NORMAL_GUESSES;
      G.guesses = done.guesses || []; G.over = true; G.won = done.won; G.revealed = 999;
      render(); return;
    }
  }
  G = newGame(modeKey, isDaily);
  render();
}

tabAll.addEventListener("click", ()=>startGame("alltime", true));
tabDecades.addEventListener("click", ()=>{
  decadeBar.style.display = "flex";
  // default to 90s the first time; otherwise keep the current decade
  startGame(currentMode!=="alltime" ? currentMode : "d1990", true);
});
tabPractice.addEventListener("click", ()=>startGame(currentMode, false));
document.querySelectorAll(".dchip").forEach(c =>
  c.addEventListener("click", ()=>startGame("d"+c.dataset.d, true)));
```
Also update `$("btnAgain")` (~line 687–690) to restart practice in the current pool: `startGame(currentMode, false);`

- [ ] **Step 7: `init` bootstrap (replace the AFL `await startGame("daily")`, ~line 772)**

```js
$("dailyNo").textContent = "#" + (dailyIndex()+1);
await startGame("alltime", true);
```

- [ ] **Step 8: Verify in browser (uses live players.json)**

Run: `python -m http.server 8000`, open `http://localhost:8000`. Check:
- All-Time daily loads a player; guesses reveal seasons; clue chips say "shared team"/"position".
- Decades tab → decade chips appear; picking 90s starts a 90s daily with a different player.
- Each decade shows `#<n>` and the correct label in the result sheet and share text.
- Practice plays unlimited; refreshing keeps the daily result non-replayable per mode.
- Hard mode hides teams and chips.
Stop the server.

- [ ] **Step 9: Commit**

```bash
git add index.html
git commit -m "feat: All-Time + per-decade + practice mode system"
```

---

## Task 10: `index.html` — embedded NBA fallback set

Replace the AFL embedded `FALLBACK` array (the huge single line ~384) with a small NBA set so the game still works when `players.json` can't be fetched (e.g. opened via `file://`).

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Generate a compact fallback from the real data**

Run:
```bash
python -c "import json; d=json.load(open('players.json',encoding='utf-8')); a=[p for p in d if p.get('answer')][:40]; print('const FALLBACK = '+json.dumps(a,separators=(',',':'))+';')" > _fallback.txt
```
This yields the 40 highest-games answerable players (each with `seasons`), spanning multiple decades.

- [ ] **Step 2: Replace the `FALLBACK` definition**

Find the AFL `const FALLBACK = [ … ];` (line ~384, ~61 KB) and replace the whole statement with the line from `_fallback.txt`. Delete `_fallback.txt` afterward.

- [ ] **Step 3: Verify fallback works**

Open `index.html` directly (double-click / `file://`). Expected: a toast "40 players (offline set)" and All-Time playable. Decade pools may be small but should not error (each decade needs ≥1 answerable in the fallback; if a decade pool is empty, `poolFor` returns `[]` — guard `startGame` to toast "no players for this decade" and stay on the previous game).

- [ ] **Step 4: Add the empty-pool guard in `startGame` (defensive)**

At the top of `newGame`, after `const pool = poolFor(modeKey);`, add:
```js
if (!pool.length){ toast("No players for "+modeLabel(modeKey)+" yet"); return G || newGame("alltime", isDaily); }
```
(Only relevant for the tiny offline set; the real data has full pools.)

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat: NBA embedded fallback set + empty-pool guard"
```

---

## Task 11: README + GitHub Action refresh workflow

**Files:**
- Create: `README.md`
- Create: `.github/workflows/refresh-data.yml`

- [ ] **Step 1: Write `README.md`**

`README.md`:
```markdown
# Journeyman — NBA

Guess the mystery NBA player from their career, one season at a time. Daily
**All-Time** puzzle plus per-**decade** puzzles (80s/90s/2000s/2010s/2020s),
unlimited practice, normal/hard modes, share grid, per-mode stats. Single static
site, no backend.

**Data coverage:** NBA seasons **1980-81 → present** (season shown by end year).

## Files
| File | What it is |
|---|---|
| `index.html` | The whole game. Loads `players.json`; falls back to an embedded ~40-player set if the fetch fails. |
| `players.json` | Generated dataset, season-by-season. |
| `journeyman_build.py` | Pure build helpers (position, decades, assembly, pools) — unit-tested. |
| `build_players.py` | Fetches from nba_api and writes `players.json`. |
| `test_*.py` | pytest suites for the builder and the data contract. |
| `.github/workflows/refresh-data.yml` | Weekly auto-refresh of `players.json`. |
| `netlify.toml` | Static publish config. |

## Run locally
```bash
python -m http.server 8000   # then visit http://localhost:8000
```
Opening `index.html` directly works too (uses the smaller embedded fallback).

## Rebuild the data
```bash
pip install -r requirements.txt
python build_players.py players.json
pytest -q
```

## Modes
- **All-Time** — daily player from all 1980-present answerable players.
- **Decades** — pick 80s/90s/2000s/2010s/2020s; each is its own daily. A player
  belongs to a decade if they played **3+ seasons** in it (so stars appear in
  more than one). The full career is still revealed; the decade only restricts
  which players can be the answer.
- **Practice** — unlimited random players from the selected pool.

## Tuning the pool
Edit constants in `build_players.py`: `ANSWER_MIN_GAMES` (who can be the answer),
`GUESS_MIN_GAMES` (autocomplete). Position is inferred from the career stat
profile (`infer_pos` in `journeyman_build.py`) into coarse GUARD/WING/BIG
buckets — hand-override any player in `players.json`.

## Deploy (Netlify)
Publish directory `.`, no build command. Every push auto-deploys.

## Attribution
Player statistics via [NBA.com](https://www.nba.com/stats) through
[nba_api](https://github.com/swar/nba_api). Not affiliated with the NBA. No team
logos, player photos, or league marks are used.
```

- [ ] **Step 2: Write the refresh workflow**

`.github/workflows/refresh-data.yml`:
```yaml
name: Refresh NBA data
on:
  schedule:
    - cron: "0 9 * * 1"   # Mondays 09:00 UTC
  workflow_dispatch:
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - name: Rebuild players.json
        run: python build_players.py players.json
      - name: Validate data contract
        run: pytest test_players_json.py -q
      - name: Commit if changed
        run: |
          if ! git diff --quiet players.json; then
            git config user.name "github-actions"
            git config user.email "actions@github.com"
            git add players.json
            git commit -m "chore: weekly NBA data refresh"
            git push
          fi
```
> Note in the PR description: stats.nba.com may block GitHub-hosted runners. If the scheduled run fails to fetch, run `build_players.py` locally and push, or move the job to a self-hosted/residential runner. Enable Actions write access: repo Settings → Actions → General → Workflow permissions → Read and write.

- [ ] **Step 3: Commit**

```bash
git add README.md .github/workflows/refresh-data.yml
git commit -m "docs: README and weekly data-refresh workflow"
```

---

## Task 12: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `pytest -q`
Expected: all builder + data-contract tests pass.

- [ ] **Step 2: Browser smoke test across modes**

Run `python -m http.server 8000`. Verify end-to-end:
- All-Time daily: win and lose paths, share text reads `Journeyman NBA — All-Time #N`.
- Each decade (80s→2020s): loads a distinct player; share/label correct; distinct daily state persists independently (finishing 90s doesn't mark 2000s done).
- Practice: unlimited, "Play practice game" restarts in the current pool.
- Hard mode: 5 guesses, teams shown as "Team A/B", no clue chips.
- Stats panel reflects the active mode.
- Offline: open via `file://` → fallback set loads.

- [ ] **Step 3: Confirm no leftover AFL references**

Run: `grep -niE "afl|footy|fitzroy|disposal|hit-?out|goal|behind|brownlow|club" index.html README.md`
Expected: no substantive gameplay references remain (a stray word in unrelated prose is fine; investigate any match). Fix any real leftovers, then commit.

- [ ] **Step 4: Final commit (if fixes were needed)**

```bash
git add -A
git commit -m "chore: verification fixes"
```

---

## Self-review notes (author)

- **Spec coverage:** modes (Task 9), decade rule ≥3 seasons (Task 2 `tag_decades` + Task 5 test), nba_api pipeline (Tasks 4–5), inferred positions like AFL (Task 2 `infer_pos`), per-mode stats/streaks (Task 9 Step 4), team colours & stat line (Tasks 6–7), branding/attribution (Task 6), fallback (Task 10), deploy + weekly refresh (Task 11). All spec sections mapped.
- **Data-model consistency:** season fields `{y,team,gp,pts,reb,ast,stl,blk}` and player fields `{name,pos,first,last,teams,games,points,decades,answer,seasons}` are used identically across the builder (Task 2), the JSON contract test (Task 5), and every `index.html` render/clue path (Tasks 7–9).
- **Naming consistency:** `poolFor`, `modeSalt`, `todayKey(modeKey)`, `statsFor`, `teamCell`, `TEAM_COLOURS`, `currentMode`/`isDailyMode` are defined once (Task 9/7) and referenced consistently.
- **Frontend testing:** no unit harness (matches the AFL single-file original); frontend risk is covered by explicit browser checks (Tasks 9, 10, 12) and the automated data-contract test that guards the interface the frontend depends on.
```
