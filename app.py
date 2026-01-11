"""
MLB Prediction Model - Complete Flask Application
=================================================
Features:
- Lineup input for both teams (9 batters + pitcher)
- Transparent projection math
- F5 and full game projections
- In-game substitutions
- Past game analysis
- Roster management
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import math

app = Flask(__name__)
app.secret_key = 'mlb_model_2025'

DB_PATH = 'data/baseball.db'

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with all tables."""
    os.makedirs('data', exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    # Teams table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            abbreviation TEXT NOT NULL,
            league TEXT,
            division TEXT,
            park_factor REAL DEFAULT 1.0
        )
    """)
    
    # Players table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            mlb_id INTEGER,
            name TEXT NOT NULL,
            team_id TEXT,
            position TEXT,
            bats TEXT DEFAULT 'R',
            throws TEXT DEFAULT 'R',
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    """)
    
    # Pitcher stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pitcher_stats (
            player_id TEXT PRIMARY KEY,
            season INTEGER,
            team TEXT,
            games INTEGER,
            games_started INTEGER,
            innings_pitched REAL,
            era REAL,
            whip REAL,
            k_rate REAL,
            bb_rate REAL,
            hr_rate REAL,
            babip REAL,
            lob_pct REAL,
            gb_rate REAL,
            fb_rate REAL,
            fip REAL,
            xfip REAL,
            siera REAL,
            war REAL,
            -- Pitch mix
            fb_pct REAL,
            sl_pct REAL,
            ct_pct REAL,
            cb_pct REAL,
            ch_pct REAL,
            sf_pct REAL,
            -- Pitch velocities
            fb_velo REAL,
            sl_velo REAL,
            cb_velo REAL,
            ch_velo REAL,
            -- Savant data
            xwoba_against REAL,
            xba_against REAL,
            barrel_rate_against REAL,
            hard_hit_against REAL,
            whiff_rate REAL,
            chase_rate REAL,
            -- vs L/R splits
            vs_l_woba REAL,
            vs_l_k_rate REAL,
            vs_l_bb_rate REAL,
            vs_r_woba REAL,
            vs_r_k_rate REAL,
            vs_r_bb_rate REAL,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
    """)
    
    # Hitter stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hitter_stats (
            player_id TEXT PRIMARY KEY,
            season INTEGER,
            team TEXT,
            games INTEGER,
            plate_appearances INTEGER,
            batting_avg REAL,
            obp REAL,
            slg REAL,
            ops REAL,
            woba REAL,
            xwoba REAL,
            wrc_plus REAL,
            drc_plus REAL,
            k_rate REAL,
            bb_rate REAL,
            iso REAL,
            babip REAL,
            gb_rate REAL,
            fb_rate REAL,
            ld_rate REAL,
            pull_rate REAL,
            barrel_rate REAL,
            hard_hit_rate REAL,
            avg_exit_velo REAL,
            war REAL,
            -- vs L/R splits
            vs_l_woba REAL,
            vs_l_ops REAL,
            vs_l_k_rate REAL,
            vs_r_woba REAL,
            vs_r_ops REAL,
            vs_r_k_rate REAL,
            -- vs pitch types (wOBA)
            vs_fastball REAL,
            vs_slider REAL,
            vs_curveball REAL,
            vs_changeup REAL,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
    """)
    
    # Pitch arsenal (per pitch type per pitcher)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pitch_arsenal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            pitch_type TEXT,
            pitch_name TEXT,
            usage_pct REAL,
            velocity REAL,
            spin_rate REAL,
            whiff_rate REAL,
            put_away_rate REAL,
            ba_against REAL,
            slg_against REAL,
            woba_against REAL,
            xba_against REAL,
            xslg_against REAL,
            xwoba_against REAL,
            hard_hit_rate REAL,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
    """)
    
    # Game predictions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_pitcher_id TEXT,
            away_pitcher_id TEXT,
            home_lineup TEXT,  -- JSON
            away_lineup TEXT,  -- JSON
            home_f5_runs REAL,
            away_f5_runs REAL,
            f5_total REAL,
            home_full_runs REAL,
            away_full_runs REAL,
            full_total REAL,
            projection_details TEXT,  -- JSON with full math breakdown
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Game results (for tracking accuracy)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            home_f5_actual INTEGER,
            away_f5_actual INTEGER,
            home_final INTEGER,
            away_final INTEGER,
            notes TEXT,
            FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
        )
    """)
    
    # Insert teams if not exists
    teams = [
        ('LAA', 'Los Angeles Angels', 'LAA', 'AL', 'West', 1.00),
        ('ARI', 'Arizona Diamondbacks', 'ARI', 'NL', 'West', 1.05),
        ('ATL', 'Atlanta Braves', 'ATL', 'NL', 'East', 1.00),
        ('BAL', 'Baltimore Orioles', 'BAL', 'AL', 'East', 1.02),
        ('BOS', 'Boston Red Sox', 'BOS', 'AL', 'East', 1.04),
        ('CHC', 'Chicago Cubs', 'CHC', 'NL', 'Central', 1.02),
        ('CWS', 'Chicago White Sox', 'CWS', 'AL', 'Central', 1.00),
        ('CIN', 'Cincinnati Reds', 'CIN', 'NL', 'Central', 1.06),
        ('CLE', 'Cleveland Guardians', 'CLE', 'AL', 'Central', 0.97),
        ('COL', 'Colorado Rockies', 'COL', 'NL', 'West', 1.15),
        ('DET', 'Detroit Tigers', 'DET', 'AL', 'Central', 0.98),
        ('HOU', 'Houston Astros', 'HOU', 'AL', 'West', 1.00),
        ('KC', 'Kansas City Royals', 'KC', 'AL', 'Central', 1.01),
        ('LAD', 'Los Angeles Dodgers', 'LAD', 'NL', 'West', 0.98),
        ('MIA', 'Miami Marlins', 'MIA', 'NL', 'East', 0.97),
        ('MIL', 'Milwaukee Brewers', 'MIL', 'NL', 'Central', 1.01),
        ('MIN', 'Minnesota Twins', 'MIN', 'AL', 'Central', 1.03),
        ('NYM', 'New York Mets', 'NYM', 'NL', 'East', 0.98),
        ('NYY', 'New York Yankees', 'NYY', 'AL', 'East', 1.03),
        ('OAK', 'Oakland Athletics', 'OAK', 'AL', 'West', 0.96),
        ('PHI', 'Philadelphia Phillies', 'PHI', 'NL', 'East', 1.02),
        ('PIT', 'Pittsburgh Pirates', 'PIT', 'NL', 'Central', 0.98),
        ('SD', 'San Diego Padres', 'SD', 'NL', 'West', 0.97),
        ('SF', 'San Francisco Giants', 'SF', 'NL', 'West', 0.96),
        ('SEA', 'Seattle Mariners', 'SEA', 'AL', 'West', 0.95),
        ('STL', 'St. Louis Cardinals', 'STL', 'NL', 'Central', 0.99),
        ('TB', 'Tampa Bay Rays', 'TB', 'AL', 'East', 0.97),
        ('TEX', 'Texas Rangers', 'TEX', 'AL', 'West', 1.04),
        ('TOR', 'Toronto Blue Jays', 'TOR', 'AL', 'East', 1.01),
        ('WSH', 'Washington Nationals', 'WSH', 'NL', 'East', 1.00),
    ]
    
    for team in teams:
        cursor.execute("""
            INSERT OR IGNORE INTO teams (team_id, name, abbreviation, league, division, park_factor)
            VALUES (?, ?, ?, ?, ?, ?)
        """, team)
    
    conn.commit()
    conn.close()
    print("Database initialized!")

