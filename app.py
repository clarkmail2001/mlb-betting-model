"""
MLB Prediction Model - Clean Rebuild
Transparent projections with proper CSV imports
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
# DATABASE SETUP
# =============================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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
            name TEXT NOT NULL,
            team_id TEXT,
            position TEXT,
            bats TEXT DEFAULT 'R',
            throws TEXT DEFAULT 'R',
            mlbam_id TEXT
        )
    """)
    
    # Pitcher stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pitcher_stats (
            player_id TEXT PRIMARY KEY,
            games INTEGER,
            games_started INTEGER,
            innings_pitched REAL,
            era REAL,
            xera REAL,
            fip REAL,
            xfip REAL,
            whip REAL,
            k9 REAL,
            bb9 REAL,
            hr9 REAL,
            k_rate REAL,
            bb_rate REAL,
            babip REAL,
            lob_pct REAL,
            gb_pct REAL,
            hr_fb REAL,
            fb_velo REAL,
            war REAL,
            xwoba_against REAL,
            barrel_rate_against REAL,
            hard_hit_against REAL,
            whiff_rate REAL,
            avg_innings_per_start REAL
        )
    """)
    
    # Hitter stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hitter_stats (
            player_id TEXT PRIMARY KEY,
            pa INTEGER,
            ab INTEGER,
            hits INTEGER,
            hr INTEGER,
            runs INTEGER,
            rbi INTEGER,
            bb INTEGER,
            k INTEGER,
            avg REAL,
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
            barrel_rate REAL,
            hard_hit_rate REAL,
            avg_exit_velo REAL,
            war REAL
        )
    """)
    
    # Pitch arsenal
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pitch_arsenal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            pitch_type TEXT,
            pitch_name TEXT,
            usage_pct REAL,
            whiff_rate REAL,
            put_away_rate REAL,
            ba_against REAL,
            slg_against REAL,
            woba_against REAL,
            xwoba_against REAL,
            hard_hit_rate REAL
        )
    """)
    
    # Predictions history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_pitcher TEXT,
            away_pitcher TEXT,
            home_pitcher_id TEXT,
            away_pitcher_id TEXT,
            f5_home REAL,
            f5_away REAL,
            f5_total REAL,
            full_home REAL,
            full_away REAL,
            full_total REAL,
            actual_home INTEGER,
            actual_away INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Results tracking for model learning
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weight_name TEXT UNIQUE,
            weight_value REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert default weights
    default_weights = [
        ('pitcher_quality_factor', 0.015),
        ('platoon_advantage', 0.010),
        ('platoon_disadvantage', -0.015),
        ('high_k_interaction', -0.012),
        ('low_k_interaction', 0.010),
        ('park_factor_multiplier', 0.020),
        ('woba_to_runs', 1.15),
        ('woba_baseline', 0.180),
    ]
    for name, value in default_weights:
        cursor.execute("INSERT OR IGNORE INTO model_weights (weight_name, weight_value) VALUES (?, ?)", (name, value))
    
    # Insert all 30 teams with park factors
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

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def safe_float(val, default=None):
    """Safely convert value to float, handling various null formats."""
    if val is None or val == '' or val == '-' or val == 'NA' or val == 'NULL' or val == 'N/A':
        return default
    try:
        # Remove % sign if present
        cleaned = str(val).replace('%', '').replace(',', '').strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    """Safely convert value to integer."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def make_player_id(name):
    """Create consistent player ID from name."""
    if not name:
        return None
    return name.lower().replace(' ', '_').replace('.', '').replace("'", '').replace('-', '_').replace(',', '').replace('í', 'i').replace('é', 'e').replace('á', 'a').replace('ñ', 'n').replace('ó', 'o').replace('ú', 'u')

def format_stat(val, decimals=3, mult=1, default='-'):
    """Format a stat for display."""
    if val is None:
        return default
    try:
        return f"{float(val) * mult:.{decimals}f}"
    except:
        return default

