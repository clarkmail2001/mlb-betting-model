# Session record — Soccer Player-Eval Lenses (2026-07-14)

This session's work shipped to **clarkmail2001/strata** `main` (commit `34d8e93`,
"soccer: PLAYER LENSES — five distinct-thesis player-eval metrics, graded not vibed").
This file is the pointer record on the session's designated branch; the MLB repo itself
was not otherwise touched.

## What shipped (in strata)

Five structurally different player-evaluation metrics — the soccer answer to xG-class
player eval, each with its own written thesis, its own data source, and its own graded
game model:

| lens | thesis | data |
|---|---|---|
| creator | finishing is noise; shot creation is signal (npxG+xA/90) | Understat club xG + StatsBomb intl history |
| form | the tournament is its own regime (Bayes-padded THIS-WC production) | player-games.jsonl live box log |
| impact | you are what the scoreboard does while you're on the pitch (ridge ± with club prior) | captured confirmed XIs + player-impact.json |
| market | the transfer market already scouted everyone (log value, age-adj) | Transfermarkt CC0 |
| wall | goals prevented = goals scored (saves-over-expected, on-pitch GA) | player-games.jsonl |

- `tools/soccer/lib/lenses.mjs` — the suite (shared spine: player value → XI roll-up → z → Poisson/DC grid)
- `tools/soccer/lab/lens-backtest.mjs` — walk-forward backtest over 87 confirmed-XI games; all 5 beat naive; pairwise r 0.17–0.80 (pool collapses at 0.92)
- `lens_*` models frozen + graded automatically (snapshot/grade dynamic filters)
- `/soccer/lenses` page (boards, backtest, distinctness) + lens strip on `/soccer/predict`
- 4 fuse-box checks: `soccer.lenses.built / on_slate / distinct / graded`