# ============================================================================
# CSV IMPORT FUNCTIONS
# ============================================================================

def import_all_csvs():
    """Import all CSV files from the mlb_model directory."""
    import csv
    
    conn = get_db()
    cursor = conn.cursor()
    
    results = {'pitchers': 0, 'hitters': 0, 'pitch_arsenal': 0}
    
    # Team name mapping
    team_map = {
        'Angels': 'LAA', 'LAA': 'LAA', 'Diamondbacks': 'ARI', 'ARI': 'ARI',
        'Braves': 'ATL', 'ATL': 'ATL', 'Orioles': 'BAL', 'BAL': 'BAL',
        'Red Sox': 'BOS', 'BOS': 'BOS', 'Cubs': 'CHC', 'CHC': 'CHC',
        'White Sox': 'CWS', 'CWS': 'CWS', 'CHW': 'CWS',
        'Reds': 'CIN', 'CIN': 'CIN', 'Guardians': 'CLE', 'CLE': 'CLE',
        'Rockies': 'COL', 'COL': 'COL', 'Tigers': 'DET', 'DET': 'DET',
        'Astros': 'HOU', 'HOU': 'HOU', 'Royals': 'KC', 'KC': 'KC', 'KCR': 'KC',
        'Dodgers': 'LAD', 'LAD': 'LAD', 'Marlins': 'MIA', 'MIA': 'MIA',
        'Brewers': 'MIL', 'MIL': 'MIL', 'Twins': 'MIN', 'MIN': 'MIN',
        'Mets': 'NYM', 'NYM': 'NYM', 'Yankees': 'NYY', 'NYY': 'NYY',
        'Athletics': 'OAK', 'OAK': 'OAK', 'Phillies': 'PHI', 'PHI': 'PHI',
        'Pirates': 'PIT', 'PIT': 'PIT', 'Padres': 'SD', 'SD': 'SD', 'SDP': 'SD',
        'Giants': 'SF', 'SF': 'SF', 'SFG': 'SF', 'Mariners': 'SEA', 'SEA': 'SEA',
        'Cardinals': 'STL', 'STL': 'STL', 'Rays': 'TB', 'TB': 'TB', 'TBR': 'TB',
        'Rangers': 'TEX', 'TEX': 'TEX', 'Blue Jays': 'TOR', 'TOR': 'TOR',
        'Nationals': 'WSH', 'WSH': 'WSH', 'WSN': 'WSH',
    }
    
    def safe_float(val, default=None):
        if val is None or val == '' or val == '-' or val == 'NA' or val == 'NULL':
            return default
        try:
            return float(str(val).replace('%', '').strip())
        except:
            return default
    
    def safe_int(val, default=0):
        try:
            return int(float(val))
        except:
            return default
    
    def make_player_id(name):
        return name.lower().replace(' ', '_').replace('.', '').replace("'", '').replace('-', '')
    
    # 1. Import Savant Pitchers (pitch arsenal data)
    if os.path.exists('savant_pitchers.csv'):
        print("Importing savant_pitchers.csv (pitch arsenal)...")
        with open('savant_pitchers.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                if not name or name == ' ':
                    continue
                
                player_id = make_player_id(name)
                team = team_map.get(row.get('team_name_alt', ''), 'UNK')
                
                # Insert player
                cursor.execute("""
                    INSERT OR IGNORE INTO players (player_id, mlb_id, name, team_id, position, throws)
                    VALUES (?, ?, ?, ?, 'P', 'R')
                """, (player_id, safe_int(row.get('player_id')), name, team))
                
                # Insert pitch arsenal
                cursor.execute("""
                    INSERT INTO pitch_arsenal 
                    (player_id, pitch_type, pitch_name, usage_pct, whiff_rate, put_away_rate,
                     ba_against, slg_against, woba_against, xba_against, xslg_against, xwoba_against, hard_hit_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    row.get('pitch_type', ''),
                    row.get('pitch_name', ''),
                    safe_float(row.get('pitch_usage')),
                    safe_float(row.get('whiff_percent')),
                    safe_float(row.get('put_away')),
                    safe_float(row.get('ba')),
                    safe_float(row.get('slg')),
                    safe_float(row.get('woba')),
                    safe_float(row.get('est_ba')),
                    safe_float(row.get('est_slg')),
                    safe_float(row.get('est_woba')),
                    safe_float(row.get('hard_hit_percent'))
                ))
                results['pitch_arsenal'] += 1
        print(f"  Imported {results['pitch_arsenal']} pitch arsenal rows")
    
    # 2. Import FanGraphs Pitch Mix
    if os.path.exists('fg_pitch_mix.csv'):
        print("Importing fg_pitch_mix.csv...")
        with open('fg_pitch_mix.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name:
                    continue
                
                player_id = make_player_id(name)
                team = team_map.get(row.get('Team', ''), 'UNK')
                
                cursor.execute("""
                    INSERT OR IGNORE INTO players (player_id, name, team_id, position)
                    VALUES (?, ?, ?, 'P')
                """, (player_id, name, team))
                
                cursor.execute("""
                    INSERT OR REPLACE INTO pitcher_stats 
                    (player_id, season, team, fb_pct, sl_pct, ct_pct, cb_pct, ch_pct, sf_pct,
                     fb_velo, sl_velo, cb_velo, ch_velo)
                    VALUES (?, 2025, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, team,
                    safe_float(row.get('FB%')), safe_float(row.get('SL%')),
                    safe_float(row.get('CT%')), safe_float(row.get('CB%')),
                    safe_float(row.get('CH%')), safe_float(row.get('SF%')),
                    safe_float(row.get('FBv')), safe_float(row.get('SLv')),
                    safe_float(row.get('CBv')), safe_float(row.get('CHv'))
                ))
                results['pitchers'] += 1
    
    # 3. Import FanGraphs Hitters
    if os.path.exists('fg_hitters.csv'):
        print("Importing fg_hitters.csv...")
        with open('fg_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name:
                    continue
                
                player_id = make_player_id(name)
                team = team_map.get(row.get('Team', ''), 'UNK')
                
                cursor.execute("""
                    INSERT OR REPLACE INTO players (player_id, name, team_id, position, is_active)
                    VALUES (?, ?, ?, 'DH', 1)
                """, (player_id, name, team))
                
                cursor.execute("""
                    INSERT OR REPLACE INTO hitter_stats
                    (player_id, season, team, plate_appearances, batting_avg, obp, slg, ops,
                     woba, wrc_plus, k_rate, bb_rate, iso, babip, war)
                    VALUES (?, 2025, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, team,
                    safe_int(row.get('PA')),
                    safe_float(row.get('AVG')), safe_float(row.get('OBP')),
                    safe_float(row.get('SLG')), safe_float(row.get('OPS')),
                    safe_float(row.get('wOBA')), safe_float(row.get('wRC+')),
                    safe_float(row.get('K%')), safe_float(row.get('BB%')),
                    safe_float(row.get('ISO')), safe_float(row.get('BABIP')),
                    safe_float(row.get('WAR'))
                ))
                results['hitters'] += 1
        print(f"  Imported {results['hitters']} hitters from FanGraphs")
    
    # 4. Import Savant Hitters
    if os.path.exists('savant_hitters.csv'):
        print("Importing savant_hitters.csv...")
        with open('savant_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                if not name or name == ' ':
                    continue
                
                player_id = make_player_id(name)
                
                # Update existing hitter with Savant data
                cursor.execute("""
                    UPDATE hitter_stats SET
                        xwoba = ?, barrel_rate = ?, hard_hit_rate = ?, avg_exit_velo = ?
                    WHERE player_id = ?
                """, (
                    safe_float(row.get('xwoba')),
                    safe_float(row.get('barrel_batted_rate')),
                    safe_float(row.get('hard_hit_percent')),
                    safe_float(row.get('avg_best_speed')),
                    player_id
                ))
    
    # 5. Import Baseball Prospectus (DRC+)
    if os.path.exists('bp_hitters.csv'):
        print("Importing bp_hitters.csv (DRC+)...")
        with open('bp_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', '')
                if not name:
                    continue
                
                player_id = make_player_id(name)
                
                cursor.execute("""
                    UPDATE hitter_stats SET drc_plus = ? WHERE player_id = ?
                """, (safe_float(row.get('DRC+')), player_id))
    
    conn.commit()
    conn.close()
    
    print(f"\nImport complete!")
    print(f"  Pitchers: {results['pitchers']}")
    print(f"  Hitters: {results['hitters']}")
    print(f"  Pitch Arsenal: {results['pitch_arsenal']}")
    
    return results

# ============================================================================
# PROJECTION ENGINE
# ============================================================================

LEAGUE_AVG = {
    'woba': 0.315,
    'xwoba': 0.315,
    'ops': 0.720,
    'wrc_plus': 100,
    'k_rate': 22.5,
    'bb_rate': 8.2,
    'era': 4.20,
    'runs_per_inning': 0.50,
    'pa_per_inning': 4.3,
}

def calculate_matchup(pitcher: Dict, hitter: Dict, park_factor: float = 1.0) -> Dict:
    """
    Calculate a single pitcher vs hitter matchup.
    Returns detailed breakdown of the calculation.
    """
    calc_steps = []
    
    # Get pitcher hand
    pitcher_hand = pitcher.get('throws', 'R')
    hitter_hand = hitter.get('bats', 'R')
    
    # Step 1: Get hitter's baseline production
    h_woba = hitter.get('woba') or hitter.get('xwoba') or LEAGUE_AVG['woba']
    h_xwoba = hitter.get('xwoba') or h_woba
    
    # Use the average of wOBA and xwOBA for more stability
    baseline_woba = (h_woba + h_xwoba) / 2
    calc_steps.append(f"Baseline wOBA: ({h_woba:.3f} + {h_xwoba:.3f}) / 2 = {baseline_woba:.3f}")
    
    # Step 2: Get hitter vs hand split if available
    split_key = f"vs_{pitcher_hand.lower()}_woba"
    h_vs_hand = hitter.get(split_key)
    if h_vs_hand:
        baseline_woba = (baseline_woba + h_vs_hand) / 2
        calc_steps.append(f"Adjusted for vs {pitcher_hand}HP: {baseline_woba:.3f}")
    
    # Step 3: Pitcher quality adjustment
    p_era = pitcher.get('era') or LEAGUE_AVG['era']
    p_xwoba = pitcher.get('xwoba_against') or LEAGUE_AVG['xwoba']
    
    # ERA-based adjustment: (League ERA - Pitcher ERA) / League ERA * 0.03
    era_adj = (LEAGUE_AVG['era'] - p_era) / LEAGUE_AVG['era'] * 0.03
    calc_steps.append(f"ERA adjustment: ({LEAGUE_AVG['era']:.2f} - {p_era:.2f}) / {LEAGUE_AVG['era']:.2f} × 0.03 = {era_adj:+.4f}")
    
    # xwOBA against adjustment
    xwoba_adj = (LEAGUE_AVG['xwoba'] - p_xwoba) * 0.5
    calc_steps.append(f"xwOBA adjustment: ({LEAGUE_AVG['xwoba']:.3f} - {p_xwoba:.3f}) × 0.5 = {xwoba_adj:+.4f}")
    
    # Step 4: K-rate interaction
    p_k_rate = pitcher.get('k_rate') or LEAGUE_AVG['k_rate']
    h_k_rate = hitter.get('k_rate') or LEAGUE_AVG['k_rate']
    
    k_interaction = 0
    if p_k_rate > 28 and h_k_rate > 25:
        k_interaction = -0.012
        calc_steps.append(f"K-rate interaction: High-K pitcher ({p_k_rate:.1f}%) vs High-K hitter ({h_k_rate:.1f}%) = {k_interaction:+.3f}")
    elif p_k_rate < 18 and h_k_rate < 18:
        k_interaction = 0.012
        calc_steps.append(f"K-rate interaction: Low-K matchup = {k_interaction:+.3f}")
    
    # Step 5: Platoon adjustment
    platoon_adj = 0
    if pitcher_hand == hitter_hand and hitter_hand != 'S':
        platoon_adj = -0.010
        calc_steps.append(f"Platoon: Same side ({pitcher_hand}HP vs {hitter_hand}HB) = {platoon_adj:+.3f}")
    elif hitter_hand != 'S' and pitcher_hand != hitter_hand:
        platoon_adj = 0.010
        calc_steps.append(f"Platoon: Opposite ({pitcher_hand}HP vs {hitter_hand}HB) = {platoon_adj:+.3f}")
    
    # Step 6: Park factor
    park_adj = (park_factor - 1.0) * 0.02
    calc_steps.append(f"Park factor: ({park_factor:.2f} - 1.0) × 0.02 = {park_adj:+.4f}")
    
    # Step 7: Final wOBA
    total_adj = era_adj + xwoba_adj + k_interaction + platoon_adj + park_adj
    projected_woba = baseline_woba + total_adj
    projected_woba = max(0.200, min(0.500, projected_woba))
    
    calc_steps.append(f"Total adjustment: {total_adj:+.4f}")
    calc_steps.append(f"Projected wOBA: {baseline_woba:.3f} + {total_adj:+.4f} = {projected_woba:.3f}")
    
    # Step 8: Convert to runs per PA
    # wOBA to runs: (wOBA - 0.180) * 1.1
    runs_per_pa = (projected_woba - 0.180) * 1.1
    runs_per_pa = max(0.05, runs_per_pa)
    calc_steps.append(f"Runs/PA: ({projected_woba:.3f} - 0.180) × 1.1 = {runs_per_pa:.4f}")
    
    # Determine advantage
    diff = projected_woba - LEAGUE_AVG['woba']
    if diff > 0.015:
        advantage = 'hitter'
    elif diff < -0.015:
        advantage = 'pitcher'
    else:
        advantage = 'neutral'
    
    return {
        'hitter_name': hitter.get('name', 'Unknown'),
        'hitter_hand': hitter_hand,
        'pitcher_hand': pitcher_hand,
        'baseline_woba': round(baseline_woba, 3),
        'projected_woba': round(projected_woba, 3),
        'runs_per_pa': round(runs_per_pa, 4),
        'advantage': advantage,
        'calculation_steps': calc_steps
    }


def project_lineup_vs_pitcher(pitcher: Dict, lineup: List[Dict], innings: float, 
                               park_factor: float = 1.0) -> Dict:
    """
    Project a lineup's performance against a pitcher.
    Returns detailed calculation breakdown.
    """
    calc_steps = []
    matchups = []
    
    # PA weights by lineup position (1-9)
    pa_weights = [0.137, 0.130, 0.123, 0.116, 0.109, 0.103, 0.097, 0.093, 0.092]
    
    # Total PA for innings
    total_pa = LEAGUE_AVG['pa_per_inning'] * innings
    calc_steps.append(f"Total PA for {innings} innings: {LEAGUE_AVG['pa_per_inning']} × {innings} = {total_pa:.1f}")
    
    total_runs = 0
    lineup_woba_sum = 0
    lineup_pa_sum = 0
    
    for i, hitter in enumerate(lineup[:9]):
        if not hitter:
            continue
        
        matchup = calculate_matchup(pitcher, hitter, park_factor)
        matchups.append(matchup)
        
        pa_share = pa_weights[i] if i < len(pa_weights) else 0.09
        hitter_pa = total_pa * pa_share
        hitter_runs = matchup['runs_per_pa'] * hitter_pa
        
        total_runs += hitter_runs
        lineup_woba_sum += matchup['projected_woba'] * hitter_pa
        lineup_pa_sum += hitter_pa
        
        calc_steps.append(f"  {i+1}. {matchup['hitter_name']}: {matchup['projected_woba']:.3f} wOBA × {hitter_pa:.1f} PA = {hitter_runs:.2f} runs")
    
    avg_lineup_woba = lineup_woba_sum / lineup_pa_sum if lineup_pa_sum > 0 else LEAGUE_AVG['woba']
    
    calc_steps.append(f"Lineup avg wOBA: {avg_lineup_woba:.3f}")
    calc_steps.append(f"Total projected runs: {total_runs:.2f}")
    
    return {
        'innings': innings,
        'total_pa': round(total_pa, 1),
        'avg_lineup_woba': round(avg_lineup_woba, 3),
        'projected_runs': round(total_runs, 2),
        'matchups': matchups,
        'calculation_steps': calc_steps
    }


def project_game(home_pitcher: Dict, away_pitcher: Dict,
                 home_lineup: List[Dict], away_lineup: List[Dict],
                 park_factor: float = 1.0, home_sp_innings: float = 5.0,
                 away_sp_innings: float = 5.0) -> Dict:
    """
    Full game projection with F5 and full game totals.
    """
    calc_steps = []
    
    calc_steps.append("=" * 50)
    calc_steps.append("F5 PROJECTION (First 5 Innings)")
    calc_steps.append("=" * 50)
    
    # F5: Away lineup vs Home pitcher (5 innings)
    calc_steps.append("\n--- AWAY TEAM vs HOME PITCHER ---")
    away_f5_proj = project_lineup_vs_pitcher(home_pitcher, away_lineup, 5.0, 1/park_factor)
    away_f5_runs = away_f5_proj['projected_runs']
    calc_steps.extend(away_f5_proj['calculation_steps'])
    
    # F5: Home lineup vs Away pitcher (5 innings)
    calc_steps.append("\n--- HOME TEAM vs AWAY PITCHER ---")
    home_f5_proj = project_lineup_vs_pitcher(away_pitcher, home_lineup, 5.0, park_factor)
    home_f5_runs = home_f5_proj['projected_runs']
    calc_steps.extend(home_f5_proj['calculation_steps'])
    
    f5_total = home_f5_runs + away_f5_runs
    
    calc_steps.append(f"\nF5 TOTAL: {away_f5_runs:.2f} + {home_f5_runs:.2f} = {f5_total:.2f}")
    
    # Full game: Add bullpen innings (innings 6-9)
    calc_steps.append("\n" + "=" * 50)
    calc_steps.append("FULL GAME PROJECTION")
    calc_steps.append("=" * 50)
    
    # Bullpen innings at league average run rate
    bp_runs_per_inn = LEAGUE_AVG['runs_per_inning'] * 1.05  # Bullpens slightly worse than starters
    
    # Away bullpen vs Home lineup
    home_bp_innings = 4.0
    home_bp_runs = home_bp_innings * bp_runs_per_inn * park_factor
    calc_steps.append(f"Home vs Away bullpen: {home_bp_innings} inn × {bp_runs_per_inn:.3f} × {park_factor:.2f} = {home_bp_runs:.2f}")
    
    # Home bullpen vs Away lineup
    away_bp_innings = 4.0
    away_bp_runs = away_bp_innings * bp_runs_per_inn * (1/park_factor)
    calc_steps.append(f"Away vs Home bullpen: {away_bp_innings} inn × {bp_runs_per_inn:.3f} × {1/park_factor:.2f} = {away_bp_runs:.2f}")
    
    home_full_runs = home_f5_runs + home_bp_runs
    away_full_runs = away_f5_runs + away_bp_runs
    full_total = home_full_runs + away_full_runs
    
    calc_steps.append(f"\nHome full game: {home_f5_runs:.2f} + {home_bp_runs:.2f} = {home_full_runs:.2f}")
    calc_steps.append(f"Away full game: {away_f5_runs:.2f} + {away_bp_runs:.2f} = {away_full_runs:.2f}")
    calc_steps.append(f"FULL GAME TOTAL: {full_total:.2f}")
    
    # Win probability
    if home_full_runs + away_full_runs > 0:
        home_win_prob = home_full_runs / (home_full_runs + away_full_runs)
        # Regress toward 50%
        home_win_prob = home_win_prob * 0.7 + 0.5 * 0.3
    else:
        home_win_prob = 0.5
    
    return {
        'home_f5_runs': round(home_f5_runs, 2),
        'away_f5_runs': round(away_f5_runs, 2),
        'f5_total': round(f5_total, 2),
        'f5_spread': round(away_f5_runs - home_f5_runs, 2),
        'home_full_runs': round(home_full_runs, 2),
        'away_full_runs': round(away_full_runs, 2),
        'full_total': round(full_total, 2),
        'full_spread': round(away_full_runs - home_full_runs, 2),
        'home_win_prob': round(home_win_prob, 3),
        'home_matchups': home_f5_proj['matchups'],
        'away_matchups': away_f5_proj['matchups'],
        'calculation_steps': calc_steps
    }

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Dashboard."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get recent predictions
    cursor.execute("SELECT COUNT(*) FROM predictions WHERE game_date >= date('now', '-7 days')")
    recent_preds = cursor.fetchone()[0]
    
    # Get player counts
    cursor.execute("SELECT COUNT(*) FROM hitter_stats")
    hitter_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM pitcher_stats")
    pitcher_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT player_id) FROM pitch_arsenal")
    arsenal_count = cursor.fetchone()[0]
    
    # Get teams
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return render_template('index.html', 
                          recent_preds=recent_preds,
                          hitter_count=hitter_count,
                          pitcher_count=pitcher_count,
                          arsenal_count=arsenal_count,
                          teams=teams)


@app.route('/matchup')
def matchup():
    """Matchup builder page."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM teams ORDER BY name")
    teams = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return render_template('matchup.html', teams=teams)


@app.route('/api/team/<team_id>/roster')
def api_team_roster(team_id):
    """Get team roster."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get pitchers
    cursor.execute("""
        SELECT p.*, ps.era, ps.whip, ps.k_rate, ps.siera, ps.war,
               ps.fb_pct, ps.sl_pct, ps.cb_pct, ps.ch_pct
        FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND (p.position = 'P' OR ps.player_id IS NOT NULL)
        ORDER BY ps.war DESC NULLS LAST
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    # Get hitters
    cursor.execute("""
        SELECT p.*, hs.woba, hs.xwoba, hs.wrc_plus, hs.drc_plus, hs.ops, hs.war,
               hs.k_rate, hs.bb_rate, hs.barrel_rate, hs.hard_hit_rate
        FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND hs.player_id IS NOT NULL
        ORDER BY hs.wrc_plus DESC NULLS LAST
    """, (team_id,))
    hitters = [dict(r) for r in cursor.fetchall()]
    
    # Get team park factor
    cursor.execute("SELECT park_factor FROM teams WHERE team_id = ?", (team_id,))
    team = cursor.fetchone()
    park_factor = team['park_factor'] if team else 1.0
    
    conn.close()
    
    return jsonify({
        'pitchers': pitchers,
        'hitters': hitters,
        'park_factor': park_factor
    })


@app.route('/api/pitcher/<player_id>')
def api_pitcher(player_id):
    """Get pitcher details including arsenal."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, ps.* FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.player_id = ?
    """, (player_id,))
    pitcher = cursor.fetchone()
    
    if not pitcher:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    
    pitcher = dict(pitcher)
    
    # Get pitch arsenal
    cursor.execute("""
        SELECT * FROM pitch_arsenal WHERE player_id = ?
        ORDER BY usage_pct DESC
    """, (player_id,))
    arsenal = [dict(r) for r in cursor.fetchall()]
    
    pitcher['arsenal'] = arsenal
    
    conn.close()
    
    return jsonify(pitcher)


@app.route('/api/hitter/<player_id>')
def api_hitter(player_id):
    """Get hitter details."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, hs.* FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.player_id = ?
    """, (player_id,))
    hitter = cursor.fetchone()
    
    conn.close()
    
    if not hitter:
        return jsonify({'error': 'Not found'}), 404
    
    return jsonify(dict(hitter))