# =============================================================================
# CSV IMPORT FUNCTIONS
# =============================================================================

def import_csvs():
    """Import all CSV files on startup."""
    conn = get_db()
    cursor = conn.cursor()
    
    print("=" * 60)
    print("IMPORTING CSV DATA")
    print("=" * 60)
    
    # Track counts
    pitcher_count = 0
    hitter_count = 0
    arsenal_count = 0
    
    # 1. Import FanGraphs Hitters
    if os.path.exists('fg_hitters.csv'):
        print("\n[1/6] Loading fg_hitters.csv...")
        with open('fg_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name:
                    continue
                
                player_id = make_player_id(name)
                team = TEAM_MAP.get(row.get('Team', ''), 'FA')
                
                # Insert player
                cursor.execute("""
                    INSERT OR REPLACE INTO players (player_id, name, team_id, position, bats)
                    VALUES (?, ?, ?, 'OF', 'R')
                """, (player_id, name, team))
                
                # Insert hitter stats
                cursor.execute("""
                    INSERT OR REPLACE INTO hitter_stats 
                    (player_id, pa, ab, hits, hr, runs, rbi, bb, k, avg, obp, slg, ops, woba, wrc_plus, k_rate, bb_rate, iso, babip, war)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    safe_int(row.get('PA')),
                    safe_int(row.get('AB')),
                    safe_int(row.get('H')),
                    safe_int(row.get('HR')),
                    safe_int(row.get('R')),
                    safe_int(row.get('RBI')),
                    safe_int(row.get('BB')),
                    safe_int(row.get('K')),
                    safe_float(row.get('AVG')),
                    safe_float(row.get('OBP')),
                    safe_float(row.get('SLG')),
                    safe_float(row.get('OPS')),
                    safe_float(row.get('wOBA')),
                    safe_float(row.get('wRC+')),
                    safe_float(row.get('K%')),
                    safe_float(row.get('BB%')),
                    safe_float(row.get('ISO')),
                    safe_float(row.get('BABIP')),
                    safe_float(row.get('WAR'))
                ))
                count += 1
            print(f"      Loaded {count} hitters from FanGraphs")
            hitter_count = count
    else:
        print("[1/6] fg_hitters.csv not found - SKIPPED")
    
    # 2. Import Savant Hitters (xwOBA, barrel rate)
    if os.path.exists('savant_hitters.csv'):
        print("\n[2/6] Loading savant_hitters.csv...")
        with open('savant_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                first = row.get('first_name', '')
                last = row.get('last_name', '')
                name = f"{first} {last}".strip()
                if not name or name == ' ':
                    continue
                
                player_id = make_player_id(name)
                
                cursor.execute("""
                    UPDATE hitter_stats SET
                        xwoba = COALESCE(?, xwoba),
                        barrel_rate = COALESCE(?, barrel_rate),
                        hard_hit_rate = COALESCE(?, hard_hit_rate),
                        avg_exit_velo = COALESCE(?, avg_exit_velo)
                    WHERE player_id = ?
                """, (
                    safe_float(row.get('xwoba')),
                    safe_float(row.get('barrel_batted_rate')),
                    safe_float(row.get('hard_hit_percent')),
                    safe_float(row.get('avg_best_speed')),
                    player_id
                ))
                if cursor.rowcount > 0:
                    count += 1
            print(f"      Updated {count} hitters with Savant data")
    else:
        print("[2/6] savant_hitters.csv not found - SKIPPED")
    
    # 3. Import Baseball Prospectus (DRC+)
    if os.path.exists('bp_hitters.csv'):
        print("\n[3/6] Loading bp_hitters.csv...")
        with open('bp_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', '')
                if not name:
                    continue
                
                player_id = make_player_id(name)
                drc = safe_float(row.get('DRC+'))
                
                cursor.execute("""
                    UPDATE hitter_stats SET drc_plus = ? WHERE player_id = ?
                """, (drc, player_id))
                if cursor.rowcount > 0:
                    count += 1
            print(f"      Updated {count} hitters with DRC+")
    else:
        print("[3/6] bp_hitters.csv not found - SKIPPED")
    
    # 4. Import FanGraphs Pitchers
    if os.path.exists('fg_pitchers.csv'):
        print("\n[4/6] Loading fg_pitchers.csv...")
        with open('fg_pitchers.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name:
                    continue
                
                player_id = make_player_id(name)
                team = TEAM_MAP.get(row.get('Team', ''), 'FA')
                mlbam = row.get('MLBAMID', '')
                
                # Insert player as pitcher
                cursor.execute("""
                    INSERT OR REPLACE INTO players (player_id, name, team_id, position, throws, mlbam_id)
                    VALUES (?, ?, ?, 'P', 'R', ?)
                """, (player_id, name, team, mlbam))
                
                # Calculate average innings per start
                ip = safe_float(row.get('IP'), 0)
                gs = safe_int(row.get('GS'), 0)
                avg_ip_start = (ip / gs) if gs > 0 else 5.0
                
                # Insert pitcher stats - direct mapping from CSV columns
                cursor.execute("""
                    INSERT OR REPLACE INTO pitcher_stats 
                    (player_id, games, games_started, innings_pitched, era, xera, fip, xfip, 
                     k9, bb9, hr9, babip, lob_pct, gb_pct, hr_fb, fb_velo, war, avg_innings_per_start)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    safe_int(row.get('G')),
                    safe_int(row.get('GS')),
                    safe_float(row.get('IP')),
                    safe_float(row.get('ERA')),
                    safe_float(row.get('xERA')),
                    safe_float(row.get('FIP')),
                    safe_float(row.get('xFIP')),
                    safe_float(row.get('K/9')),
                    safe_float(row.get('BB/9')),
                    safe_float(row.get('HR/9')),
                    safe_float(row.get('BABIP')),
                    safe_float(row.get('LOB%')),
                    safe_float(row.get('GB%')),
                    safe_float(row.get('HR/FB')),
                    safe_float(row.get('vFA (pi)')),
                    safe_float(row.get('WAR')),
                    avg_ip_start
                ))
                count += 1
            print(f"      Loaded {count} pitchers from FanGraphs")
            pitcher_count = count
    else:
        print("[4/6] fg_pitchers.csv not found - SKIPPED")
    
    # 5. Import FanGraphs Pitch Mix
    if os.path.exists('fg_pitch_mix.csv'):
        print("\n[5/6] Loading fg_pitch_mix.csv...")
        with open('fg_pitch_mix.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name:
                    continue
                
                player_id = make_player_id(name)
                
                # Update pitcher with pitch mix percentages
                cursor.execute("""
                    UPDATE pitcher_stats SET
                        fb_velo = COALESCE(?, fb_velo)
                    WHERE player_id = ?
                """, (safe_float(row.get('FBv')), player_id))
                count += 1
            print(f"      Updated {count} pitchers with pitch mix")
    else:
        print("[5/6] fg_pitch_mix.csv not found - SKIPPED")
    
    # 6. Import Savant Pitchers (pitch arsenal with results)
    if os.path.exists('savant_pitchers.csv'):
        print("\n[6/6] Loading savant_pitchers.csv...")
        # Clear existing arsenal data to avoid duplicates
        cursor.execute("DELETE FROM pitch_arsenal")
        
        with open('savant_pitchers.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            player_xwoba = {}  # Track for aggregation
            
            for row in reader:
                first = row.get('first_name', '')
                last = row.get('last_name', '')
                name = f"{first} {last}".strip()
                if not name or name == ' ':
                    continue
                
                player_id = make_player_id(name)
                
                # Insert pitch arsenal data
                cursor.execute("""
                    INSERT INTO pitch_arsenal 
                    (player_id, pitch_type, pitch_name, usage_pct, whiff_rate, put_away_rate, 
                     ba_against, slg_against, woba_against, xwoba_against, hard_hit_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    safe_float(row.get('est_woba')),
                    safe_float(row.get('hard_hit_percent'))
                ))
                
                # Track for weighted average
                usage = safe_float(row.get('pitch_usage'), 0)
                xwoba = safe_float(row.get('est_woba'))
                whiff = safe_float(row.get('whiff_percent'))
                hh = safe_float(row.get('hard_hit_percent'))
                
                if player_id not in player_xwoba:
                    player_xwoba[player_id] = {'total_usage': 0, 'weighted_xwoba': 0, 'weighted_whiff': 0, 'weighted_hh': 0}
                
                if usage and xwoba:
                    player_xwoba[player_id]['total_usage'] += usage
                    player_xwoba[player_id]['weighted_xwoba'] += usage * xwoba
                    if whiff:
                        player_xwoba[player_id]['weighted_whiff'] += usage * whiff
                    if hh:
                        player_xwoba[player_id]['weighted_hh'] += usage * hh
                
                count += 1
            
            # Update pitcher aggregate stats
            for pid, data in player_xwoba.items():
                if data['total_usage'] > 0:
                    avg_xwoba = data['weighted_xwoba'] / data['total_usage']
                    avg_whiff = data['weighted_whiff'] / data['total_usage'] if data['weighted_whiff'] else None
                    avg_hh = data['weighted_hh'] / data['total_usage'] if data['weighted_hh'] else None
                    
                    cursor.execute("""
                        UPDATE pitcher_stats SET
                            xwoba_against = ?,
                            whiff_rate = ?,
                            hard_hit_against = ?
                        WHERE player_id = ?
                    """, (avg_xwoba, avg_whiff, avg_hh, pid))
            
            print(f"      Loaded {count} pitch arsenal rows")
            arsenal_count = count
    else:
        print("[6/6] savant_pitchers.csv not found - SKIPPED")
    
    conn.commit()
    
    # Final counts
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position = 'P'")
    final_pitchers = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position != 'P'")
    final_hitters = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM pitch_arsenal")
    final_arsenal = cursor.fetchone()['cnt']
    
    print("\n" + "=" * 60)
    print(f"IMPORT COMPLETE")
    print(f"  Pitchers: {final_pitchers}")
    print(f"  Hitters:  {final_hitters}")
    print(f"  Arsenal:  {final_arsenal}")
    print("=" * 60 + "\n")
    
    conn.close()
    return {'pitchers': final_pitchers, 'hitters': final_hitters, 'arsenal': final_arsenal}

# =============================================================================
# LEAGUE AVERAGES
# =============================================================================

LEAGUE_AVG = {
    'woba': 0.315,
    'xwoba': 0.315,
    'k_rate': 22.5,
    'bb_rate': 8.2,
    'era': 4.20,
    'xfip': 4.10,
    'runs_per_inning': 0.50,
    'pa_per_inning': 4.3,
}

# =============================================================================
# PROJECTION ENGINE
# =============================================================================

def get_model_weights():
    """Get current model weights from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT weight_name, weight_value FROM model_weights")
    weights = {row['weight_name']: row['weight_value'] for row in cursor.fetchall()}
    conn.close()
    return weights

def calculate_matchup_detailed(pitcher, hitter, park_factor=1.0, weights=None):
    """
    Calculate single batter vs pitcher matchup with full transparency.
    Returns detailed breakdown of every calculation step.
    """
    if weights is None:
        weights = get_model_weights()
    
    breakdown = {
        'hitter_name': hitter.get('name', 'Unknown'),
        'steps': []
    }
    
    # Step 1: Baseline wOBA
    h_woba = hitter.get('woba') or LEAGUE_AVG['woba']
    h_xwoba = hitter.get('xwoba') or h_woba
    baseline = (h_woba + h_xwoba) / 2
    
    breakdown['steps'].append({
        'name': 'Baseline wOBA',
        'formula': f"(wOBA + xwOBA) / 2",
        'values': f"({format_stat(h_woba)} + {format_stat(h_xwoba)}) / 2",
        'result': round(baseline, 3)
    })
    
    # Step 2: Pitcher Quality Adjustment
    p_xfip = pitcher.get('xfip') or pitcher.get('era') or LEAGUE_AVG['xfip']
    pitcher_factor = weights.get('pitcher_quality_factor', 0.015)
    pitcher_adj = (LEAGUE_AVG['xfip'] - p_xfip) * pitcher_factor
    
    breakdown['steps'].append({
        'name': 'Pitcher Quality',
        'formula': f"(League xFIP - Pitcher xFIP) × {pitcher_factor}",
        'values': f"({LEAGUE_AVG['xfip']:.2f} - {p_xfip:.2f}) × {pitcher_factor}",
        'result': round(pitcher_adj, 4)
    })
    
    # Step 3: K-Rate Interaction
    p_k9 = pitcher.get('k9') or 9.0
    p_whiff = pitcher.get('whiff_rate') or 25
    h_k_rate = hitter.get('k_rate') or LEAGUE_AVG['k_rate']
    
    high_k_adj = weights.get('high_k_interaction', -0.012)
    low_k_adj = weights.get('low_k_interaction', 0.010)
    
    if p_k9 > 10.0 and h_k_rate > 25:
        k_adj = high_k_adj
        k_reason = f"High-K matchup (P K/9: {p_k9:.1f}, H K%: {h_k_rate:.1f}%)"
    elif p_k9 < 7.0 and h_k_rate < 18:
        k_adj = low_k_adj
        k_reason = f"Low-K matchup (P K/9: {p_k9:.1f}, H K%: {h_k_rate:.1f}%)"
    else:
        k_adj = 0
        k_reason = f"Neutral K matchup (P K/9: {p_k9:.1f}, H K%: {h_k_rate:.1f}%)"
    
    breakdown['steps'].append({
        'name': 'K-Rate Interaction',
        'formula': k_reason,
        'values': '',
        'result': round(k_adj, 4)
    })
    
    # Step 4: Park Factor
    park_mult = weights.get('park_factor_multiplier', 0.020)
    park_adj = (park_factor - 1.0) * park_mult
    
    breakdown['steps'].append({
        'name': 'Park Factor',
        'formula': f"(Park Factor - 1.0) × {park_mult}",
        'values': f"({park_factor:.2f} - 1.0) × {park_mult}",
        'result': round(park_adj, 4)
    })
    
    # Step 5: Final Projected wOBA
    total_adj = pitcher_adj + k_adj + park_adj
    proj_woba = baseline + total_adj
    proj_woba = max(0.220, min(0.450, proj_woba))  # Clamp to realistic range
    
    breakdown['steps'].append({
        'name': 'Total Adjustment',
        'formula': 'Pitcher + K-Rate + Park',
        'values': f"{pitcher_adj:.4f} + {k_adj:.4f} + {park_adj:.4f}",
        'result': round(total_adj, 4)
    })
    
    breakdown['steps'].append({
        'name': 'Projected wOBA',
        'formula': 'Baseline + Adjustments (clamped 0.220-0.450)',
        'values': f"{baseline:.3f} + {total_adj:.4f}",
        'result': round(proj_woba, 3)
    })
    
    # Step 6: Convert to Runs
    woba_baseline = weights.get('woba_baseline', 0.180)
    woba_to_runs = weights.get('woba_to_runs', 1.15)
    runs_per_pa = (proj_woba - woba_baseline) * woba_to_runs
    runs_per_pa = max(0.05, runs_per_pa)
    
    breakdown['steps'].append({
        'name': 'Runs per PA',
        'formula': f"(Proj wOBA - {woba_baseline}) × {woba_to_runs}",
        'values': f"({proj_woba:.3f} - {woba_baseline}) × {woba_to_runs}",
        'result': round(runs_per_pa, 4)
    })
    
    # Summary
    breakdown['baseline_woba'] = round(baseline, 3)
    breakdown['projected_woba'] = round(proj_woba, 3)
    breakdown['runs_per_pa'] = round(runs_per_pa, 4)
    breakdown['advantage'] = 'hitter' if proj_woba > 0.340 else ('pitcher' if proj_woba < 0.290 else 'neutral')
    
    return breakdown

def estimate_pitcher_innings(pitcher):
    """Estimate how many innings the pitcher will throw based on their data."""
    avg_ip = pitcher.get('avg_innings_per_start')
    if avg_ip and avg_ip > 0:
        return min(7.0, max(4.0, avg_ip))
    
    # Fallback: estimate from total IP and GS
    ip = pitcher.get('innings_pitched', 0)
    gs = pitcher.get('games_started', 0)
    
    if gs and gs > 0:
        return min(7.0, max(4.0, ip / gs))
    
    # Default for unknown pitchers
    return 5.0

def project_game(home_pitcher, away_pitcher, home_lineup, away_lineup, park_factor=1.0):
    """
    Full game projection with transparent calculations.
    """
    weights = get_model_weights()
    
    # PA distribution by lineup position (based on historical data)
    pa_weights = [0.137, 0.130, 0.123, 0.116, 0.109, 0.103, 0.097, 0.093, 0.092]
    
    # Estimate pitcher innings
    home_p_innings = estimate_pitcher_innings(home_pitcher)
    away_p_innings = estimate_pitcher_innings(away_pitcher)
    
    # Calculate total PA for F5 (5 innings)
    f5_pa = LEAGUE_AVG['pa_per_inning'] * 5
    
    result = {
        'home_pitcher': {
            'name': home_pitcher.get('name', 'Unknown'),
            'estimated_innings': round(home_p_innings, 1),
            'era': home_pitcher.get('era'),
            'xfip': home_pitcher.get('xfip'),
            'k9': home_pitcher.get('k9'),
        },
        'away_pitcher': {
            'name': away_pitcher.get('name', 'Unknown'),
            'estimated_innings': round(away_p_innings, 1),
            'era': away_pitcher.get('era'),
            'xfip': away_pitcher.get('xfip'),
            'k9': away_pitcher.get('k9'),
        },
        'park_factor': park_factor,
        'away_matchups': [],
        'home_matchups': [],
    }
    
    # Away team vs Home pitcher (F5)
    away_f5_runs = 0
    for i, hitter in enumerate(away_lineup[:9]):
        if not hitter:
            continue
        
        matchup = calculate_matchup_detailed(home_pitcher, hitter, park_factor, weights)
        matchup['lineup_position'] = i + 1
        matchup['pa_share'] = pa_weights[i] if i < len(pa_weights) else 0.09
        matchup['expected_pa'] = round(f5_pa * matchup['pa_share'], 2)
        matchup['expected_runs'] = round(matchup['runs_per_pa'] * matchup['expected_pa'], 3)
        
        result['away_matchups'].append(matchup)
        away_f5_runs += matchup['expected_runs']
    
    # Home team vs Away pitcher (F5)
    home_f5_runs = 0
    for i, hitter in enumerate(home_lineup[:9]):
        if not hitter:
            continue
        
        matchup = calculate_matchup_detailed(away_pitcher, hitter, park_factor, weights)
        matchup['lineup_position'] = i + 1
        matchup['pa_share'] = pa_weights[i] if i < len(pa_weights) else 0.09
        matchup['expected_pa'] = round(f5_pa * matchup['pa_share'], 2)
        matchup['expected_runs'] = round(matchup['runs_per_pa'] * matchup['expected_pa'], 3)
        
        result['home_matchups'].append(matchup)
        home_f5_runs += matchup['expected_runs']
    
    # Bullpen innings (after starter)
    home_bp_innings = max(0, 9 - home_p_innings)
    away_bp_innings = max(0, 9 - away_p_innings)
    
    # Bullpen runs (league average + slight regression)
    bp_runs_per_inning = LEAGUE_AVG['runs_per_inning'] * 1.05
    
    home_bp_runs = bp_runs_per_inning * home_bp_innings * park_factor
    away_bp_runs = bp_runs_per_inning * away_bp_innings
    
    # Full game projections
    # Scale F5 runs to starter innings, then add bullpen
    home_starter_runs = home_f5_runs * (away_p_innings / 5.0)
    away_starter_runs = away_f5_runs * (home_p_innings / 5.0)
    
    home_full = home_starter_runs + home_bp_runs
    away_full = away_starter_runs + away_bp_runs
    
    result['projections'] = {
        'f5': {
            'home': round(home_f5_runs, 2),
            'away': round(away_f5_runs, 2),
            'total': round(home_f5_runs + away_f5_runs, 2),
        },
        'full': {
            'home': round(home_full, 2),
            'away': round(away_full, 2),
            'total': round(home_full + away_full, 2),
        },
        'bullpen': {
            'home_innings': round(home_bp_innings, 1),
            'away_innings': round(away_bp_innings, 1),
            'home_runs': round(home_bp_runs, 2),
            'away_runs': round(away_bp_runs, 2),
        }
    }
    
    return result

# =============================================================================
# INITIALIZE APP
# =============================================================================

print("Initializing MLB Prediction Model...")
init_db()
import_csvs()

# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get counts
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position = 'P'")
    pitcher_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position != 'P'")
    hitter_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT COUNT(*) as cnt FROM pitch_arsenal")
    arsenal_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT COUNT(*) as cnt FROM predictions")
    prediction_count = cursor.fetchone()['cnt']
    
    # Get teams organized by division
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    
    divisions = {}
    for t in teams:
        key = f"{t['league']} {t['division']}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(t)
    
    # Get recent predictions
    cursor.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 5")
    recent_predictions = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return render_template('index.html',
        pitcher_count=pitcher_count,
        hitter_count=hitter_count,
        arsenal_count=arsenal_count,
        prediction_count=prediction_count,
        teams=teams,
        divisions=divisions,
        recent_predictions=recent_predictions
    )

@app.route('/teams')
def teams_list():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    # Organize by division
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
    
    # Get pitchers
    cursor.execute("""
        SELECT p.*, ps.*
        FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND p.position = 'P'
        ORDER BY ps.war DESC NULLS LAST
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    # Get hitters
    cursor.execute("""
        SELECT p.*, hs.*
        FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND p.position != 'P'
        ORDER BY hs.wrc_plus DESC NULLS LAST
    """, (team_id,))
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
    
    # Calculate accuracy stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN actual_home IS NOT NULL THEN 1 ELSE 0 END) as with_results
        FROM predictions
    """)
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
    
    # Get pitchers
    cursor.execute("""
        SELECT p.*, ps.era, ps.xfip, ps.k9, ps.bb9, ps.war, ps.xwoba_against, 
               ps.whiff_rate, ps.innings_pitched, ps.games_started, ps.avg_innings_per_start
        FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND p.position = 'P'
        ORDER BY ps.war DESC NULLS LAST
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    # Get hitters
    cursor.execute("""
        SELECT p.*, hs.woba, hs.xwoba, hs.wrc_plus, hs.ops, hs.war, hs.k_rate, 
               hs.bb_rate, hs.barrel_rate, hs.avg, hs.hr, hs.pa
        FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND p.position != 'P'
        ORDER BY hs.wrc_plus DESC NULLS LAST
    """, (team_id,))
    hitters = [dict(r) for r in cursor.fetchall()]
    
    # Get park factor
    cursor.execute("SELECT park_factor FROM teams WHERE team_id = ?", (team_id,))
    team = cursor.fetchone()
    
    conn.close()
    
    return jsonify({
        'pitchers': pitchers,
        'hitters': hitters,
        'park_factor': team['park_factor'] if team else 1.0
    })

@app.route('/api/project', methods=['POST'])
def api_project():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Get home pitcher
    cursor.execute("""
        SELECT p.*, ps.* FROM players p 
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id 
        WHERE p.player_id = ?
    """, (data.get('home_pitcher_id'),))
    home_p = cursor.fetchone()
    home_pitcher = dict(home_p) if home_p else {}
    
    # Get away pitcher
    cursor.execute("""
        SELECT p.*, ps.* FROM players p 
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id 
        WHERE p.player_id = ?
    """, (data.get('away_pitcher_id'),))
    away_p = cursor.fetchone()
    away_pitcher = dict(away_p) if away_p else {}
    
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
    
    park_factor = data.get('park_factor', 1.0)
    result = project_game(home_pitcher, away_pitcher, home_lineup, away_lineup, park_factor)
    
    return jsonify(result)

@app.route('/api/save-prediction', methods=['POST'])
def api_save_prediction():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO predictions 
        (game_date, home_team, away_team, home_pitcher, away_pitcher, 
         home_pitcher_id, away_pitcher_id, f5_home, f5_away, f5_total, 
         full_home, full_away, full_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('game_date'),
        data.get('home_team'),
        data.get('away_team'),
        data.get('home_pitcher'),
        data.get('away_pitcher'),
        data.get('home_pitcher_id'),
        data.get('away_pitcher_id'),
        data.get('f5_home'),
        data.get('f5_away'),
        data.get('f5_total'),
        data.get('full_home'),
        data.get('full_away'),
        data.get('full_total'),
    ))
    
    conn.commit()
    prediction_id = cursor.lastrowid
    conn.close()
    
    return jsonify({'success': True, 'id': prediction_id})

@app.route('/api/prediction/<int:pred_id>/result', methods=['POST'])
def api_update_result(pred_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE predictions 
        SET actual_home = ?, actual_away = ?
        WHERE id = ?
    """, (data.get('actual_home'), data.get('actual_away'), pred_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/player/<player_id>/move', methods=['POST'])
def api_move_player(player_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE players SET team_id = ? WHERE player_id = ?", 
                   (data.get('team_id'), player_id))
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
        cursor.execute("""
            SELECT p.*, ps.era, ps.xfip, ps.war 
            FROM players p
            LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
            WHERE p.position = 'P' AND LOWER(p.name) LIKE ?
            ORDER BY ps.war DESC NULLS LAST
            LIMIT 20
        """, (f'%{q}%',))
    elif player_type == 'hitter':
        cursor.execute("""
            SELECT p.*, hs.woba, hs.wrc_plus, hs.war 
            FROM players p
            LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
            WHERE p.position != 'P' AND LOWER(p.name) LIKE ?
            ORDER BY hs.war DESC NULLS LAST
            LIMIT 20
        """, (f'%{q}%',))
    else:
        cursor.execute("""
            SELECT * FROM players 
            WHERE LOWER(name) LIKE ?
            ORDER BY name
            LIMIT 20
        """, (f'%{q}%',))
    
    players = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return jsonify(players)

@app.route('/admin/import-csvs')
def admin_import():
    """Manually trigger CSV import."""
    try:
        result = import_csvs()
        return jsonify({'success': True, 'counts': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset-db')
def admin_reset():
    """Reset database and reimport."""
    try:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_db()
        result = import_csvs()
        return jsonify({'success': True, 'counts': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# RUN APP
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
