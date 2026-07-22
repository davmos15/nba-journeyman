# Journeyman — NBA — Design

**Date:** 2026-07-22
**Source repo:** https://github.com/davmos15/footy-journeyman.git (AFL version)
**Goal:** An almost-identical NBA copy of the AFL "Journeyman" daily guessing game, adding an **All-Time** daily game and per-**decade** daily games (80s / 90s / 2000s / 2010s / 2020s).

---

## 1. Core mechanic (unchanged from AFL)

A single static site. A mystery player's **career is revealed one season at a time in a random (seeded) order**. Each wrong guess reveals another season and shows **clue chips** comparing the guess to the answer: shared team, position match, and whether the answer debuted earlier or later. Fewer seasons revealed = better score.

- **Normal:** 8 guesses. **Hard:** 5 guesses, teams hidden, no clue chips.
- **Daily** puzzle is deterministic (same for everyone on a given date via a seeded index). **Practice** = unlimited random players.
- Share grid, guess-distribution stats, light/dark toggle, About panel — all carried over.
- The live site reads `players.json`; if that fetch fails it falls back to a small embedded player set baked into `index.html`.

## 2. Game modes (the main change vs AFL)

Replace the AFL "Daily / Practice" tabs with three groups:

1. **All-Time** — one daily puzzle drawn from the full 1980–present answer pool.
2. **Decades** — a decade selector (**80s, 90s, 2000s, 2010s, 2020s**); **each decade is its own independent daily puzzle** with its own answer pool.
3. **Practice** — unlimited random players drawn from the currently-selected pool (all-time, or the chosen decade).

Details:
- Each daily variant keeps its **own stats, streak, and guess-distribution**, and its own share text, e.g. `Journeyman NBA — 90s #12`.
- Storage/state keys are **namespaced per mode**: `daily-alltime-N`, `daily-1980-N`, `daily-1990-N`, … All modes share one EPOCH/date calculation, but each uses a **different selection seed** so the modes pick different players on the same day.
- When guessing, the **autocomplete/guess pool is the full guess pool** (you can name any eligible player); only the **answer pool** is restricted per mode.

## 3. Data source & pipeline (`build_players.py`, rewritten for `nba_api`)

- Data source: **`nba_api`** (official stats.nba.com). Coverage **1980-81 season → current**.
- **Two endpoints by era** (stats.nba.com coverage differs): `LeagueDashPlayerStats` (PerGame) only returns data from **1996-97 onward** (it yields empty frames for older seasons). So the builder uses `LeagueDashPlayerStats` for **1996-97 → present** (full rosters) and **`LeagueLeaders` (PerGame)** for **1980-81 → 1995-96** — the earliest per-season endpoint reaching back to 1980. `PLAYER_ID` is consistent across both endpoints, so a career spanning the 1996 boundary merges correctly. Each row gives `PLAYER_ID`, name, team, `GP`, `PTS`, `REB`, `AST`, `STL`, `BLK`. ~46 API calls total.
- **Pre-1996 limitation:** `LeagueLeaders` returns only *qualified* players (those meeting the season games/minutes minimum), so deep-bench or injury-shortened pre-1996 seasons may be missing, and career games for that era can be slightly undercounted. Accepted — pre-1996 we mostly want recognisable players anyway.
- Aggregate by player into a career:
  - `seasons[]` of `{y, team, gp, pts, reb, ast, stl, blk}` (per-game values), sorted by year.
  - `teams[]` (distinct, in order of first appearance), `first`, `last`, career `games`, career `points`.
- **Traded mid-season:** the season row uses the player's **primary team that year** (team with the most games), collapsing to one team per season row — same simplification as the AFL builder.
- **Weekly refresh** via GitHub Action commits an updated `players.json` on change (retries + browser-like User-Agent because stats.nba.com sometimes blocks cloud IPs). The live site never depends on the API — it reads the committed JSON.

### 3a. Position — inferred exactly like the AFL builder