@app.route('/api/project', methods=['POST'])
def api_project():
    """Run game projection."""
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get pitchers
    cursor.execute("""
        SELECT p.*, ps.* FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.player_id = ?
    """, (data['home_pitcher_id'],))
    home_pitcher = dict(cursor.fetchone() or {})
    
    cursor.execute("""
        SELECT p.*, ps.* FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.player_id = ?
    """, (data['away_pitcher_id'],))
    away_pitcher = dict(cursor.fetchone() or {})
    
    # Get lineups
    home_lineup = []
    for pid in data.get('home_lineup', []):
        cursor.execute("""
            SELECT p.*, hs.* FROM players p
            LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
            WHERE p.player_id = ?
        """, (pid,))
        h = cursor.fetchone()
        if h:
            home_lineup.append(dict(h))
    
    away_lineup = []
    for pid in data.get('away_lineup', []):
        cursor.execute("""
            SELECT p.*, hs.* FROM players p
            LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
            WHERE p.player_id = ?
        """, (pid,))
        h = cursor.fetchone()
        if h:
            away_lineup.append(dict(h))
    
    conn.close()
    
    # Run projection
    park_factor = data.get('park_factor', 1.0)
    projection = project_game(home_pitcher, away_pitcher, home_lineup, away_lineup, park_factor)
    
    # Add pitcher info
    projection['home_pitcher'] = home_pitcher
    projection['away_pitcher'] = away_pitcher
    
    return jsonify(projection)


