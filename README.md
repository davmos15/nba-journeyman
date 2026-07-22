# Journeyman — NBA

Guess the mystery NBA player from their career, one season at a time. Daily
**All-Time** puzzle plus per-**decade** puzzles (80s / 90s / 2000s / 2010s /
2020s), unlimited practice, normal/hard modes, share grid, per-mode stats.
Single static site, no backend.

**Data coverage:** NBA seasons **1980-81 → present** (each season is shown by its
end year, e.g. `1997` = the 1996-97 season).

## Files

| File | What it is |
|---|---|
| `index.html` | The whole game. Loads `players.json` at runtime; falls back to an embedded ~50-player set (spanning every decade) if the fetch fails. |
| `players.json` | Generated dataset, season-by-season. |
| `journeyman_build.py` | Pure build helpers (position, decades, assembly, pools) — unit-tested. |
| `build_players.py` | Fetches from `nba_api` and writes `players.json`. |
| `test_journeyman_build.py`, `test_players_json.py` | pytest suites for the builder and the data contract. |
| `.github/workflows/refresh-data.yml` | Weekly auto-refresh of `players.json`. |
| `netlify.toml` | Static publish config. |
| `requirements.txt` | Python deps for the builder/tests. |

## Configure before launch

Near the top of the `<script>` in `index.html` there's a **SITE CONFIG** block
with `COFFEE_URL` (carried over from the AFL version — **confirm it points at
your Buy Me a Coffee link** before launch). The ☕ button and the About panel
use it.

## Run locally

Because the game fetches `players.json`, open it through a server, not `file://`:

```bash
python -m http.server 8000   # then visit http://localhost:8000
```

Opening `index.html` directly still works — it just uses the smaller embedded
fallback set.

## Modes

- **All-Time** — daily player drawn from all 1980-present answerable players.
- **Decades** — pick 80s / 90s / 2000s / 2010s / 2020s; each is its own daily
  puzzle. A player belongs to a decade if they played **3+ seasons** in it, so
  stars can appear in more than one decade. The full career is still revealed —
  the decade only restricts which players can be the answer.
- **Practice** — unlimited random players from the currently selected pool.

Each daily variant keeps its own stats, streak, and share text.

## Rebuild the data

```bash
pip install -r requirements.txt
python build_players.py players.json
pytest -q
```

The builder uses two `nba_api` endpoints because stats.nba.com's coverage
differs by era:

- **1996-97 → present:** `LeagueDashPlayerStats` (full rosters).
- **1980-81 → 1995-96:** `LeagueLeaders` — the earliest per-season endpoint that
  reaches back to 1980. It returns only *qualified* players (those meeting the
  season games/minutes minimum), so deep-bench or injury-shortened seasons before
  1996-97 may be missing and early-career games can be slightly undercounted.
  `PLAYER_ID` matches across both endpoints, so a career spanning the 1996
  boundary merges correctly.

> **Note:** stats.nba.com sometimes rate-limits or blocks automated/cloud IPs.
> The committed `players.json` means the live site never depends on the API — if
> a scheduled refresh fails, run the builder locally and commit the result.

## Tuning the pool

Edit the constants at the top of `build_players.py`:

| Constant | Effect |
|---|---|
| `ANSWER_MIN_GAMES` | Career games needed to be a possible mystery answer. Raise it to make daily answers more famous. |
| `GUESS_MIN_GAMES` | Career games needed to appear in autocomplete. |
| `START_SEASON_YEAR` / `DASH_START_YEAR` | Era coverage and the endpoint-split boundary. |

**Position** is inferred from the career per-game stat profile (`infer_pos` in
`journeyman_build.py`) into coarse **GUARD / WING / BIG** buckets — the same
heuristic philosophy as the AFL original. It only drives a late clue; hand-
override any player by editing `players.json`.

## Deploy (Netlify)

Static publish: build command *(blank)*, publish directory `.`. Every push
auto-deploys. The included GitHub Action rebuilds `players.json` weekly and
commits only if something changed (enable Actions write access: repo Settings →
Actions → General → Workflow permissions → Read and write).

## Attribution

Player statistics via [NBA.com](https://www.nba.com/stats) through
[nba_api](https://github.com/swar/nba_api). Not affiliated with the NBA. No team
logos, player photos, or league marks are used.