Positions are **heuristic**, derived from the player's **career per-game stat profile** (the AFL builder's `infer_pos` approach, adapted to basketball), not from an API position field. Buckets are deliberately **coarse** to avoid confident-wrong labels: **GUARD / WING / BIG** (roughly: assist-heavy → GUARD, rebound/block-heavy → BIG, otherwise WING). Position only drives a **late clue**, so occasional noise is acceptable, and any player can be **hand-overridden** by editing `players.json`. Exact thresholds are tuned in `build_players.py` constants, mirroring how the AFL version exposes `infer_pos`.

### 3b. Pool tuning constants (mirroring AFL)

- `ANSWER_MIN_GAMES` / notability threshold → who can be the **mystery answer** (keeps answers to recognisable players).
- `GUESS_MIN_GAMES` → who appears in **autocomplete** (broader).
- Both pools live in one array; guess-only players omit `seasons` to keep the file small (same trick as AFL).

### 3c. Decade tagging & membership

- Each player gets `decades: [1980, 1990, ...]` listing **every decade in which they played 3+ seasons** (i.e. *more than 2* seasons). A player can belong to multiple decades (e.g. Jordan → 80s and 90s).
- A decade's **answer pool** = players tagged with that decade **and** meeting the answer-notability threshold. Verify each decade yields a healthy pool (target ≥ 30 answerable players); if a decade is thin, relax its threshold.
- In a decade game the **full career is still revealed** (seasons outside the decade included) — the decade only restricts which players can be the answer, preserving the journeyman feel.

## 4. Data model (`players.json`)

```json
{
  "name": "Michael Jordan",
  "pos": "GUARD",
  "first": 1984,
  "last": 2002,
  "teams": ["CHI", "WAS"],
  "games": 1072,
  "points": 32292,
  "decades": [1980, 1990, 2000],
  "answer": true,
  "seasons": [
    { "y": 1996, "team": "CHI", "gp": 82, "pts": 30.4, "reb": 6.6, "ast": 4.3, "stl": 2.2, "blk": 0.5 }
  ]
}
```

Guess-only players omit `seasons`. Career `games`/`points` are totals; season stats are per-game.

## 5. UI / branding

- Title **"Journeyman — NBA"**; copy in About/instructions updated for basketball (season, teams, PPG/RPG/APG).
- **NBA team colours** map + 3-letter team abbreviations for the coloured dots (replacing AFL club colours/abbrs).
- Season row shows **team + `GP · PPG · RPG · APG`** (steals/blocks available too since data starts 1980; shown if space allows, otherwise kept as the four headline figures).
- Attribution updated to credit **NBA.com / `nba_api`** (no team logos, player photos, or league marks). `COFFEE_URL` carried over from the AFL site (existing handle, confirm before launch).
- Footer year-range + player count filled in automatically from the data, as in AFL.

## 6. Deployment

- Same Netlify static publish (`publish = "."`, no build command); `players.json` cached with the same header.
- `.github/workflows/refresh-data.yml` adapted to run the `nba_api` builder weekly and commit on change.

## 7. Risks / judgement calls

- **`nba_api` reliability:** stats.nba.com can rate-limit/block automated/cloud requests. Mitigation: polite delays + retries + realistic headers in the builder; the committed `players.json` insulates the live site from any API outage.
- **Inferred positions:** coarse GUARD/WING/BIG buckets, hand-overridable — accepted trade-off (matches AFL).
- **Traded seasons** collapse to one primary team per season row.
- **Decade pool sizing:** confirm every decade (esp. 2020s, which is short) has enough answerable players; relax thresholds per-decade if needed.

## 8. File inventory (target repo `journeyman-nba`)

| File | Purpose |
|---|---|
| `index.html` | Whole game (logic + styles + embedded fallback set). Adapted from AFL with NBA modes, teams, copy. |
| `players.json` | Generated NBA dataset (1980–present). |
| `build_players.py` | Rewritten to build from `nba_api`. |
| `.github/workflows/refresh-data.yml` | Weekly `nba_api` rebuild + commit. |
| `netlify.toml` | Static publish config (as AFL). |
| `README.md` | NBA-specific docs. |
| `requirements.txt` | `nba_api`, `pandas` (new — pins builder deps). |

## Out of scope (YAGNI)

- Honours/awards (MVP, rings) — not needed for the clue set.
- Live in-season auto-updating beyond the weekly Action.
- Pre-1980 eras and 40s/50s/60s/70s decade games.
