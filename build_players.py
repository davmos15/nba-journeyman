#!/usr/bin/env python3
"""Journeyman — NBA dataset builder.

Fetches per-season player stats from nba_api (official stats.nba.com) and writes
the season-aggregated players.json the game consumes. One call per season (~45
total) rather than per-player — far fewer requests.

Two endpoints, because stats.nba.com's coverage differs by era:
  * 1996-97 → present : LeagueDashPlayerStats (full rosters, every player).
  * 1980-81 → 1995-96 : LeagueLeaders (this is the earliest per-season endpoint
    that reaches back to 1980; it returns only *qualified* players — those
    meeting the season games/minutes minimum — so deep-bench or injury-shortened
    seasons before 1996-97 may be missing. Acceptable: pre-1996 we mostly want
    recognisable players anyway, and PLAYER_ID matches across both endpoints so
    a career spanning the 1996 boundary merges correctly.)

Run:  python3 build_players.py players.json

Season year stored (`y`) = season END year (1996-97 -> 1997), matching
Basketball-Reference. Both endpoints return one row per player per season, so a
traded player's row carries the endpoint's team assignment for that season.
"""
import sys, json, os, time
from datetime import date
from nba_api.stats.endpoints import leaguedashplayerstats, leagueleaders
from journeyman_build import assemble_player, classify

OUT = sys.argv[1] if len(sys.argv) > 1 else "players.json"

# Tunables -------------------------------------------------------------
START_SEASON_YEAR = 1980   # first season's starting year -> "1980-81"
DASH_START_YEAR   = 1996   # seasons starting >= this use LeagueDashPlayerStats
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


def _retry(fn, label):
    """Call fn() with retries — stats.nba.com intermittently times out / blocks."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - network flakiness
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {label}: {last_err}")


def fetch_rows(season):
    """Yield normalized per-season record dicts for one season, choosing the
    endpoint by era. Keys: y, team, gp, pts, reb, ast, stl, blk (+ _pid, _name)."""
    start_year = int(season[:4])
    end_year = start_year + 1
    if start_year >= DASH_START_YEAR:
        df = _retry(lambda: leaguedashplayerstats.LeagueDashPlayerStats(
            season=season, per_mode_detailed="PerGame",
            season_type_all_star="Regular Season", timeout=60,
        ).get_data_frames()[0], season)
        name_col, team_col = "PLAYER_NAME", "TEAM_ABBREVIATION"
    else:
        df = _retry(lambda: leagueleaders.LeagueLeaders(
            season=season, per_mode48="PerGame",
            season_type_all_star="Regular Season",
            stat_category_abbreviation="PTS", timeout=60,
        ).get_data_frames()[0], season)
        name_col, team_col = "PLAYER", "TEAM"
    for _, row in df.iterrows():
        yield {
            "_pid": int(row["PLAYER_ID"]),
            "_name": str(row[name_col]),
            "y": end_year,
            "team": str(row[team_col]),
            "gp": int(row["GP"]),
            "pts": round(float(row["PTS"]), 1),
            "reb": round(float(row["REB"]), 1),
            "ast": round(float(row["AST"]), 1),
            "stl": round(float(row["STL"]), 1),
            "blk": round(float(row["BLK"]), 1),
        }


def main():
    per_player = {}  # pid -> {"name":..., "records":[...]}
    for season in season_strings():
        print("Fetching", season, "…", flush=True)
        for rec in fetch_rows(season):
            pid = rec.pop("_pid")
            name = rec.pop("_name")
            slot = per_player.setdefault(pid, {"name": name, "records": []})
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