@app.route('/api/import', methods=['POST'])
def api_import():
    """Import CSV files."""
    try:
        result = import_all_csvs()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/teams')
def teams():
    """Teams list."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('teams.html', teams=teams)


@app.route('/team/<team_id>')
def team_detail(team_id):
    """Team detail page."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,))
    team = cursor.fetchone()
    if not team:
        return "Team not found", 404
    team = dict(team)
    
    # Get pitchers
    cursor.execute("""
        SELECT p.*, ps.era, ps.whip, ps.k_rate, ps.bb_rate, ps.siera, ps.war,
               ps.fb_pct, ps.sl_pct, ps.cb_pct, ps.ch_pct, ps.xwoba_against
        FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ?
        ORDER BY ps.war DESC NULLS LAST
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    # Get hitters
    cursor.execute("""
        SELECT p.*, hs.batting_avg, hs.obp, hs.slg, hs.ops, hs.woba, hs.xwoba,
               hs.wrc_plus, hs.drc_plus, hs.k_rate, hs.bb_rate, hs.war,
               hs.barrel_rate, hs.hard_hit_rate
        FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND hs.player_id IS NOT NULL
        ORDER BY hs.wrc_plus DESC NULLS LAST
    """, (team_id,))
    hitters = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return render_template('team.html', team=team, pitchers=pitchers, hitters=hitters)


@app.route('/player/<player_id>')
def player_detail(player_id):
    """Player detail page."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Try pitcher first
    cursor.execute("""
        SELECT p.*, ps.* FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.player_id = ?
    """, (player_id,))
    player = cursor.fetchone()
    
    if player and player['era'] is not None:
        player = dict(player)
        player_type = 'pitcher'
        
        # Get arsenal
        cursor.execute("""
            SELECT * FROM pitch_arsenal WHERE player_id = ?
            ORDER BY usage_pct DESC
        """, (player_id,))
        player['arsenal'] = [dict(r) for r in cursor.fetchall()]
    else:
        # Try hitter
        cursor.execute("""
            SELECT p.*, hs.* FROM players p
            LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
            WHERE p.player_id = ?
        """, (player_id,))
        player = cursor.fetchone()
        
        if player:
            player = dict(player)
            player_type = 'hitter'
        else:
            conn.close()
            return "Player not found", 404
    
    conn.close()
    
    return render_template('player.html', player=player, player_type=player_type)


@app.route('/roster-manager')
def roster_manager():
    """Roster management page."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM teams ORDER BY name")
    teams = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return render_template('roster_manager.html', teams=teams)


@app.route('/api/player/<player_id>/move', methods=['POST'])
def api_move_player(player_id):
    """Move player to different team."""
    data = request.json
    new_team = data.get('team_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE players SET team_id = ? WHERE player_id = ?", (new_team, player_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


@app.route('/results')
def results():
    """Results tracking page."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, r.home_f5_actual, r.away_f5_actual, r.home_final, r.away_final
        FROM predictions p
        LEFT JOIN game_results r ON p.prediction_id = r.prediction_id
        ORDER BY p.created_at DESC
        LIMIT 50
    """)
    predictions = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return render_template('results.html', predictions=predictions)


@app.route('/api/result', methods=['POST'])
def api_save_result():
    """Save game result."""
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO game_results (prediction_id, home_f5_actual, away_f5_actual, home_final, away_final)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data['prediction_id'],
        data.get('home_f5_actual'),
        data.get('away_f5_actual'),
        data.get('home_final'),
        data.get('away_final')
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    init_db()
    print("\n" + "=" * 50)
    print("MLB PREDICTION MODEL")
    print("=" * 50)
    print("Open http://localhost:5000 in your browser")
    print("=" * 50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
