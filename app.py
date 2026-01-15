"""
MLB Prediction Model - With CSV Auto-Import
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import csv
import os

app = Flask(__name__)
app.secret_key = 'mlb_model_2025'

DB_PATH = '/tmp/baseball.db' if os.environ.get('RAILWAY_ENVIRONMENT') else 'baseball.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            team_id TEXT,
            position TEXT,
            bats TEXT DEFAULT 'R',
            throws TEXT DEFAULT 'R'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pitcher_stats (
            player_id TEXT PRIMARY KEY,
            era REAL, whip REAL, k_rate REAL, bb_rate REAL,
            siera REAL, xfip REAL, fip REAL, war REAL,
            fb_pct REAL, sl_pct REAL, cb_pct REAL, ch_pct REAL,
            fb_velo REAL, xwoba_against REAL, barrel_rate_against REAL,
            hard_hit_against REAL, whiff_rate REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hitter_stats (
            player_id TEXT PRIMARY KEY,
            pa INTEGER, avg REAL, obp REAL, slg REAL, ops REAL,
            woba REAL, xwoba REAL, wrc_plus REAL, drc_plus REAL,
            k_rate REAL, bb_rate REAL, iso REAL, babip REAL,
            barrel_rate REAL, hard_hit_rate REAL, avg_exit_velo REAL, war REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pitch_arsenal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT, pitch_type TEXT, pitch_name TEXT,
            usage_pct REAL, whiff_rate REAL, put_away_rate REAL,
            ba_against REAL, slg_against REAL, woba_against REAL,
            xwoba_against REAL, hard_hit_rate REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT, home_team TEXT, away_team TEXT,
            home_pitcher TEXT, away_pitcher TEXT,
            f5_home REAL, f5_away REAL, f5_total REAL,
            full_home REAL, full_away REAL, full_total REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert teams
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

# Team name mapping
TEAM_MAP = {
    'Angels': 'LAA', 'LAA': 'LAA', 'Diamondbacks': 'ARI', 'ARI': 'ARI', 'D-backs': 'ARI',
    'Braves': 'ATL', 'ATL': 'ATL', 'Orioles': 'BAL', 'BAL': 'BAL',
    'Red Sox': 'BOS', 'BOS': 'BOS', 'Cubs': 'CHC', 'CHC': 'CHC',
    'White Sox': 'CWS', 'CWS': 'CWS', 'CHW': 'CWS',
    'Reds': 'CIN', 'CIN': 'CIN', 'Guardians': 'CLE', 'CLE': 'CLE', 'Indians': 'CLE',
    'Rockies': 'COL', 'COL': 'COL', 'Tigers': 'DET', 'DET': 'DET',
    'Astros': 'HOU', 'HOU': 'HOU', 'Royals': 'KC', 'KC': 'KC', 'KCR': 'KC',
    'Dodgers': 'LAD', 'LAD': 'LAD', 'Marlins': 'MIA', 'MIA': 'MIA',
    'Brewers': 'MIL', 'MIL': 'MIL', 'Twins': 'MIN', 'MIN': 'MIN',
    'Mets': 'NYM', 'NYM': 'NYM', 'Yankees': 'NYY', 'NYY': 'NYY',
    'Athletics': 'OAK', 'OAK': 'OAK', "A's": 'OAK',
    'Phillies': 'PHI', 'PHI': 'PHI', 'Pirates': 'PIT', 'PIT': 'PIT',
    'Padres': 'SD', 'SD': 'SD', 'SDP': 'SD',
    'Giants': 'SF', 'SF': 'SF', 'SFG': 'SF',
    'Mariners': 'SEA', 'SEA': 'SEA',
    'Cardinals': 'STL', 'STL': 'STL',
    'Rays': 'TB', 'TB': 'TB', 'TBR': 'TB',
    'Rangers': 'TEX', 'TEX': 'TEX',
    'Blue Jays': 'TOR', 'TOR': 'TOR',
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
    return name.lower().replace(' ', '_').replace('.', '').replace("'", '').replace('-', '').replace(',', '')

def import_csvs():
    """Import all CSV files on startup."""
    conn = get_db()
    cursor = conn.cursor()
    
    print("Importing CSV data...")
    
    # 1. Import FanGraphs Hitters
    if os.path.exists('fg_hitters.csv'):
        print("  Loading fg_hitters.csv...")
        with open('fg_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name:
                    continue
                
                player_id = make_player_id(name)
                team = TEAM_MAP.get(row.get('Team', ''), 'FA')
                
                cursor.execute("""
                    INSERT OR REPLACE INTO players (player_id, name, team_id, position, bats)
                    VALUES (?, ?, ?, 'DH', 'R')
                """, (player_id, name, team))
                
                cursor.execute("""
                    INSERT OR REPLACE INTO hitter_stats
                    (player_id, pa, avg, obp, slg, ops, woba, wrc_plus, k_rate, bb_rate, iso, babip, war)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    safe_int(row.get('PA')),
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
    
    # 2. Import Savant Hitters (xwOBA, barrel rate)
    if os.path.exists('savant_hitters.csv'):
        print("  Loading savant_hitters.csv...")
        with open('savant_hitters.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                if not name or name == ' ':
                    continue
                
                player_id = make_player_id(name)
                
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
    
    # 3. Import Baseball Prospectus (DRC+)
    if os.path.exists('bp_hitters.csv'):
        print("  Loading bp_hitters.csv...")
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


        # 4. Import FanGraphs Pitchers (ERA, WHIP, K%, WAR, SIERA, xFIP)
    if os.path.exists('fg_pitchers.csv'):
        print("  Loading fg_pitchers.csv...")
        with open('fg_pitchers.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', row.get('NameASCII', ''))
                if not name:
                    continue
                
                player_id = make_player_id(name)
                team = TEAM_MAP.get(row.get('Team', ''), 'FA')
                
                # Insert player if not exists
                cursor.execute("""
                    INSERT OR IGNORE INTO players (player_id, name, team_id, position, throws)
                    VALUES (?, ?, ?, 'P', 'R')
                """, (player_id, name, team))
                
                # Calculate derived stats
                ip = safe_float(row.get('IP'), 0)
                k9 = safe_float(row.get('K/9'))
                bb9 = safe_float(row.get('BB/9'))
                
                # Convert K/9 and BB/9 to K% and BB% (approximate)
                k_rate = (k9 / 9.0) * 100 if k9 else None
                bb_rate = (bb9 / 9.0) * 100 if bb9 else None
                
                # Insert/update pitcher stats
        # Insert/update pitcher stats - calculate WHIP from K/9 and BB/9
        # WHIP ≈ (BB/9 + (9 - K/9 + BB/9) * 0.30) / 9 (rough estimate)
        h9_estimate = max(0, 9 - k9 + bb9) if (k9 and bb9) else None
        whip = ((bb9 or 0) + (h9_estimate or 9)) / 9 if h9_estimate is not None else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO pitcher_stats
            (player_id, era, whip, k_rate, bb_rate, fip, xfip, war)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player_id,
            safe_float(row.get('ERA')),
            whip,
            k_rate,
            bb_rate,
            safe_float(row.get('FIP')),
            safe_float(row.get('xFIP')),
            safe_float(row.get('WAR'))
        ))
        
    # 5. Import FanGraphs Pitch Mix (pitchers)
    if os.path.exists('fg_pitch_mix.csv'):
        with open('fg_pitch_mix.csv', 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                                name = row.get('Name', row.get('NameASCII', ''))
                                if not name:
                                            continue
                
                                player_id = make_player_id(name)
                                team = TEAM_MAP.get(row.get('Team', ''), 'FA')
                
                                cursor.execute("""
                                            INSERT OR REPLACE INTO players (player_id, name, team_id, position, throws)
                                                    VALUES (?, ?, ?, 'P', 'R')
                                    """, (player_id, name, team))
                
                cursor.execute("""
                    INSERT OR REPLACE INTO pitcher_stats
                    (player_id, fb_pct, sl_pct, cb_pct, ch_pct, fb_velo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    safe_float(row.get('FB%')),
                    safe_float(row.get('SL%')),
                    safe_float(row.get('CB%')),
                    safe_float(row.get('CH%')),
                    safe_float(row.get('FBv'))
                ))
    
        # 6. Import Savant Pitchers (pitch arsenal with results)
    if os.path.exists('savant_pitchers.csv'):
        print("  Loading savant_pitchers.csv...")
        with open('savant_pitchers.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                if not name or name == ' ':
                    continue
                
                player_id = make_player_id(name)
                team = TEAM_MAP.get(row.get('team_name_alt', ''), 'FA')
                
                # Insert player if not exists
                cursor.execute("""
                    INSERT OR IGNORE INTO players (player_id, name, team_id, position, throws)
                    VALUES (?, ?, ?, 'P', 'R')
                """, (player_id, name, team))
                
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
                
                # Update pitcher aggregate stats
                cursor.execute("""
                    UPDATE pitcher_stats SET
                        xwoba_against = COALESCE(xwoba_against, ?),
                        whiff_rate = COALESCE(whiff_rate, ?),
                        hard_hit_against = COALESCE(hard_hit_against, ?)
                    WHERE player_id = ?
                """, (
                    safe_float(row.get('est_woba')),
                    safe_float(row.get('whiff_percent')),
                    safe_float(row.get('hard_hit_percent')),
                    player_id
                ))
    
    conn.commit()
    
    # Count results
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position = 'P'")
    pitcher_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position != 'P'")
    hitter_count = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM pitch_arsenal")
    arsenal_count = cursor.fetchone()['cnt']
    
    print(f"  Imported: {pitcher_count} pitchers, {hitter_count} hitters, {arsenal_count} pitch arsenal rows")
    
    conn.close()

# League averages for projections
LEAGUE_AVG = {
    'woba': 0.315,
    'xwoba': 0.315,
    'k_rate': 22.5,
    'bb_rate': 8.2,
    'era': 4.20,
    'runs_per_inning': 0.50,
    'pa_per_inning': 4.3,
}

def calculate_matchup(pitcher, hitter, park_factor=1.0):
    """Calculate single batter vs pitcher matchup."""
    # Get hitter baseline
    h_woba = hitter.get('woba') or hitter.get('xwoba') or LEAGUE_AVG['woba']
    h_xwoba = hitter.get('xwoba') or h_woba
    baseline = (h_woba + h_xwoba) / 2
    
    # Pitcher adjustment
    p_xwoba = pitcher.get('xwoba_against') or LEAGUE_AVG['xwoba']
    pitcher_adj = (LEAGUE_AVG['xwoba'] - p_xwoba) * 0.5
    
    # K-rate interaction
    p_whiff = pitcher.get('whiff_rate') or 25
    h_k_rate = hitter.get('k_rate') or LEAGUE_AVG['k_rate']
    k_adj = -0.008 if (p_whiff > 28 and h_k_rate > 25) else 0
    
    # Park factor
    park_adj = (park_factor - 1.0) * 0.015
    
    # Final projection
    proj_woba = baseline + pitcher_adj + k_adj + park_adj
    proj_woba = max(0.200, min(0.450, proj_woba))
    
    # Convert to runs
    runs_per_pa = (proj_woba - 0.180) * 1.1
    runs_per_pa = max(0.05, runs_per_pa)
    
    return {
        'name': hitter.get('name', 'Unknown'),
        'baseline_woba': round(baseline, 3),
        'projected_woba': round(proj_woba, 3),
        'runs_per_pa': round(runs_per_pa, 4),
        'advantage': 'hitter' if proj_woba > 0.330 else ('pitcher' if proj_woba < 0.300 else 'neutral')
    }

def project_game(home_pitcher, away_pitcher, home_lineup, away_lineup, park_factor=1.0):
    """Full game projection."""
    pa_weights = [0.137, 0.130, 0.123, 0.116, 0.109, 0.103, 0.097, 0.093, 0.092]
    
    # F5 = 5 innings, ~21.5 PA per team
    f5_pa = LEAGUE_AVG['pa_per_inning'] * 5
    
    # Away vs Home pitcher
    away_f5_runs = 0
    away_matchups = []
    for i, hitter in enumerate(away_lineup[:9]):
        if not hitter:
            continue
        matchup = calculate_matchup(home_pitcher, hitter, park_factor)
        away_matchups.append(matchup)
        pa_share = pa_weights[i] if i < len(pa_weights) else 0.09
        away_f5_runs += matchup['runs_per_pa'] * f5_pa * pa_share
    
    # Home vs Away pitcher
    home_f5_runs = 0
    home_matchups = []
    for i, hitter in enumerate(home_lineup[:9]):
        if not hitter:
            continue
        matchup = calculate_matchup(away_pitcher, hitter, park_factor)
        home_matchups.append(matchup)
        pa_share = pa_weights[i] if i < len(pa_weights) else 0.09
        home_f5_runs += matchup['runs_per_pa'] * f5_pa * pa_share
    
    # Full game = F5 + 4 innings of bullpen
    bp_runs = LEAGUE_AVG['runs_per_inning'] * 4 * 1.05  # Bullpens slightly worse
    home_full = home_f5_runs + bp_runs * park_factor
    away_full = away_f5_runs + bp_runs
    
    return {
        'home_f5_runs': round(home_f5_runs, 2),
        'away_f5_runs': round(away_f5_runs, 2),
        'f5_total': round(home_f5_runs + away_f5_runs, 2),
        'home_full_runs': round(home_full, 2),
        'away_full_runs': round(away_full, 2),
        'full_total': round(home_full + away_full, 2),
        'home_matchups': home_matchups,
        'away_matchups': away_matchups,
    }

# Initialize database and import data
init_db()
import_csvs()

# ============== ROUTES ==============

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as cnt FROM players")
    player_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position = 'P'")
    pitcher_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT COUNT(*) as cnt FROM players WHERE position != 'P'")
    hitter_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT COUNT(*) as cnt FROM pitch_arsenal")
    arsenal_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    divisions = {}
    for t in teams:
        key = f"{t['league']} {t['division']}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(t)
    
    return render_template('index.html', 
                          player_count=player_count,
                          pitcher_count=pitcher_count,
                          hitter_count=hitter_count,
                          arsenal_count=arsenal_count,
                          teams=teams,
                          divisions=divisions)

@app.route('/teams')
def teams():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('teams.html', teams=teams)

@app.route('/team/<team_id>')
def team_detail(team_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,))
    team = cursor.fetchone()
    if not team:
        return "Team not found", 404
    team = dict(team)
    
    cursor.execute("""
        SELECT p.*, ps.* FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND p.position = 'P'
        ORDER BY ps.war DESC NULLS LAST
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("""
        SELECT p.*, hs.* FROM players p
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

@app.route('/api/team/<team_id>/roster')
def api_roster(team_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, ps.era, ps.whip, ps.k_rate, ps.war, ps.xwoba_against, ps.whiff_rate
        FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND p.position = 'P'
        ORDER BY ps.war DESC NULLS LAST
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("""
        SELECT p.*, hs.woba, hs.xwoba, hs.wrc_plus, hs.ops, hs.war, hs.k_rate, hs.barrel_rate
        FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND p.position != 'P'
        ORDER BY hs.wrc_plus DESC NULLS LAST
    """, (team_id,))
    hitters = [dict(r) for r in cursor.fetchall()]
    
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
    
    # Get pitchers
    cursor.execute("SELECT * FROM pitcher_stats WHERE player_id = ?", (data.get('home_pitcher_id'),))
    home_p = cursor.fetchone()
    home_pitcher = dict(home_p) if home_p else {}
    
    cursor.execute("SELECT * FROM pitcher_stats WHERE player_id = ?", (data.get('away_pitcher_id'),))
    away_p = cursor.fetchone()
    away_pitcher = dict(away_p) if away_p else {}
    
    # Get lineups
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

@app.route('/results')
def results():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM predictions ORDER BY created_at DESC LIMIT 50")
    predictions = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('results.html', predictions=predictions)

@app.route('/roster-manager')
def roster_manager():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teams ORDER BY name")
    teams = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('roster_manager.html', teams=teams)

@app.route('/api/player/<player_id>/move', methods=['POST'])
def api_move_player(player_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET team_id = ? WHERE player_id = ?", (data.get('team_id'), player_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
