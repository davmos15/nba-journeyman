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
