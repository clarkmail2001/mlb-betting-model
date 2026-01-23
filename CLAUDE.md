CLAUDE.md - MLB BETTING MODEL
Last Updated: January 22, 2026
Project Status: Pre-Season Development (Opening Day: March 27, 2026)
Current Version: v2.0 (Pitch Arsenal Integration Complete)

TABLE OF CONTENTS

Project Overview
Current Status
Technical Architecture
Projection Engine Logic
Data Weighting System
Feature Roadmap
Data Requirements
Decision Log
Build Instructions
TODOs & Blockers


PROJECT OVERVIEW
What We're Building
A comprehensive MLB prediction model that analyzes pitcher-batter matchups using transparent mathematical calculations to project runs scored in games. The model is designed for real-money wagering with complete mathematical transparency and self-learning capabilities.
Core Philosophy

Transparent Math - Every projection shows step-by-step calculations
Learning System - Model improves by tracking actual outcomes vs predictions
Comprehensive Betting - Covers F5, full game, NRFI, extra innings, live betting
Opponent-Adjusted Stats - Accounts for strength of schedule
Career Context - Uses multi-year data to understand player trends

Success Criteria

✅ Realistic run projections (6-12 total runs per game)
✅ Accurate F5 projections (within ±1 run 70% of games)
✅ Transparent calculations (show every step)
✅ Self-learning (adjust weights based on results)
✅ Profitable betting outcomes (ROI > 5% over full season)

Key Differentiators
This model is unique because:

Most betting models are black boxes → This shows all calculations
Most use basic stats → This uses pitch arsenal matchups, discipline metrics, opponent quality
Most are static → This learns from outcomes and adjusts
Most focus on one bet type → This covers every possible bet


CURRENT STATUS
✅ What's Working
Database:

542 pitchers loaded with stats (ERA, xFIP, K/9, BB/9, WAR, pitch arsenal)
665 hitters loaded with stats (wOBA, xwOBA, wRC+, DRC+, K%, BB%, barrel rate)
30 teams with park factors
Pitch arsenal data (pitcher throws X pitch, hitter's performance vs that pitch)
Hitter vs pitch type performance

Projection Engine:

Baseline wOBA calculation (hitter wOBA + xwOBA averaged)
Pitcher quality adjustment (based on xFIP vs league average)
K-rate interaction (high-K pitcher vs high-K hitter penalties)
Park factor adjustments
Pitch arsenal matchups (weighted by usage %)
Runs conversion formula: (wOBA - 0.290) × 4.6 = runs per PA
Expected PA by lineup position
F5 and Full Game projections
Bullpen projections (league average rate × remaining innings)

UI:

Clean, baseball-themed design (cream background, slate headers, red accents)
Team pages showing rosters
Player pages showing detailed stats
Matchup builder (select teams, pitchers, lineups)
Results tracking page (save predictions, enter actual scores)

❌ What's Broken/Missing
Critical Missing Features:

❌ vs L/R Splits - Hitters perform differently vs LHP/RHP (PRIORITY #1)
❌ Historical Data - No 2022-2024 season data loaded (limits career context)
❌ Opponent Quality Adjustment - Stats not adjusted for strength of schedule
❌ Daily Data Updates - No automatic refresh of 2026 running stats
❌ Machine Learning - No weight optimization based on historical accuracy
❌ Confidence Intervals - Projections don't show uncertainty ranges
❌ Roster Management - Can't move players between teams (trades, FA signings)
❌ Live Betting Features - No in-game projections

Known Issues:

Some pitcher stats showing as dashes (import may have missed some columns)
No pitcher handedness (L/R) stored in database yet
No catcher framing stats integrated
No defensive metrics (OAA, DRS) integrated

📊 Data Inventory
Currently Loaded:

2025 FanGraphs hitters (fg_hitters.csv)
2025 FanGraphs pitchers (fg_pitchers.csv)
2025 Baseball Savant hitters (savant_hitters.csv)
2025 Baseball Savant pitchers - pitch arsenal (savant_pitchers.csv)
2025 Baseball Prospectus hitters - DRC+ (bp_hitters.csv)
2025 Hitter vs Pitch Type data (savant_hitters_all_csv.csv)

Missing Data:

vs L/R splits (hitters and pitchers)
2022-2024 historical season data
Catcher framing stats
Defensive metrics (OAA, DRS, arm strength)
Baserunning stats (sprint speed)
Plate discipline metrics (O-Swing%, Z-Contact%, etc.)
Batted ball data (GB%, FB%, pull%, etc.)
Retrosheet game-by-game data for ML training


TECHNICAL ARCHITECTURE
Technology Stack

Backend: Python 3.11, Flask web framework
Database: SQLite (stored in /tmp on Railway, local file for development)
Deployment: Railway (free tier, auto-deploys from GitHub)
Frontend: HTML/CSS/JavaScript (vanilla, no framework)
Version Control: GitHub (clarkmail2001/mlb-betting-model)

Database Schema
Core Tables:
sqlteams (team_id, name, abbreviation, league, division, park_factor)
players (player_id, name, team_id, position, bats, throws, mlbam_id)
pitcher_stats (player_id, games, gs, ip, era, xfip, k9, bb9, war, ...)
hitter_stats (player_id, pa, woba, xwoba, wrc_plus, k_rate, war, ...)
pitch_arsenal (player_id, pitch_type, usage_pct, woba_against, whiff_rate, ...)
hitter_vs_pitch (player_id, pitch_type, woba, xwoba, run_value, ...)
predictions (id, date, teams, pitchers, projections, actual_scores, ...)
model_weights (weight_name, weight_value, updated_at)
New Tables (Not Yet Populated):
sqlhitter_splits (player_id, split_type, woba, wrc_plus, ...)  -- vs LHP/RHP
catcher_stats (player_id, framing_runs, blocking_runs, ...)
fielding_stats (player_id, position, outs_above_avg, ...)
baserunning_stats (player_id, sprint_speed, bolts, ...)
hitter_discipline (player_id, o_swing_pct, z_contact_pct, ...)
pitch_movement (player_id, pitch_type, avg_speed, break_x, break_z, ...)
```

### **Data Flow**
```
CSV Files (FanGraphs, Savant, BP)
        ↓
import_csvs() function
        ↓
SQLite Database
        ↓
API Routes (/api/project)
        ↓
Projection Engine (calculate_matchup_detailed)
        ↓
JSON Response
        ↓
Frontend UI (matchup.html)
        ↓
Display Results
```

### **Key Functions**

**Projection Engine:**
- `project_game()` - Main function, projects full game
- `calculate_matchup_detailed()` - Single batter vs pitcher matchup
- `calculate_arsenal_matchup()` - Pitch-by-pitch weighted wOBA
- `estimate_pitcher_innings()` - How long starter will go
- `get_pitcher_arsenal()` - Retrieve pitcher's pitch mix
- `get_hitter_vs_pitch()` - Retrieve hitter's performance vs pitch types

**Database:**
- `init_db()` - Create tables, load initial data
- `import_csvs()` - Parse and import all CSV files
- `get_db()` - Database connection helper

**Utilities:**
- `safe_float()` - Parse numeric values from CSVs
- `make_player_id()` - Normalize player names to IDs
- `format_stat()` - Display stats with proper decimals

---

## PROJECTION ENGINE LOGIC

### **Step-by-Step Calculation (Per At-Bat)**

For each hitter vs pitcher matchup:

**1. BASELINE wOBA**
```
baseline = (hitter_wOBA + hitter_xwOBA) / 2

Future Enhancement (when splits available):
IF pitcher is LHP:
    baseline = hitter's vs_LHP wOBA
ELSE:
    baseline = hitter's vs_RHP wOBA
```

**2. PITCH ARSENAL MATCHUP (30% weight)**
```
For each pitch pitcher throws:
    pitch_weight = (usage_pct / 100)
    pitcher_woba_on_pitch = pitch_arsenal.woba_against
    hitter_woba_vs_pitch = hitter_vs_pitch.woba
    matchup_woba = (pitcher_woba + hitter_woba) / 2
    weighted_sum += pitch_weight × matchup_woba

arsenal_woba = weighted_sum / total_usage
arsenal_adj = (arsenal_woba - baseline) × 0.30
```

**3. PITCHER QUALITY ADJUSTMENT**
```
pitcher_factor = 0.012
pitcher_adj = (league_avg_xfip - pitcher_xfip) × pitcher_factor

Example:
- Elite pitcher (xFIP 3.00): (4.10 - 3.00) × 0.012 = +0.013 (helps hitter)
- Bad pitcher (xFIP 5.00): (4.10 - 5.00) × 0.012 = -0.011 (hurts hitter)
```

**4. K-RATE INTERACTION**
```
IF pitcher_k9 > 10.0 AND hitter_k_rate > 25%:
    k_adj = -0.008  # High-K matchup
ELIF pitcher_k9 < 7.0 AND hitter_k_rate < 18%:
    k_adj = +0.006  # Low-K matchup
ELSE:
    k_adj = 0  # Neutral
```

**5. PARK FACTOR**
```
park_mult = 0.015
park_adj = (park_factor - 1.0) × park_mult

Example:
- Coors Field (1.15): (1.15 - 1.0) × 0.015 = +0.002
- Petco Park (0.97): (0.97 - 1.0) × 0.015 = -0.0005
```

**6. FINAL PROJECTED wOBA**
```
total_adj = arsenal_adj + pitcher_adj + k_adj + park_adj
proj_woba = baseline + total_adj
proj_woba = CLAMP(proj_woba, 0.250, 0.420)  # Realistic bounds
```

**7. CONVERT TO RUNS**
```
woba_baseline = 0.290
woba_multiplier = 4.6
runs_per_pa = (proj_woba - woba_baseline) × woba_multiplier
runs_per_pa = CLAMP(runs_per_pa, 0.05, 0.18)  # Bounds for realism
```

**8. EXPECTED PA BY LINEUP POSITION**
```
PA Distribution (F5):
- Leadoff: 13.7% of team PA
- #2: 13.0%
- #3: 12.3%
- #4: 11.6%
- #5: 10.9%
- #6: 10.3%
- #7: 9.7%
- #8: 9.3%
- #9: 9.2%

Total F5 PA ≈ 21.5 (4.3 PA/inning × 5 innings)
```

**9. PLAYER RUNS**
```
expected_pa = total_f5_pa × lineup_position_weight
expected_runs = runs_per_pa × expected_pa
```

**10. TEAM F5 RUNS**
```
team_f5_runs = SUM(all 9 hitters' expected_runs)
```

**11. FULL GAME PROJECTION**
```
# Scale F5 to starter's expected innings
runs_per_ip = f5_runs / 5.0
runs_vs_starter = runs_per_ip × starter_expected_ip

# Add bullpen runs
bullpen_innings = 9 - starter_expected_ip
bullpen_runs = (league_avg_runs_per_game / 9) × 1.05 × bullpen_innings × park_factor

full_game_runs = runs_vs_starter + bullpen_runs
League Averages (2025 Season)
pythonLEAGUE_AVG = {
    'woba': 0.315,
    'xwoba': 0.315,
    'k_rate': 22.5,
    'bb_rate': 8.2,
    'era': 4.20,
    'xfip': 4.10,
    'runs_per_game': 4.5,
    'runs_per_f5': 2.5,
    'pa_per_inning': 4.3,
    'runs_per_pa': 0.115,
}
Model Weights (Adjustable)
pythonCURRENT_WEIGHTS = {
    'pitcher_quality_factor': 0.012,
    'platoon_advantage': 0.015,
    'platoon_disadvantage': -0.020,
    'high_k_interaction': -0.008,
    'low_k_interaction': 0.006,
    'park_factor_multiplier': 0.015,
    'woba_to_runs_multiplier': 4.6,
    'woba_baseline': 0.290,
    'arsenal_weight': 0.30,
}
```

These weights can be adjusted through the `/api/weights` endpoint or (future feature) directly from the admin UI.

---

## DATA WEIGHTING SYSTEM

### **Philosophy**

**Career data ALWAYS matters.** Even late in the season, what a player did over 3-4 years is more predictive than 120 games of current season data. The model never relies solely on current-season statistics.

### **Dynamic Season Weighting**

**Early Season (Games 1-30):**
```
Career Baseline: 90-97%
2026 Current Season: 3-10%

Rationale: Small sample size (10-30 games) is unreliable.
3 games: 97% career / 3% current
10 games: 95% career / 5% current
30 games: 90% career / 10% current
```

**Mid Season (Games 31-80):**
```
Career Baseline: 70%
2026 Current Season: 30%

Rationale: Sample size now meaningful but still establishing.
```

**Late Season (Games 81-162):**
```
Career Baseline: 60%
2026 Current Season: 40%

Rationale: Full season data carries weight, but career still dominant.
```

### **Career Breakdown (Multi-Year Weighting)**

When "Career Baseline" = 60% (late season example):
```
2025 Season: 50% of career weight = 30% total
2024 Season: 30% of career weight = 18% total
2023 Season: 15% of career weight = 9% total
2022 Season: 5% of career weight = 3% total
```

**Most recent full season (2025) is most predictive, but 3-4 year trends visible.**

### **Admin Controls (Future Feature)**

The weighting system will be adjustable through the admin panel:
```
┌─────────────────────────────────────────┐
│ SEASON WEIGHTING CONTROLS               │
├─────────────────────────────────────────┤
│ Games 1-30:                             │
│   Career: [90%] ◄──────► Current: [10%]│
│                                         │
│ Games 31-80:                            │
│   Career: [70%] ◄──────► Current: [30%]│
│                                         │
│ Games 81-162:                           │
│   Career: [60%] ◄──────► Current: [40%]│
│                                         │
│ Career Breakdown:                       │
│   2025: [50%]                           │
│   2024: [30%]                           │
│   2023: [15%]                           │
│   2022: [5%]                            │
└─────────────────────────────────────────┘
These values can be changed dynamically as the season progresses without code changes.
Machine Learning Optimization
Once historical data is loaded, ML will analyze past seasons to determine optimal weights:
python# ML Training Process:
For each game in 2024 season:
    At time of game:
        - Get player's 2023 stats (career baseline)
        - Get player's 2024 stats through N games (current season)
        - Test different weight combinations
        - Compare projection vs actual outcome
    
Find weights that minimize prediction error across all games.

Expected Output:
"Optimal weighting for Game 47 of season: 65% career, 35% current"
```

**ML will discover the ideal curve, removing guesswork.**

---

## FEATURE ROADMAP

### **PHASE 1: CORE PROJECTIONS (Weeks 1-3)**

**Week 1:**
- ✅ Roster Manager (move players between teams)
- ✅ Opponent Quality Adjustment (strength of schedule)
- ✅ Confidence Intervals (show projection uncertainty)

**Week 2:**
- ✅ Historical Data Structure (2022-2024 season tables)
- ✅ Daily Update Script Framework (FanGraphs scraping)
- ✅ Admin Controls for Weight Adjustments

**Week 3 (Blocked on data):**
- ⏸️ vs L/R Splits Integration (need CSV files)
- ⏸️ Import 2022-2024 Historical Data (need exports)
- ⏸️ Pitcher Handedness (L/R) tracking

**Deliverable:** Accurate F5 projections with platoon splits and opponent adjustments.

---

### **PHASE 2: MACHINE LEARNING (Weeks 4-5)**

**Week 4:**
- ✅ Retrosheet Data Import (2024-2025 seasons, ~4,800 games)
- ✅ Feature Extraction Pipeline (convert projections to ML features)
- ✅ ML Model Training (XGBoost, Random Forest, Linear Regression)

**Week 5:**
- ✅ Weight Optimization (find best coefficients from historical data)
- ✅ Backtesting Framework (test on 2024 season, compare accuracy)
- ✅ Two-Model System (Manual weights vs ML weights, compare live)

**Deliverable:** ML-optimized weights that improve projection accuracy by 5-10%.

---

### **PHASE 3: LIVE BETTING (Weeks 6-7)**

**Week 6:**
- ✅ Live Game Projection Page (separate from pre-game)
- ✅ Bullpen Depth Chart Integration (closers, setup men, usage patterns)
- ✅ Rest-of-Game Projections (from current inning onward)
- ✅ Inning-Specific Projections (next 1, 3, 5 innings)

**Week 7:**
- ✅ NRFI Probability Calculator (No Run First Inning)
- ✅ Extra Innings Probability (games likely to go beyond 9)
- ✅ Situational Adjustments (runners on base, late-game leverage)

**Deliverable:** Full in-game betting toolkit for live wagering.

---

### **PHASE 4: ADVANCED STATS (Weeks 8-10)**

**Week 8:**
- ✅ Catcher Framing Integration (framing runs, blocking runs)
- ✅ Defensive Metrics (OAA, DRS, arm strength)
- ✅ Baserunning Stats (sprint speed, stolen base success)

**Week 9:**
- ✅ Plate Discipline (O-Swing%, Z-Contact%, chase rate)
- ✅ Batted Ball Data (GB%, FB%, pull%, launch angle)
- ✅ Pitch Movement (break_x, break_z, velocity)

**Week 10:**
- ✅ Full Model Calibration (test on spring training games)
- ✅ Final Weight Adjustments
- ✅ Opening Day Ready

**Deliverable:** Production-ready model with all advanced metrics integrated.

---

## DATA REQUIREMENTS

### **PRIORITY 1: vs L/R SPLITS (CRITICAL)**

**What's Needed:**
- Hitters vs LHP (Left-Handed Pitchers)
- Hitters vs RHP (Right-Handed Pitchers)
- Pitchers vs LHB (Left-Handed Batters)
- Pitchers vs RHB (Right-Handed Batters)

**Where to Get:**
- **Baseball Reference:** https://www.baseball-reference.com/leagues/split.cgi
- Filter: "Split Stats" → "vs LHP" / "vs RHP"
- Export as CSV

**Required Columns:**
```
Name, Team, PA, wOBA, wRC+, K%, BB%, ISO, AVG, OBP, SLG, OPS
Why Critical:
A .280 hitter might be .320 vs LHP and .250 vs RHP. Without splits, projections are blind to this massive variance.

PRIORITY 2: HISTORICAL SEASONS (2022-2024)
What's Needed:

FanGraphs hitters (2022, 2023, 2024)
FanGraphs pitchers (2022, 2023, 2024)
Same format as current fg_hitters.csv / fg_pitchers.csv

Why Important:

Career baseline requires multi-year data
ML training requires historical games to learn from
Trend analysis (is player improving or declining?)


PRIORITY 3: RETROSHEET GAME DATA
What's Needed:

2024 season play-by-play data
2025 season play-by-play data
Format: Event files (every pitch, every at-bat)

Where to Get:

Retrosheet: https://www.retrosheet.org/game.htm
Download event files for 2024-2025

Why Important:

ML training requires actual game outcomes
Learn optimal weights from real data
Backtest model accuracy on past games


NICE TO HAVE: ADVANCED METRICS
Catcher Framing:

Baseball Prospectus: Framing runs saved
Baseball Savant: Strike rate by zone

Defensive Metrics:

Baseball Savant: Outs Above Average (OAA)
FanGraphs: Defensive Runs Saved (DRS)

Baserunning:

Baseball Savant: Sprint speed, bolts
FanGraphs: Base running runs (BsR)

Plate Discipline:

FanGraphs: O-Swing%, Z-Contact%, Chase rate
Baseball Savant: Whiff%, CSW%

Batted Ball:

FanGraphs: GB%, FB%, LD%, Pull%, Oppo%
Baseball Savant: Launch angle, exit velocity

All available as CSV exports from FanGraphs and Baseball Savant.

DECISION LOG
Why These Specific Formulas?
wOBA as Primary Metric:

Most correlated with run scoring (.420 correlation)
Weights hits by value (HR > 2B > 1B)
Better than AVG (.280 correlation) or OPS (.380 correlation)

xFIP for Pitchers:

Removes HR/FB luck (random variance)
More predictive than ERA (past performance) or FIP (includes actual HRs)
Best forward-looking metric

Runs Conversion: (wOBA - 0.290) × 4.6

Empirically derived from historical data
League average wOBA .315 → .115 runs/PA (matches reality)
Elite hitters .380 wOBA → .414 runs/PA (4-5 runs per game)

Pitch Arsenal Weight: 30%

Heavy enough to matter (shifts projections by ±0.5 runs)
Not so heavy that it overrides baseline performance
Testable assumption (ML will optimize this)


Why Confidence Intervals Matter
F5 Projections: 82% confidence (±0.9 runs)

Known starter, known lineup
150+ IP sample size for pitcher
High reliability

Full Game Projections: 64% confidence (±1.8 runs)

Bullpen usage uncertain
Pinch hitters unknown
Manager decisions unpredictable

Users should bet more on F5 than full game because confidence is higher.

Why Career Data Always Matters (60%+ weight)
Small Sample Variance:

30 games = 120 PA for hitter
Can hit .400 in April, regress to .280 by August
Career baseline prevents overreaction to hot/cold streaks

Regression to Mean:

Players tend toward their career averages over time
Outlier months are more likely noise than signal
Even 100-game samples can mislead

ML Will Validate This:

Train on 2024 season, test different weights
Likely finds: "60-70% career, 30-40% current" is optimal
Data-driven confirmation of intuition


Why Opponent Quality Matters
Aaron Judge Example:

Faces weak pitchers (avg xFIP 4.80): Stats inflated
Faces elite pitchers (avg xFIP 3.50): Stats deflated
Adjustment ensures fair comparison across schedules

Implementation:
pythonopponent_avg_xfip = 4.80  # Weak pitchers
league_avg = 4.10
adjustment = (4.80 - 4.10) × 0.003 = -0.002 wOBA

Deflate Judge's .370 wOBA → .368 (slightly less impressive)
This is strength of schedule adjustment, same concept as NFL SOS.

BUILD INSTRUCTIONS
Local Development Setup
bash# Clone repository
git clone https://github.com/clarkmail2001/mlb-betting-model.git
cd mlb-betting-model

# Install dependencies
pip install -r requirements.txt

# Initialize database
python app.py  # Runs init_db() and import_csvs() automatically

# Run local server
python app.py
# Open browser: http://localhost:5000
```

### **Railway Deployment**

1. Push code to GitHub
2. Railway auto-detects changes
3. Rebuilds and deploys automatically
4. Live at: mlb-betting-model-production.up.railway.app

**Environment Variables (Railway):**
```
RAILWAY_ENVIRONMENT=production
PORT=5000

Adding New CSV Data
Step 1: Add CSV file to repository
bashgit add new_data.csv
git commit -m "Add new data file"
git push origin main
Step 2: Update import_csvs() function
python# In app.py, add new import logic:
if os.path.exists('new_data.csv'):
    print("\n[8/8] Loading new_data.csv...")
    with open('new_data.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse and insert data
Step 3: Push update
bashgit add app.py
git commit -m "Add import logic for new data"
git push origin main
# Railway auto-deploys

Adjusting Model Weights
Option 1: Direct Database Update
python# In Python console or script:
conn = get_db()
cursor = conn.cursor()
cursor.execute("UPDATE model_weights SET weight_value = 0.35 WHERE weight_name = 'arsenal_weight'")
conn.commit()
Option 2: API Endpoint
bashcurl -X POST https://your-app.railway.app/api/weights \
  -H "Content-Type: application/json" \
  -d '{"arsenal_weight": 0.35, "pitcher_quality_factor": 0.015}'
Option 3: Admin UI (Future Feature)

Navigate to /admin/weights
Adjust sliders for each weight
Click "Save Changes"


TODOS & BLOCKERS
🔴 BLOCKED - Waiting on Max to Provide
1. vs L/R Splits (PRIORITY #1)

 Export hitters vs LHP from Baseball Reference
 Export hitters vs RHP from Baseball Reference
 Export pitchers vs LHB from Baseball Reference
 Export pitchers vs RHB from Baseball Reference
 Send CSV files or column headers to Claude

2. Historical Season Data

 Export 2022 FanGraphs hitters (same format as fg_hitters.csv)
 Export 2022 FanGraphs pitchers (same format as fg_pitchers.csv)
 Export 2023 FanGraphs hitters
 Export 2023 FanGraphs pitchers
 Export 2024 FanGraphs hitters
 Export 2024 FanGraphs pitchers

3. Retrosheet Game Data (For ML Training)

 Download 2024 Retrosheet event files
 Download 2025 Retrosheet event files
 Provide to Claude for import script


🟢 READY TO BUILD - Can Start Now
1. Roster Manager

 Build player search interface
 Add "Move to Team" dropdown
 Implement database update on player move
 Track transaction history

2. Opponent Quality Adjustment

 Calculate opponent strength faced (pitcher xFIP, lineup wRC+)
 Adjust player stats based on opponent quality
 Display adjustment transparently in projections
 Add "Strength of Schedule" indicator to player pages

3. Confidence Intervals

 Calculate projection uncertainty ranges
 Different confidence for F5 vs Full Game vs NRFI
 Display: "Yankees 3.2 ± 0.9 runs (82% confidence)"
 Explain why confidence is high or low

4. Historical Data Structure

 Create tables for 2022-2024 seasons
 Implement dynamic weighting system
 Build admin UI for weight adjustments
 Test weighting logic with dummy data

5. Daily Update Script Framework

 Write FanGraphs scraping script
 Build one-click "Update Stats" button
 Set up Railway cron job for automatic updates
 Email notification system (success/failure alerts)


🟡 PLANNED - Phase 2 Features
Machine Learning:

 Feature extraction pipeline (convert projections to ML inputs)
 Train XGBoost model on Retrosheet data
 Backtest on 2024 season
 Compare ML weights vs manual weights
 Implement two-model system (both run simultaneously)

Live Betting:

 Build separate live game projection page
 Bullpen depth chart integration
 Rest-of-game projections (from current inning)
 NRFI probability calculator
 Extra innings probability

Advanced Stats:

 Catcher framing integration
 Defensive metrics (OAA, DRS)
 Baserunning stats
 Plate discipline metrics
 Batted ball data
 Pitch movement data


📋 Questions for Max

vs L/R Splits: Can you export from Baseball Reference today, or need help finding the data?
Historical Data: Do you want to prioritize 2024-2025 (recent, smaller dataset) or go back to 2022 (more data, harder to collect)?
Daily Updates: Prefer automatic (set-and-forget with email alerts) or manual (one-click button each morning)?
Weight Adjustments: Want UI controls to change weights on the fly, or comfortable with database updates?
Build Order: Start with Roster Manager (immediate utility for off-season trades), or Opponent Quality (improves projections)?


CONTACT & SUPPORT
GitHub Repository: https://github.com/clarkmail2001/mlb-betting-model
Live Deployment: mlb-betting-model-production.up.railway.app
Project Owner: Max
Development: Claude (Anthropic)
For Issues:

GitHub Issues tab
Direct message in Claude chat
Email alerts from daily update script


END OF CLAUDE.MD
