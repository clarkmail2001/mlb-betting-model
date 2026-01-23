"""
MLB Prediction Model - v2.0
Fixed projection math + Pitch Arsenal Matchups
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'mlb_model_2026'

DB_PATH = '/tmp/baseball.db' if os.environ.get('RAILWAY_ENVIRONMENT') else 'baseball.db'

# =============================================================================
# TEAM MAPPING
# =============================================================================

TEAM_MAP = {
    'Angels': 'LAA', 'LAA': 'LAA', 'Los Angeles Angels': 'LAA',
    'Diamondbacks': 'ARI', 'ARI': 'ARI', 'D-backs': 'ARI', 'Arizona Diamondbacks': 'ARI',
    'Braves': 'ATL', 'ATL': 'ATL', 'Atlanta Braves': 'ATL',
    'Orioles': 'BAL', 'BAL': 'BAL', 'Baltimore Orioles': 'BAL',
    'Red Sox': 'BOS', 'BOS': 'BOS', 'Boston Red Sox': 'BOS',
    'Cubs': 'CHC', 'CHC': 'CHC', 'Chicago Cubs': 'CHC',
    'White Sox': 'CWS', 'CWS': 'CWS', 'CHW': 'CWS', 'Chicago White Sox': 'CWS',
    'Reds': 'CIN', 'CIN': 'CIN', 'Cincinnati Reds': 'CIN',
    'Guardians': 'CLE', 'CLE': 'CLE', 'Indians': 'CLE', 'Cleveland Guardians': 'CLE',
    'Rockies': 'COL', 'COL': 'COL', 'Colorado Rockies': 'COL',
    'Tigers': 'DET', 'DET': 'DET', 'Detroit Tigers': 'DET',
    'Astros': 'HOU', 'HOU': 'HOU', 'Houston Astros': 'HOU',
    'Royals': 'KC', 'KC': 'KC', 'KCR': 'KC', 'Kansas City Royals': 'KC',
    'Dodgers': 'LAD', 'LAD': 'LAD', 'Los Angeles Dodgers': 'LAD',
    'Marlins': 'MIA', 'MIA': 'MIA', 'Miami Marlins': 'MIA',
    'Brewers': 'MIL', 'MIL': 'MIL', 'Milwaukee Brewers': 'MIL',
    'Twins': 'MIN', 'MIN': 'MIN', 'Minnesota Twins': 'MIN',
    'Mets': 'NYM', 'NYM': 'NYM', 'New York Mets': 'NYM',
    'Yankees': 'NYY', 'NYY': 'NYY', 'New York Yankees': 'NYY',
    'Athletics': 'OAK', 'OAK': 'OAK', "A's": 'OAK', 'Oakland Athletics': 'OAK',
    'Phillies': 'PHI', 'PHI': 'PHI', 'Philadelphia Phillies': 'PHI',
    'Pirates': 'PIT', 'PIT': 'PIT', 'Pittsburgh Pirates': 'PIT',
    'Padres': 'SD', 'SD': 'SD', 'SDP': 'SD', 'San Diego Padres': 'SD',
    'Giants': 'SF', 'SF': 'SF', 'SFG': 'SF', 'San Francisco Giants': 'SF',
    'Mariners': 'SEA', 'SEA': 'SEA', 'Seattle Mariners': 'SEA',
    'Cardinals': 'STL', 'STL': 'STL', 'St. Louis Cardinals': 'STL',
    'Rays': 'TB', 'TB': 'TB', 'TBR': 'TB', 'Tampa Bay Rays': 'TB',
    'Rangers': 'TEX', 'TEX': 'TEX', 'Texas Rangers': 'TEX',
    'Blue Jays': 'TOR', 'TOR': 'TOR', 'Toronto Blue Jays': 'TOR',
    'Nationals': 'WSH', 'WSH': 'WSH', 'WSN': 'WSH', 'Washington Nationals': 'WSH',
}

PITCH_TYPE_MAP = {
    'FF': '4-Seam Fastball', 'SI': 'Sinker', 'FC': 'Cutter', 'SL': 'Slider',
    'ST': 'Sweeper', 'CU': 'Curveball', 'KC': 'Knuckle Curve', 'CH': 'Changeup',
    'FS': 'Splitter', 'KN': 'Knuckleball', 'SC': 'Screwball', 'SV': 'Slurve',
}

LEAGUE_AVG = {
    'woba': 0.315, 'xwoba': 0.315, 'k_rate': 22.5, 'bb_rate': 8.2,
    'era': 4.20, 'xfip': 4.10, 'runs_per_game': 4.5, 'runs_per_f5': 2.5,
    'pa_per_inning': 4.3, 'runs_per_pa': 0.115,
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def safe_float(val, default=None):
    if val is None or val == '' or val == '-' or val == 'NA' or val == 'NULL' or val == 'N/A':
        return default
    try:
        return float(str(val).replace('%', '').replace(',', '').strip())
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def make_player_id(name):
    if not name:
        return None
    return name.lower().replace(' ', '_').replace('.', '').replace("'", '').replace('-', '_').replace(',', '').replace('í', 'i').replace('é', 'e').replace('á', 'a').replace('ñ', 'n').replace('ó', 'o').replace('ú', 'u')

def format_stat(val, decimals=3, mult=1, default='-'):
    if val is None:
        return default
    try:
        return f"{float(val) * mult:.{decimals}f}"
    except:
        return default

# =============================================================================
# DATABASE SETUP
# =============================================================================

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT PRIMARY KEY, name TEXT NOT NULL, abbreviation TEXT NOT NULL,
        league TEXT, division TEXT, park_factor REAL DEFAULT 1.0)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS players (
        player_id TEXT PRIMARY KEY, name TEXT NOT NULL, team_id TEXT,
        position TEXT, bats TEXT DEFAULT 'R', throws TEXT DEFAULT 'R', mlbam_id TEXT)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS pitcher_stats (
        player_id TEXT PRIMARY KEY, games INTEGER, games_started INTEGER,
        innings_pitched REAL, era REAL, xera REAL, fip REAL, xfip REAL,
        whip REAL, k9 REAL, bb9 REAL, hr9 REAL, k_rate REAL, bb_rate REAL,
        babip REAL, lob_pct REAL, gb_pct REAL, hr_fb REAL, fb_velo REAL,
        war REAL, xwoba_against REAL, barrel_rate_against REAL,
        hard_hit_against REAL, whiff_rate REAL, avg_innings_per_start REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS hitter_stats (
        player_id TEXT PRIMARY KEY, pa INTEGER, ab INTEGER, hits INTEGER,
        hr INTEGER, runs INTEGER, rbi INTEGER, bb INTEGER, k INTEGER,
        avg REAL, obp REAL, slg REAL, ops REAL, woba REAL, xwoba REAL,
        wrc_plus REAL, drc_plus REAL, k_rate REAL, bb_rate REAL, iso REAL,
        babip REAL, barrel_rate REAL, hard_hit_rate REAL, avg_exit_velo REAL, war REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS pitch_arsenal (
        id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT, pitch_type TEXT,
        pitch_name TEXT, usage_pct REAL, whiff_rate REAL, put_away_rate REAL,
        ba_against REAL, slg_against REAL, woba_against REAL, xwoba_against REAL,
        hard_hit_rate REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS hitter_vs_pitch (
        id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT, pitch_type TEXT,
        pitch_name TEXT, pa INTEGER, whiff_rate REAL, ba REAL, slg REAL,
        woba REAL, xwoba REAL, run_value REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, game_date TEXT, home_team TEXT,
        away_team TEXT, home_pitcher TEXT, away_pitcher TEXT,
        home_pitcher_id TEXT, away_pitcher_id TEXT, f5_home REAL, f5_away REAL,
        f5_total REAL, full_home REAL, full_away REAL, full_total REAL,
        actual_home INTEGER, actual_away INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    # NEW v3.0 TABLES
    cursor.execute("""CREATE TABLE IF NOT EXISTS catcher_stats (
        player_id TEXT PRIMARY KEY, framing_runs REAL, blocking_runs REAL,
        blocks_above_avg REAL, pop_time_2b REAL, pop_time_3b REAL, max_arm_strength REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS fielding_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT, position TEXT,
        outs_above_avg REAL, fielding_runs_prevented REAL, arm_strength REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS baserunning_stats (
        player_id TEXT PRIMARY KEY, sprint_speed REAL, hp_to_1b REAL,
        bolts INTEGER, competitive_runs INTEGER)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS hitter_splits (
        id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT, split_type TEXT,
        pa INTEGER, bb_rate REAL, k_rate REAL, avg REAL, obp REAL, slg REAL,
        ops REAL, iso REAL, woba REAL, wrc_plus REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS hitter_discipline (
        player_id TEXT PRIMARY KEY, o_swing_pct REAL, z_swing_pct REAL, swing_pct REAL,
        o_contact_pct REAL, z_contact_pct REAL, contact_pct REAL, zone_pct REAL,
        f_strike_pct REAL, swstr_pct REAL, csw_pct REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS hitter_batted_ball (
        player_id TEXT PRIMARY KEY, gb_pct REAL, fb_pct REAL, ld_pct REAL,
        hr_fb REAL, pull_pct REAL, cent_pct REAL, oppo_pct REAL,
        soft_pct REAL, med_pct REAL, hard_pct REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS pitcher_discipline (
        player_id TEXT PRIMARY KEY, o_swing_pct REAL, z_swing_pct REAL, swing_pct REAL,
        o_contact_pct REAL, z_contact_pct REAL, contact_pct REAL, zone_pct REAL,
        f_strike_pct REAL, swstr_pct REAL, csw_pct REAL)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS pitch_movement (
        id INTEGER PRIMARY KEY AUTOINCREMENT, player_id TEXT, pitch_type TEXT,
        pitch_name TEXT, avg_speed REAL, break_z REAL, break_z_induced REAL,
        break_x REAL, pitches_thrown INTEGER)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS model_weights (
        id INTEGER PRIMARY KEY AUTOINCREMENT, weight_name TEXT UNIQUE,
        weight_value REAL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    # CORRECTED weights - the key fix!
    # League avg wOBA (.315) should produce ~0.115 runs/PA
    # Formula: runs = (wOBA - 0.290) × 4.6
    # Verification: (0.315 - 0.290) × 4.6 = 0.115 ✓
    weights = [
        ('pitcher_quality_factor', 0.012), ('platoon_advantage', 0.015),
        ('platoon_disadvantage', -0.020), ('high_k_interaction', -0.008),
        ('low_k_interaction', 0.006), ('park_factor_multiplier', 0.015),
        ('woba_to_runs_multiplier', 4.6),  # FIXED: was 1.15
        ('woba_baseline', 0.290),           # FIXED: was 0.180
        ('arsenal_weight', 0.30),
    ]
    for name, value in weights:
        cursor.execute("INSERT OR REPLACE INTO model_weights (weight_name, weight_value) VALUES (?, ?)", (name, value))
    
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
        cursor.execute("INSERT OR IGNORE INTO teams VALUES (?,?,?,?,?,?)", team)
    
    conn.commit()
    conn.close()

# =============================================================================
# CSV IMPORT
# =============================================================================

def import_csvs():
    conn = get_db()
    cursor = conn.cursor()
    print("=" * 60)
    print("IMPORTING CSV DATA")
    print("=" * 60)
    
    # 1. FanGraphs Hitters
    if os.path.exists('fg_hitters.csv'):
        print("\n[1/7] Loading fg_hitters.csv...")
        with open('fg_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name: continue
                player_id = make_player_id(name)
                team = TEAM_MAP.get(row.get('Team', ''), 'FA')
                cursor.execute("INSERT OR REPLACE INTO players (player_id, name, team_id, position, bats) VALUES (?, ?, ?, 'OF', 'R')", (player_id, name, team))
                cursor.execute("""INSERT OR REPLACE INTO hitter_stats 
                    (player_id, pa, ab, hits, hr, runs, rbi, bb, k, avg, obp, slg, ops, woba, wrc_plus, k_rate, bb_rate, iso, babip, war)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player_id, safe_int(row.get('PA')), safe_int(row.get('AB')), safe_int(row.get('H')),
                     safe_int(row.get('HR')), safe_int(row.get('R')), safe_int(row.get('RBI')),
                     safe_int(row.get('BB')), safe_int(row.get('K')), safe_float(row.get('AVG')),
                     safe_float(row.get('OBP')), safe_float(row.get('SLG')), safe_float(row.get('OPS')),
                     safe_float(row.get('wOBA')), safe_float(row.get('wRC+')), safe_float(row.get('K%')),
                     safe_float(row.get('BB%')), safe_float(row.get('ISO')), safe_float(row.get('BABIP')),
                     safe_float(row.get('WAR'))))
                count += 1
            print(f"      Loaded {count} hitters")
    
    # 2. Savant Hitters
    if os.path.exists('savant_hitters.csv'):
        print("\n[2/7] Loading savant_hitters.csv...")
        with open('savant_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                if not name or name == ' ': continue
                player_id = make_player_id(name)
                cursor.execute("""UPDATE hitter_stats SET xwoba=COALESCE(?,xwoba), barrel_rate=COALESCE(?,barrel_rate),
                    hard_hit_rate=COALESCE(?,hard_hit_rate), avg_exit_velo=COALESCE(?,avg_exit_velo) WHERE player_id=?""",
                    (safe_float(row.get('xwoba')), safe_float(row.get('barrel_batted_rate')),
                     safe_float(row.get('hard_hit_percent')), safe_float(row.get('avg_best_speed')), player_id))
                if cursor.rowcount > 0: count += 1
            print(f"      Updated {count} hitters with Savant data")
    
    # 3. BP Hitters (DRC+)
    if os.path.exists('bp_hitters.csv'):
        print("\n[3/7] Loading bp_hitters.csv...")
        with open('bp_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', '')
                if not name: continue
                player_id = make_player_id(name)
                cursor.execute("UPDATE hitter_stats SET drc_plus=? WHERE player_id=?", (safe_float(row.get('DRC+')), player_id))
                if cursor.rowcount > 0: count += 1
            print(f"      Updated {count} hitters with DRC+")
    
    # 4. FanGraphs Pitchers
    if os.path.exists('fg_pitchers.csv'):
        print("\n[4/7] Loading fg_pitchers.csv...")
        with open('fg_pitchers.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name: continue
                player_id = make_player_id(name)
                team = TEAM_MAP.get(row.get('Team', ''), 'FA')
                mlbam = row.get('MLBAMID', '')
                cursor.execute("INSERT OR REPLACE INTO players (player_id, name, team_id, position, throws, mlbam_id) VALUES (?, ?, ?, 'P', 'R', ?)",
                    (player_id, name, team, mlbam))
                ip = safe_float(row.get('IP'), 0)
                gs = safe_int(row.get('GS'), 0)
                avg_ip = (ip / gs) if gs > 0 else 5.0
                cursor.execute("""INSERT OR REPLACE INTO pitcher_stats 
                    (player_id, games, games_started, innings_pitched, era, xera, fip, xfip, k9, bb9, hr9, babip, lob_pct, gb_pct, hr_fb, fb_velo, war, avg_innings_per_start)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player_id, safe_int(row.get('G')), safe_int(row.get('GS')), safe_float(row.get('IP')),
                     safe_float(row.get('ERA')), safe_float(row.get('xERA')), safe_float(row.get('FIP')),
                     safe_float(row.get('xFIP')), safe_float(row.get('K/9')), safe_float(row.get('BB/9')),
                     safe_float(row.get('HR/9')), safe_float(row.get('BABIP')), safe_float(row.get('LOB%')),
                     safe_float(row.get('GB%')), safe_float(row.get('HR/FB')), safe_float(row.get('vFA (pi)')),
                     safe_float(row.get('WAR')), avg_ip))
                count += 1
            print(f"      Loaded {count} pitchers")
    
    # 5. Pitch Mix
    if os.path.exists('fg_pitch_mix.csv'):
        print("\n[5/7] Loading fg_pitch_mix.csv...")
        with open('fg_pitch_mix.csv', 'r', encoding='utf-8-sig') as f:
            count = sum(1 for _ in csv.DictReader(f))
            print(f"      Processed {count} rows")
    
    # 6. Savant Pitchers (pitch arsenal)
    if os.path.exists('savant_pitchers.csv'):
        print("\n[6/7] Loading savant_pitchers.csv...")
        cursor.execute("DELETE FROM pitch_arsenal")
        with open('savant_pitchers.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            player_data = {}
            for row in reader:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                if not name or name == ' ': continue
                player_id = make_player_id(name)
                pitch_type = row.get('pitch_type', '')
                cursor.execute("""INSERT INTO pitch_arsenal (player_id, pitch_type, pitch_name, usage_pct, whiff_rate, put_away_rate, ba_against, slg_against, woba_against, xwoba_against, hard_hit_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player_id, pitch_type, row.get('pitch_name', PITCH_TYPE_MAP.get(pitch_type, pitch_type)),
                     safe_float(row.get('pitch_usage')), safe_float(row.get('whiff_percent')),
                     safe_float(row.get('put_away')), safe_float(row.get('ba')), safe_float(row.get('slg')),
                     safe_float(row.get('woba')), safe_float(row.get('est_woba')), safe_float(row.get('hard_hit_percent'))))
                usage = safe_float(row.get('pitch_usage'), 0)
                xwoba = safe_float(row.get('est_woba'))
                if player_id not in player_data:
                    player_data[player_id] = {'usage': 0, 'xwoba': 0, 'whiff': 0, 'hh': 0}
                if usage and xwoba:
                    player_data[player_id]['usage'] += usage
                    player_data[player_id]['xwoba'] += usage * xwoba
                count += 1
            for pid, data in player_data.items():
                if data['usage'] > 0:
                    cursor.execute("UPDATE pitcher_stats SET xwoba_against=? WHERE player_id=?",
                        (data['xwoba'] / data['usage'], pid))
            print(f"      Loaded {count} pitch arsenal rows")
    
    # 7. Hitter vs Pitch Type (NEW!)
    if os.path.exists('savant_hitters_pitch_arsenal.csv'):
        print("\n[7/7] Loading savant_hitters_pitch_arsenal.csv...")
        cursor.execute("DELETE FROM hitter_vs_pitch")
        with open('savant_hitters_pitch_arsenal.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                first = row.get('first_name', row.get('name_first', ''))
                last = row.get('last_name', row.get('name_last', ''))
                if not first and not last:
                    full = row.get('player_name', row.get('name', ''))
                    if full:
                        parts = full.split(' ', 1)
                        first, last = (parts[0], parts[1]) if len(parts) > 1 else (parts[0], '')
                name = f"{first} {last}".strip()
                if not name or name == ' ': continue
                player_id = make_player_id(name)
                pitch_type = row.get('pitch_type', '')
                cursor.execute("""INSERT INTO hitter_vs_pitch (player_id, pitch_type, pitch_name, pa, whiff_rate, ba, slg, woba, xwoba, run_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player_id, pitch_type, row.get('pitch_name', PITCH_TYPE_MAP.get(pitch_type, pitch_type)),
                     safe_int(row.get('pa', row.get('pitches', 0))), safe_float(row.get('whiff_percent', row.get('whiff_rate'))),
                     safe_float(row.get('ba', row.get('batting_avg'))), safe_float(row.get('slg', row.get('slugging'))),
                     safe_float(row.get('woba')), safe_float(row.get('est_woba', row.get('xwoba'))),
                     safe_float(row.get('run_value', row.get('rv')))))
                count += 1
            print(f"      Loaded {count} hitter vs pitch rows")
    else:
        print("\n[7/7] savant_hitters_pitch_arsenal.csv not found")
    
    # 8. Catcher Framing
    if os.path.exists('catcher-framing.csv'):
        print("\n[8] Loading catcher-framing.csv...")
        with open('catcher-framing.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('name', '')
                if not name: continue
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO catcher_stats (player_id, framing_runs) VALUES (?, ?)",
                    (player_id, safe_float(row.get('rv_tot'))))
                count += 1
            print(f"      Loaded {count} catcher framing rows")
    
    # 9. Catcher Blocking
    if os.path.exists('catcher_blocking.csv'):
        print("\n[9] Loading catcher_blocking.csv...")
        with open('catcher_blocking.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('player_name', '')
                if not name: continue
                if ',' in name:
                    parts = name.split(',', 1)
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                player_id = make_player_id(name)
                cursor.execute("UPDATE catcher_stats SET blocking_runs=?, blocks_above_avg=? WHERE player_id=?",
                    (safe_float(row.get('catcher_blocking_runs')), safe_float(row.get('blocks_above_average')), player_id))
                if cursor.rowcount == 0:
                    cursor.execute("INSERT INTO catcher_stats (player_id, blocking_runs, blocks_above_avg) VALUES (?, ?, ?)",
                        (player_id, safe_float(row.get('catcher_blocking_runs')), safe_float(row.get('blocks_above_average'))))
                count += 1
            print(f"      Loaded {count} catcher blocking rows")
    
    # 10. Catcher Poptime
    if os.path.exists('poptime.csv'):
        print("\n[10] Loading poptime.csv...")
        with open('poptime.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('entity_name', '')
                if not name: continue
                if ',' in name:
                    parts = name.split(',', 1)
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                player_id = make_player_id(name)
                cursor.execute("UPDATE catcher_stats SET pop_time_2b=?, pop_time_3b=?, max_arm_strength=? WHERE player_id=?",
                    (safe_float(row.get('pop_2b_sba')), safe_float(row.get('pop_3b_sba')), safe_float(row.get('maxeff_arm_2b_3b_sba')), player_id))
                if cursor.rowcount == 0:
                    cursor.execute("INSERT INTO catcher_stats (player_id, pop_time_2b, pop_time_3b, max_arm_strength) VALUES (?, ?, ?, ?)",
                        (player_id, safe_float(row.get('pop_2b_sba')), safe_float(row.get('pop_3b_sba')), safe_float(row.get('maxeff_arm_2b_3b_sba'))))
                count += 1
            print(f"      Loaded {count} catcher poptime rows")
    
    # 11. Fielding OAA
    if os.path.exists('outs_above_average.csv'):
        print("\n[11] Loading outs_above_average.csv...")
        cursor.execute("DELETE FROM fielding_stats")
        with open('outs_above_average.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('last_name, first_name', '')
                if not name: continue
                if ',' in name:
                    parts = name.split(',', 1)
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO fielding_stats (player_id, position, outs_above_avg, fielding_runs_prevented) VALUES (?, ?, ?, ?)",
                    (player_id, row.get('primary_pos_formatted', ''), safe_float(row.get('outs_above_average')), safe_float(row.get('fielding_runs_prevented'))))
                count += 1
            print(f"      Loaded {count} fielding OAA rows")
    
    # 12. Arm Strength
    if os.path.exists('arm_strength.csv'):
        print("\n[12] Loading arm_strength.csv...")
        with open('arm_strength.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('fielder_name', '')
                if not name: continue
                if ',' in name:
                    parts = name.split(',', 1)
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                player_id = make_player_id(name)
                arm = safe_float(row.get('arm_overall')) or safe_float(row.get('max_arm_strength'))
                cursor.execute("UPDATE fielding_stats SET arm_strength=? WHERE player_id=?", (arm, player_id))
                count += 1
            print(f"      Updated {count} arm strength rows")
    
    # 13. Sprint Speed
    if os.path.exists('sprint_speed.csv'):
        print("\n[13] Loading sprint_speed.csv...")
        cursor.execute("DELETE FROM baserunning_stats")
        with open('sprint_speed.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('last_name, first_name', '')
                if not name: continue
                if ',' in name:
                    parts = name.split(',', 1)
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO baserunning_stats (player_id, sprint_speed, hp_to_1b, bolts, competitive_runs) VALUES (?, ?, ?, ?, ?)",
                    (player_id, safe_float(row.get('sprint_speed')), safe_float(row.get('hp_to_1b')), safe_int(row.get('bolts')), safe_int(row.get('competitive_runs'))))
                count += 1
            print(f"      Loaded {count} sprint speed rows")
    
    # 14. Hitter Splits vs LHP
    if os.path.exists('Splits_Leaderboard_Data_vs_LHP.csv'):
        print("\n[14] Loading Splits vs LHP...")
        cursor.execute("DELETE FROM hitter_splits WHERE split_type='vs_LHP'")
        with open('Splits_Leaderboard_Data_vs_LHP.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', '')
                if not name: continue
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO hitter_splits (player_id, split_type, pa, bb_rate, k_rate, avg, obp, slg, ops, iso, woba, wrc_plus) VALUES (?, 'vs_LHP', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, safe_int(row.get('PA')), safe_float(row.get('BB%')), safe_float(row.get('K%')), safe_float(row.get('AVG')), safe_float(row.get('OBP')), safe_float(row.get('SLG')), safe_float(row.get('OPS')), safe_float(row.get('ISO')), safe_float(row.get('wOBA')), safe_float(row.get('wRC+'))))
                count += 1
            print(f"      Loaded {count} hitter vs LHP rows")
    
    # 15. Hitter Splits vs RHP
    if os.path.exists('Splits_Leaderboard_Data_vs_RHP.csv'):
        print("\n[15] Loading Splits vs RHP...")
        cursor.execute("DELETE FROM hitter_splits WHERE split_type='vs_RHP'")
        with open('Splits_Leaderboard_Data_vs_RHP.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', '')
                if not name: continue
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO hitter_splits (player_id, split_type, pa, bb_rate, k_rate, avg, obp, slg, ops, iso, woba, wrc_plus) VALUES (?, 'vs_RHP', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, safe_int(row.get('PA')), safe_float(row.get('BB%')), safe_float(row.get('K%')), safe_float(row.get('AVG')), safe_float(row.get('OBP')), safe_float(row.get('SLG')), safe_float(row.get('OPS')), safe_float(row.get('ISO')), safe_float(row.get('wOBA')), safe_float(row.get('wRC+'))))
                count += 1
            print(f"      Loaded {count} hitter vs RHP rows")
    
    # 16. Hitter Discipline
    if os.path.exists('fangraphs-leaderboards.csv'):
        print("\n[16] Loading hitter discipline...")
        cursor.execute("DELETE FROM hitter_discipline")
        with open('fangraphs-leaderboards.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name: continue
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO hitter_discipline (player_id, o_swing_pct, z_swing_pct, swing_pct, o_contact_pct, z_contact_pct, contact_pct, zone_pct, f_strike_pct, swstr_pct, csw_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, safe_float(row.get('O-Swing%')), safe_float(row.get('Z-Swing%')), safe_float(row.get('Swing%')), safe_float(row.get('O-Contact%')), safe_float(row.get('Z-Contact%')), safe_float(row.get('Contact%')), safe_float(row.get('Zone%')), safe_float(row.get('F-Strike%')), safe_float(row.get('SwStr%')), safe_float(row.get('CSW%'))))
                count += 1
            print(f"      Loaded {count} hitter discipline rows")
    
    # 17. Hitter Batted Ball
    if os.path.exists('fangraphs-leaderboards-2.csv'):
        print("\n[17] Loading hitter batted ball...")
        cursor.execute("DELETE FROM hitter_batted_ball")
        with open('fangraphs-leaderboards-2.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name: continue
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO hitter_batted_ball (player_id, gb_pct, fb_pct, ld_pct, hr_fb, pull_pct, cent_pct, oppo_pct, soft_pct, med_pct, hard_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, safe_float(row.get('GB%')), safe_float(row.get('FB%')), safe_float(row.get('LD%')), safe_float(row.get('HR/FB')), safe_float(row.get('Pull%')), safe_float(row.get('Cent%')), safe_float(row.get('Oppo%')), safe_float(row.get('Soft%')), safe_float(row.get('Med%')), safe_float(row.get('Hard%'))))
                count += 1
            print(f"      Loaded {count} hitter batted ball rows")
    
    # 18. Pitcher Discipline
    if os.path.exists('fangraphs-leaderboards-4.csv'):
        print("\n[18] Loading pitcher discipline...")
        cursor.execute("DELETE FROM pitcher_discipline")
        with open('fangraphs-leaderboards-4.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name: continue
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO pitcher_discipline (player_id, o_swing_pct, z_swing_pct, swing_pct, o_contact_pct, z_contact_pct, contact_pct, zone_pct, f_strike_pct, swstr_pct, csw_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, safe_float(row.get('O-Swing%')), safe_float(row.get('Z-Swing%')), safe_float(row.get('Swing%')), safe_float(row.get('O-Contact%')), safe_float(row.get('Z-Contact%')), safe_float(row.get('Contact%')), safe_float(row.get('Zone%')), safe_float(row.get('F-Strike%')), safe_float(row.get('SwStr%')), safe_float(row.get('CSW%'))))
                count += 1
            print(f"      Loaded {count} pitcher discipline rows")
    
    # 19. Pitch Movement
    if os.path.exists('pitch_movement.csv'):
        print("\n[19] Loading pitch movement...")
        cursor.execute("DELETE FROM pitch_movement")
        with open('pitch_movement.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('last_name, first_name', '')
                if not name: continue
                if ',' in name:
                    parts = name.split(',', 1)
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                player_id = make_player_id(name)
                cursor.execute("INSERT OR REPLACE INTO pitch_movement (player_id, pitch_type, pitch_name, avg_speed, break_z, break_z_induced, break_x, pitches_thrown) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, row.get('pitch_type', ''), row.get('pitch_type_name', ''), safe_float(row.get('avg_speed')), safe_float(row.get('pitcher_break_z')), safe_float(row.get('pitcher_break_z_induced')), safe_float(row.get('pitcher_break_x')), safe_int(row.get('pitches_thrown'))))
                count += 1
            print(f"      Loaded {count} pitch movement rows")
    
    conn.commit()
    
    # Print summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    cursor.execute("SELECT COUNT(*) as c FROM players WHERE position='P'")
    p_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM players WHERE position!='P'")
    h_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM pitch_arsenal")
    a_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM hitter_vs_pitch")
    hvp_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM catcher_stats")
    c_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM fielding_stats")
    f_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM baserunning_stats")
    b_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM hitter_splits")
    s_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM hitter_discipline")
    hd_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM pitcher_discipline")
    pd_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM pitch_movement")
    pm_count = cursor.fetchone()['c']
    
    print(f"  Pitchers: {p_count}")
    print(f"  Hitters: {h_count}")
    print(f"  Pitch Arsenal: {a_count}")
    print(f"  Hitter vs Pitch: {hvp_count}")
    print(f"  Catchers: {c_count}")
    print(f"  Fielding: {f_count}")
    print(f"  Baserunning: {b_count}")
    print(f"  Hitter Splits: {s_count}")
    print(f"  Hitter Discipline: {hd_count}")
    print(f"  Pitcher Discipline: {pd_count}")
    print(f"  Pitch Movement: {pm_count}")
    
    conn.close()
    return {'pitchers': p_count, 'hitters': h_count, 'arsenal': a_count, 'hitter_vs_pitch': hvp_count, 
            'catchers': c_count, 'fielding': f_count, 'baserunning': b_count, 'splits': s_count,
            'hitter_discipline': hd_count, 'pitcher_discipline': pd_count, 'pitch_movement': pm_count}

# =============================================================================
# PROJECTION ENGINE - v3.0 FULLY INTEGRATED
# =============================================================================
# 
# HOW THE MODEL CALCULATES RUNS:
# 
# For each hitter vs pitcher matchup:
#   1. GET BASELINE wOBA
#      - Use vs LHP or vs RHP split if available (priority)
#      - Otherwise use (overall wOBA + xwOBA) / 2
#   
#   2. PITCH ARSENAL MATCHUP
#      - For each pitch the pitcher throws (weighted by usage %):
#        - Get pitcher's wOBA allowed on that pitch
#        - Get hitter's wOBA vs that pitch type
#        - Average them = matchup wOBA for that pitch
#      - Weighted sum = overall arsenal matchup wOBA
#      - Blend with baseline (30% weight)
#   
#   3. PITCHER QUALITY ADJUSTMENT
#      - Compare pitcher xFIP to league average (4.10)
#      - Elite pitcher (3.00 xFIP) = -0.013 wOBA adjustment
#      - Bad pitcher (5.00 xFIP) = +0.011 wOBA adjustment
#   
#   4. PLATOON/DISCIPLINE ADJUSTMENT
#      - High chase hitter vs high chase-inducing pitcher = penalty
#      - Contact hitter vs contact-suppressing pitcher = penalty
#   
#   5. K-RATE INTERACTION
#      - High-K pitcher vs High-K hitter = -0.008 wOBA
#      - Low-K matchup = +0.006 wOBA
#   
#   6. PARK FACTOR
#      - Coors Field (1.15) = +0.002 wOBA
#      - Petco (0.97) = -0.0005 wOBA
#   
#   7. CATCHER FRAMING ADJUSTMENT
#      - Elite framer (+10 runs) helps pitcher = -0.003 wOBA
#      - Bad framer (-10 runs) hurts pitcher = +0.003 wOBA
#   
#   8. DEFENSE ADJUSTMENT
#      - Good team defense = fewer runs on balls in play
#   
#   9. CONVERT TO RUNS
#      - Runs per PA = (Projected wOBA - 0.290) × 4.6
#      - Bounded: 0.05 to 0.18 runs/PA
#   
#   10. EXPECTED PA BY LINEUP POSITION
#       - Leadoff: 13.7% of team PA
#       - #2: 13.0%, #3: 12.3%, etc.
#       - Total F5 PA ≈ 21.5 (4.3 PA/inning × 5)
#   
#   11. PLAYER RUNS = Runs/PA × Expected PA
#   
#   12. TEAM F5 RUNS = Sum of all 9 hitters
#   
#   13. FULL GAME
#       - Scale F5 to starter's expected innings
#       - Add bullpen runs (league avg rate × remaining innings)
#
# =============================================================================

def get_model_weights():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT weight_name, weight_value FROM model_weights")
    weights = {row['weight_name']: row['weight_value'] for row in cursor.fetchall()}
    conn.close()
    return weights

def get_pitcher_arsenal(player_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""SELECT pitch_type, pitch_name, usage_pct, woba_against, xwoba_against, whiff_rate
        FROM pitch_arsenal WHERE player_id=? AND usage_pct>5 ORDER BY usage_pct DESC""", (player_id,))
    arsenal = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return arsenal

def get_hitter_vs_pitch(player_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT pitch_type, woba, xwoba, whiff_rate, run_value FROM hitter_vs_pitch WHERE player_id=?", (player_id,))
    vs_pitch = {row['pitch_type']: dict(row) for row in cursor.fetchall()}
    conn.close()
    return vs_pitch

def get_hitter_split(player_id, pitcher_hand):
    """Get hitter's stats vs LHP or RHP"""
    conn = get_db()
    cursor = conn.cursor()
    split_type = 'vs_LHP' if pitcher_hand == 'L' else 'vs_RHP'
    cursor.execute("SELECT * FROM hitter_splits WHERE player_id=? AND split_type=?", (player_id, split_type))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_hitter_discipline(player_id):
    """Get hitter's plate discipline metrics"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hitter_discipline WHERE player_id=?", (player_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_pitcher_discipline(player_id):
    """Get pitcher's plate discipline metrics"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pitcher_discipline WHERE player_id=?", (player_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_catcher_stats(player_id):
    """Get catcher framing/blocking stats"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM catcher_stats WHERE player_id=?", (player_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_team_defense(team_id):
    """Get team's total defensive value (sum of OAA for starters)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""SELECT SUM(outs_above_avg) as total_oaa, SUM(fielding_runs_prevented) as total_frp
        FROM fielding_stats f JOIN players p ON f.player_id = p.player_id
        WHERE p.team_id = ?""", (team_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row['total_oaa']:
        return {'oaa': row['total_oaa'], 'frp': row['total_frp']}
    return None

def calculate_arsenal_matchup(pitcher_arsenal, hitter_vs_pitch, weights):
    """Weight each pitch by usage and get matchup-specific expected wOBA."""
    if not pitcher_arsenal:
        return None, []
    weighted_woba = 0
    total_usage = 0
    breakdown = []
    for pitch in pitcher_arsenal:
        pitch_type = pitch['pitch_type']
        usage = (pitch['usage_pct'] or 0) / 100
        if usage <= 0:
            continue
        p_woba = pitch['woba_against'] or pitch['xwoba_against'] or LEAGUE_AVG['woba']
        if pitch_type in hitter_vs_pitch:
            h_woba = hitter_vs_pitch[pitch_type].get('woba') or hitter_vs_pitch[pitch_type].get('xwoba') or LEAGUE_AVG['woba']
        else:
            h_woba = LEAGUE_AVG['woba']
        matchup_woba = (p_woba + h_woba) / 2
        weighted_woba += usage * matchup_woba
        total_usage += usage
        breakdown.append({
            'pitch': pitch['pitch_name'] or pitch_type,
            'usage': round(usage * 100, 1),
            'pitcher_woba': round(p_woba, 3) if p_woba else '-',
            'hitter_woba': round(h_woba, 3) if h_woba else '-',
            'matchup_woba': round(matchup_woba, 3)
        })
    if total_usage > 0:
        return round(weighted_woba / total_usage, 3), breakdown
    return None, []

def calculate_matchup_detailed(pitcher, hitter, park_factor=1.0, weights=None, pitcher_arsenal=None, hitter_vs_pitch=None, pitcher_hand='R', catcher=None, team_defense=None):
    """Calculate single batter vs pitcher matchup with full transparency."""
    if weights is None:
        weights = get_model_weights()
    breakdown = {'hitter_name': hitter.get('name', 'Unknown'), 'steps': []}
    
    # ===========================================
    # STEP 1: BASELINE wOBA (with L/R splits)
    # ===========================================
    split_data = get_hitter_split(hitter.get('player_id', ''), pitcher_hand)
    
    if split_data and split_data.get('woba'):
        # USE SPLIT DATA - this is the key integration
        baseline = split_data['woba']
        split_pa = split_data.get('pa', 0)
        breakdown['steps'].append({
            'name': f"Baseline wOBA (vs {pitcher_hand}HP)", 
            'formula': f"Split wOBA from {split_pa} PA vs {pitcher_hand}HP",
            'values': f"vs {pitcher_hand}HP: {baseline:.3f}", 
            'result': round(baseline, 3)
        })
        breakdown['used_split'] = True
        breakdown['split_pa'] = split_pa
    else:
        # Fallback to overall stats
        h_woba = hitter.get('woba') or LEAGUE_AVG['woba']
        h_xwoba = hitter.get('xwoba') or h_woba
        baseline = (h_woba + h_xwoba) / 2
        breakdown['steps'].append({
            'name': 'Baseline wOBA', 
            'formula': '(wOBA + xwOBA) / 2',
            'values': f"({format_stat(h_woba)} + {format_stat(h_xwoba)}) / 2", 
            'result': round(baseline, 3)
        })
        breakdown['used_split'] = False
    
    # ===========================================
    # STEP 2: PITCH ARSENAL MATCHUP
    # ===========================================
    arsenal_adj = 0
    arsenal_breakdown = []
    arsenal_weight = weights.get('arsenal_weight', 0.30)
    if pitcher_arsenal and hitter_vs_pitch:
        arsenal_woba, arsenal_breakdown = calculate_arsenal_matchup(pitcher_arsenal, hitter_vs_pitch, weights)
        if arsenal_woba:
            arsenal_adj = (arsenal_woba - baseline) * arsenal_weight
            breakdown['steps'].append({
                'name': 'Pitch Arsenal Matchup',
                'formula': f"(Arsenal wOBA - Baseline) × {arsenal_weight}",
                'values': f"({arsenal_woba:.3f} - {baseline:.3f}) × {arsenal_weight}",
                'result': round(arsenal_adj, 4)
            })
            breakdown['arsenal_breakdown'] = arsenal_breakdown
    
    # ===========================================
    # STEP 3: PITCHER QUALITY
    # ===========================================
    p_xfip = pitcher.get('xfip') or pitcher.get('era') or LEAGUE_AVG['xfip']
    pitcher_factor = weights.get('pitcher_quality_factor', 0.012)
    pitcher_adj = (LEAGUE_AVG['xfip'] - p_xfip) * pitcher_factor
    breakdown['steps'].append({
        'name': 'Pitcher Quality', 
        'formula': f"(League xFIP - Pitcher xFIP) × {pitcher_factor}",
        'values': f"({LEAGUE_AVG['xfip']:.2f} - {p_xfip:.2f}) × {pitcher_factor}", 
        'result': round(pitcher_adj, 4)
    })
    
    # ===========================================
    # STEP 4: DISCIPLINE MATCHUP
    # ===========================================
    discipline_adj = 0
    h_disc = get_hitter_discipline(hitter.get('player_id', ''))
    p_disc = get_pitcher_discipline(pitcher.get('player_id', ''))
    
    if h_disc and p_disc:
        # Chase rate interaction: high chase hitter vs high chase-inducing pitcher
        h_chase = h_disc.get('o_swing_pct') or 0.30
        p_chase_rate = p_disc.get('o_swing_pct') or 0.30  # How often batters chase vs this pitcher
        
        # High chase hitter (>35%) vs pitcher who induces chase (>35%) = bad for hitter
        if h_chase > 0.35 and p_chase_rate > 0.35:
            discipline_adj = -0.008
            breakdown['steps'].append({
                'name': 'Discipline Matchup',
                'formula': 'High chase hitter vs chase-inducing pitcher',
                'values': f"H O-Swing: {h_chase:.1%}, P O-Swing: {p_chase_rate:.1%}",
                'result': round(discipline_adj, 4)
            })
        # Low chase hitter vs pitcher who can't induce chase = good for hitter
        elif h_chase < 0.28 and p_chase_rate < 0.28:
            discipline_adj = 0.005
            breakdown['steps'].append({
                'name': 'Discipline Matchup',
                'formula': 'Patient hitter vs non-chase pitcher',
                'values': f"H O-Swing: {h_chase:.1%}, P O-Swing: {p_chase_rate:.1%}",
                'result': round(discipline_adj, 4)
            })
    
    # ===========================================
    # STEP 5: K-RATE INTERACTION
    # ===========================================
    p_k9 = pitcher.get('k9') or 9.0
    h_k_rate = hitter.get('k_rate') or LEAGUE_AVG['k_rate']
    if p_k9 > 10.0 and h_k_rate > 25:
        k_adj = weights.get('high_k_interaction', -0.008)
        k_reason = f"High-K matchup (P K/9: {p_k9:.1f}, H K%: {h_k_rate:.1f}%)"
    elif p_k9 < 7.0 and h_k_rate < 18:
        k_adj = weights.get('low_k_interaction', 0.006)
        k_reason = f"Low-K matchup (P K/9: {p_k9:.1f}, H K%: {h_k_rate:.1f}%)"
    else:
        k_adj = 0
        k_reason = f"Neutral K (P K/9: {p_k9:.1f}, H K%: {h_k_rate:.1f}%)"
    breakdown['steps'].append({
        'name': 'K-Rate Interaction', 
        'formula': k_reason, 
        'values': '', 
        'result': round(k_adj, 4)
    })
    
    # ===========================================
    # STEP 6: PARK FACTOR
    # ===========================================
    park_mult = weights.get('park_factor_multiplier', 0.015)
    park_adj = (park_factor - 1.0) * park_mult
    breakdown['steps'].append({
        'name': 'Park Factor', 
        'formula': f"(Park - 1.0) × {park_mult}",
        'values': f"({park_factor:.2f} - 1.0) × {park_mult}", 
        'result': round(park_adj, 4)
    })
    
    # ===========================================
    # STEP 7: CATCHER FRAMING
    # ===========================================
    catcher_adj = 0
    if catcher:
        catcher_stats = get_catcher_stats(catcher.get('player_id', ''))
        if catcher_stats and catcher_stats.get('framing_runs'):
            framing = catcher_stats['framing_runs']
            # ~10 framing runs over season = ~0.003 wOBA impact per PA
            catcher_adj = -framing * 0.0003  # Negative because good framing helps pitcher
            breakdown['steps'].append({
                'name': 'Catcher Framing',
                'formula': f"Framing runs ({framing:.1f}) × -0.0003",
                'values': f"{catcher.get('name', 'Unknown')}: {framing:.1f} framing runs",
                'result': round(catcher_adj, 4)
            })
    
    # ===========================================
    # STEP 8: TEAM DEFENSE (applied at team level, small per-PA impact)
    # ===========================================
    defense_adj = 0
    if team_defense and team_defense.get('oaa'):
        oaa = team_defense['oaa']
        # Good defense (OAA +20) = ~0.002 wOBA saved per PA
        defense_adj = -oaa * 0.0001
        breakdown['steps'].append({
            'name': 'Team Defense',
            'formula': f"Team OAA ({oaa:.0f}) × -0.0001",
            'values': f"Total OAA: {oaa:.0f}",
            'result': round(defense_adj, 4)
        })
    
    # ===========================================
    # STEP 9: FINAL PROJECTED wOBA
    # ===========================================
    total_adj = arsenal_adj + pitcher_adj + discipline_adj + k_adj + park_adj + catcher_adj + defense_adj
    proj_woba = max(0.250, min(0.420, baseline + total_adj))
    breakdown['steps'].append({
        'name': 'Projected wOBA', 
        'formula': 'Baseline + All Adjustments',
        'values': f"{baseline:.3f} + {total_adj:.4f}", 
        'result': round(proj_woba, 3)
    })
    
    # ===========================================
    # STEP 10: CONVERT TO RUNS
    # ===========================================
    woba_baseline = weights.get('woba_baseline', 0.290)
    woba_mult = weights.get('woba_to_runs_multiplier', 4.6)
    raw_runs = (proj_woba - woba_baseline) * woba_mult
    runs_per_pa = max(0.05, min(0.18, raw_runs))  # Tighter bounds for realistic totals
    breakdown['steps'].append({
        'name': 'Runs per PA', 
        'formula': f"(wOBA - {woba_baseline}) × {woba_mult}",
        'values': f"({proj_woba:.3f} - {woba_baseline}) × {woba_mult} = {raw_runs:.4f} → {runs_per_pa:.4f}", 
        'result': round(runs_per_pa, 4)
    })
    
    # Summary
    breakdown['baseline_woba'] = round(baseline, 3)
    breakdown['projected_woba'] = round(proj_woba, 3)
    breakdown['runs_per_pa'] = round(runs_per_pa, 4)
    breakdown['advantage'] = 'hitter' if proj_woba > 0.350 else ('pitcher' if proj_woba < 0.280 else 'neutral')
    return breakdown

def estimate_pitcher_innings(pitcher):
    avg_ip = pitcher.get('avg_innings_per_start')
    if avg_ip and avg_ip > 0:
        return min(7.0, max(4.0, avg_ip))
    ip = pitcher.get('innings_pitched', 0)
    gs = pitcher.get('games_started', 0)
    if gs and gs > 0:
        return min(7.0, max(4.0, ip / gs))
    return 5.0

def project_game(home_pitcher, away_pitcher, home_lineup, away_lineup, park_factor=1.0, home_catcher=None, away_catcher=None, home_team_id=None, away_team_id=None):
    """Full game projection with all data integrated."""
    weights = get_model_weights()
    pa_weights = [0.137, 0.130, 0.123, 0.116, 0.109, 0.103, 0.097, 0.093, 0.092]
    home_p_ip = estimate_pitcher_innings(home_pitcher)
    away_p_ip = estimate_pitcher_innings(away_pitcher)
    f5_pa = LEAGUE_AVG['pa_per_inning'] * 5
    
    home_arsenal = get_pitcher_arsenal(home_pitcher.get('player_id', ''))
    away_arsenal = get_pitcher_arsenal(away_pitcher.get('player_id', ''))
    
    # Get pitcher handedness (default R if not specified)
    home_p_hand = home_pitcher.get('throws', 'R') or 'R'
    away_p_hand = away_pitcher.get('throws', 'R') or 'R'
    
    # Get team defense stats
    home_defense = get_team_defense(home_team_id) if home_team_id else None
    away_defense = get_team_defense(away_team_id) if away_team_id else None
    
    result = {
        'home_pitcher': {
            'name': home_pitcher.get('name', 'Unknown'), 
            'player_id': home_pitcher.get('player_id', ''),
            'estimated_innings': round(home_p_ip, 1), 
            'era': home_pitcher.get('era'), 
            'xfip': home_pitcher.get('xfip'),
            'k9': home_pitcher.get('k9'), 
            'throws': home_p_hand,
            'arsenal_count': len(home_arsenal)
        },
        'away_pitcher': {
            'name': away_pitcher.get('name', 'Unknown'), 
            'player_id': away_pitcher.get('player_id', ''),
            'estimated_innings': round(away_p_ip, 1), 
            'era': away_pitcher.get('era'), 
            'xfip': away_pitcher.get('xfip'),
            'k9': away_pitcher.get('k9'), 
            'throws': away_p_hand,
            'arsenal_count': len(away_arsenal)
        },
        'park_factor': park_factor, 
        'away_matchups': [], 
        'home_matchups': [],
    }
    
    # Track how many hitters used split data
    away_splits_used = 0
    home_splits_used = 0
    
    # Away team vs Home pitcher
    away_f5_runs = 0
    for i, hitter in enumerate(away_lineup[:9]):
        if not hitter: continue
        hvp = get_hitter_vs_pitch(hitter.get('player_id', ''))
        matchup = calculate_matchup_detailed(
            home_pitcher, hitter, park_factor, weights, 
            home_arsenal, hvp, home_p_hand, home_catcher, home_defense
        )
        matchup['lineup_position'] = i + 1
        matchup['pa_share'] = pa_weights[i] if i < len(pa_weights) else 0.09
        matchup['expected_pa'] = round(f5_pa * matchup['pa_share'], 2)
        matchup['expected_runs'] = round(matchup['runs_per_pa'] * matchup['expected_pa'], 3)
        matchup['has_arsenal_data'] = len(hvp) > 0
        if matchup.get('used_split'):
            away_splits_used += 1
        result['away_matchups'].append(matchup)
        away_f5_runs += matchup['expected_runs']
    
    # Home team vs Away pitcher
    home_f5_runs = 0
    for i, hitter in enumerate(home_lineup[:9]):
        if not hitter: continue
        hvp = get_hitter_vs_pitch(hitter.get('player_id', ''))
        matchup = calculate_matchup_detailed(
            away_pitcher, hitter, park_factor, weights, 
            away_arsenal, hvp, away_p_hand, away_catcher, away_defense
        )
        matchup['lineup_position'] = i + 1
        matchup['pa_share'] = pa_weights[i] if i < len(pa_weights) else 0.09
        matchup['expected_pa'] = round(f5_pa * matchup['pa_share'], 2)
        matchup['expected_runs'] = round(matchup['runs_per_pa'] * matchup['expected_pa'], 3)
        matchup['has_arsenal_data'] = len(hvp) > 0
        if matchup.get('used_split'):
            home_splits_used += 1
        result['home_matchups'].append(matchup)
        home_f5_runs += matchup['expected_runs']
    
    # Bullpen calculations (corrected formula)
    home_bp_ip = max(0, 9 - home_p_ip)
    away_bp_ip = max(0, 9 - away_p_ip)
    bp_runs_per_ip = LEAGUE_AVG['runs_per_game'] / 9 * 1.05
    
    # Scale F5 runs to full game based on starter innings
    away_runs_per_ip = away_f5_runs / 5.0 if away_f5_runs > 0 else 0.5
    home_runs_per_ip = home_f5_runs / 5.0 if home_f5_runs > 0 else 0.5
    
    away_vs_starter = away_runs_per_ip * home_p_ip
    away_vs_bp = bp_runs_per_ip * home_bp_ip * park_factor
    away_full = away_vs_starter + away_vs_bp
    
    home_vs_starter = home_runs_per_ip * away_p_ip
    home_vs_bp = bp_runs_per_ip * away_bp_ip * park_factor
    home_full = home_vs_starter + home_vs_bp
    
    result['projections'] = {
        'f5': {
            'home': round(home_f5_runs, 2), 
            'away': round(away_f5_runs, 2), 
            'total': round(home_f5_runs + away_f5_runs, 2)
        },
        'full': {
            'home': round(home_full, 2), 
            'away': round(away_full, 2), 
            'total': round(home_full + away_full, 2)
        },
        'bullpen': {
            'home_bp_innings': round(home_bp_ip, 1), 
            'away_bp_innings': round(away_bp_ip, 1),
            'away_vs_starter': round(away_vs_starter, 2),
            'away_vs_bp': round(away_vs_bp, 2),
            'home_vs_starter': round(home_vs_starter, 2),
            'home_vs_bp': round(home_vs_bp, 2)
        }
    }
    
    # Data quality indicators
    result['data_quality'] = {
        'away_splits_used': away_splits_used,
        'home_splits_used': home_splits_used,
        'home_pitcher_arsenal': len(home_arsenal),
        'away_pitcher_arsenal': len(away_arsenal)
    }
    
    return result

# =============================================================================
# INITIALIZE
# =============================================================================

print("Initializing MLB Prediction Model v3.0...")
init_db()
import_csvs()

# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position = 'P'")
    pitcher_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position != 'P'")
    hitter_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM pitch_arsenal")
    arsenal_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM hitter_vs_pitch")
    hitter_vs_pitch_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM predictions")
    prediction_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    divisions = {}
    for t in teams:
        key = f"{t['league']} {t['division']}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(t)
    cursor.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 5")
    recent_predictions = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT weight_name, weight_value FROM model_weights")
    weights = {row['weight_name']: row['weight_value'] for row in cursor.fetchall()}
    conn.close()
    return render_template('index.html', pitcher_count=pitcher_count, hitter_count=hitter_count,
        arsenal_count=arsenal_count, hitter_vs_pitch_count=hitter_vs_pitch_count,
        prediction_count=prediction_count, teams=teams, divisions=divisions,
        recent_predictions=recent_predictions, weights=weights)

@app.route('/teams')
def teams_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    divisions = {}
    for t in teams:
        key = f"{t['league']} {t['division']}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(t)
    return render_template('teams.html', teams=teams, divisions=divisions)

@app.route('/team/<team_id>')
def team_detail(team_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,))
    team = cursor.fetchone()
    if not team:
        return "Team not found", 404
    team = dict(team)
    cursor.execute("""SELECT p.*, ps.* FROM players p LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND p.position = 'P' ORDER BY ps.war DESC NULLS LAST""", (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    cursor.execute("""SELECT p.*, hs.* FROM players p LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND p.position != 'P' ORDER BY hs.wrc_plus DESC NULLS LAST""", (team_id,))
    hitters = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('team.html', team=team, pitchers=pitchers, hitters=hitters)

@app.route('/player/<player_id>')
def player_detail(player_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
    player = cursor.fetchone()
    if not player:
        return "Player not found", 404
    player = dict(player)
    if player['position'] == 'P':
        cursor.execute("SELECT * FROM pitcher_stats WHERE player_id = ?", (player_id,))
        stats = cursor.fetchone()
        if stats:
            player.update(dict(stats))
        cursor.execute("SELECT * FROM pitch_arsenal WHERE player_id = ? ORDER BY usage_pct DESC", (player_id,))
        player['arsenal'] = [dict(r) for r in cursor.fetchall()]
        player_type = 'pitcher'
    else:
        cursor.execute("SELECT * FROM hitter_stats WHERE player_id = ?", (player_id,))
        stats = cursor.fetchone()
        if stats:
            player.update(dict(stats))
        cursor.execute("SELECT * FROM hitter_vs_pitch WHERE player_id = ? ORDER BY pa DESC", (player_id,))
        player['vs_pitch'] = [dict(r) for r in cursor.fetchall()]
        player_type = 'hitter'
    cursor.execute("SELECT * FROM teams WHERE team_id = ?", (player.get('team_id'),))
    team = cursor.fetchone()
    player['team'] = dict(team) if team else None
    conn.close()
    return render_template('player.html', player=player, player_type=player_type)

@app.route('/matchup')
def matchup():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY name")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('matchup.html', teams=teams)

@app.route('/results')
def results():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 100")
    predictions = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN actual_home IS NOT NULL THEN 1 ELSE 0 END) as with_results FROM predictions")
    stats = cursor.fetchone()
    conn.close()
    return render_template('results.html', predictions=predictions, stats=dict(stats) if stats else {})

@app.route('/roster-manager')
def roster_manager():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY name")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('roster_manager.html', teams=teams)

# =============================================================================
# API ROUTES
# =============================================================================

@app.route('/api/team/<team_id>/roster')
def api_roster(team_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""SELECT p.*, ps.era, ps.xfip, ps.k9, ps.bb9, ps.war, ps.xwoba_against, 
        ps.whiff_rate, ps.innings_pitched, ps.games_started, ps.avg_innings_per_start
        FROM players p LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND p.position = 'P' ORDER BY ps.war DESC NULLS LAST""", (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    cursor.execute("""SELECT p.*, hs.woba, hs.xwoba, hs.wrc_plus, hs.ops, hs.war, hs.k_rate, 
        hs.bb_rate, hs.barrel_rate, hs.avg, hs.hr, hs.pa
        FROM players p LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND p.position != 'P' ORDER BY hs.wrc_plus DESC NULLS LAST""", (team_id,))
    hitters = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT park_factor FROM teams WHERE team_id = ?", (team_id,))
    team = cursor.fetchone()
    conn.close()
    return jsonify({'pitchers': pitchers, 'hitters': hitters, 'park_factor': team['park_factor'] if team else 1.0})

@app.route('/api/project', methods=['POST'])
def api_project():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT p.*, ps.* FROM players p LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id WHERE p.player_id = ?", (data.get('home_pitcher_id'),))
    home_p = cursor.fetchone()
    home_pitcher = dict(home_p) if home_p else {}
    cursor.execute("SELECT p.*, ps.* FROM players p LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id WHERE p.player_id = ?", (data.get('away_pitcher_id'),))
    away_p = cursor.fetchone()
    away_pitcher = dict(away_p) if away_p else {}
    home_lineup = []
    for pid in data.get('home_lineup', []):
        cursor.execute("SELECT p.*, hs.* FROM players p LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id WHERE p.player_id = ?", (pid,))
        h = cursor.fetchone()
        if h:
            home_lineup.append(dict(h))
    away_lineup = []
    for pid in data.get('away_lineup', []):
        cursor.execute("SELECT p.*, hs.* FROM players p LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id WHERE p.player_id = ?", (pid,))
        h = cursor.fetchone()
        if h:
            away_lineup.append(dict(h))
    conn.close()
    park_factor = data.get('park_factor', 1.0)
    result = project_game(home_pitcher, away_pitcher, home_lineup, away_lineup, park_factor)
    return jsonify(result)

@app.route('/api/save-prediction', methods=['POST'])
def api_save_prediction():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO predictions (game_date, home_team, away_team, home_pitcher, away_pitcher, 
        home_pitcher_id, away_pitcher_id, f5_home, f5_away, f5_total, full_home, full_away, full_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data.get('game_date'), data.get('home_team'), data.get('away_team'), data.get('home_pitcher'),
         data.get('away_pitcher'), data.get('home_pitcher_id'), data.get('away_pitcher_id'),
         data.get('f5_home'), data.get('f5_away'), data.get('f5_total'),
         data.get('full_home'), data.get('full_away'), data.get('full_total')))
    conn.commit()
    prediction_id = cursor.lastrowid
    conn.close()
    return jsonify({'success': True, 'id': prediction_id})

@app.route('/api/prediction/<int:pred_id>/result', methods=['POST'])
def api_update_result(pred_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE predictions SET actual_home = ?, actual_away = ? WHERE id = ?",
        (data.get('actual_home'), data.get('actual_away'), pred_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/player/<player_id>/move', methods=['POST'])
def api_move_player(player_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET team_id = ? WHERE player_id = ?", (data.get('team_id'), player_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/search/players')
def api_search_players():
    q = request.args.get('q', '').lower()
    player_type = request.args.get('type', 'all')
    conn = get_db()
    cursor = conn.cursor()
    if player_type == 'pitcher':
        cursor.execute("""SELECT p.*, ps.era, ps.xfip, ps.war FROM players p
            LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
            WHERE p.position = 'P' AND LOWER(p.name) LIKE ? ORDER BY ps.war DESC NULLS LAST LIMIT 20""", (f'%{q}%',))
    elif player_type == 'hitter':
        cursor.execute("""SELECT p.*, hs.woba, hs.wrc_plus, hs.war FROM players p
            LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
            WHERE p.position != 'P' AND LOWER(p.name) LIKE ? ORDER BY hs.war DESC NULLS LAST LIMIT 20""", (f'%{q}%',))
    else:
        cursor.execute("SELECT * FROM players WHERE LOWER(name) LIKE ? ORDER BY name LIMIT 20", (f'%{q}%',))
    players = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(players)

@app.route('/api/weights', methods=['GET', 'POST'])
def api_weights():
    conn = get_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        data = request.json
        for name, value in data.items():
            cursor.execute("UPDATE model_weights SET weight_value = ?, updated_at = CURRENT_TIMESTAMP WHERE weight_name = ?", (value, name))
        conn.commit()
    cursor.execute("SELECT weight_name, weight_value FROM model_weights")
    weights = {row['weight_name']: row['weight_value'] for row in cursor.fetchall()}
    conn.close()
    return jsonify(weights)

@app.route('/admin/import-csvs')
def admin_import():
    try:
        result = import_csvs()
        return jsonify({'success': True, 'counts': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset-db')
def admin_reset():
    try:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()
        result = import_csvs()
        return jsonify({'success': True, 'counts': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# RUN
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
