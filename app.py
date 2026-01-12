"""
MLB Prediction Model - Fixed for Railway
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'mlb_model_2025'

# Use /tmp for Railway (writable directory)
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
            siera REAL, xfip REAL, war REAL,
            fb_pct REAL, sl_pct REAL, cb_pct REAL, ch_pct REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hitter_stats (
            player_id TEXT PRIMARY KEY,
            woba REAL, xwoba REAL, wrc_plus REAL, ops REAL,
            k_rate REAL, bb_rate REAL, barrel_rate REAL, war REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date TEXT, home_team TEXT, away_team TEXT,
            f5_total REAL, full_total REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

# Initialize on startup
init_db()

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as cnt FROM players")
    player_count = cursor.fetchone()['cnt']
    
    cursor.execute("SELECT * FROM teams ORDER BY league, division, name")
    teams = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    # Group teams by division
    divisions = {}
    for t in teams:
        key = f"{t['league']} {t['division']}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(t)
    
    return render_template('index.html', 
                          player_count=player_count,
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
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("""
        SELECT p.*, hs.* FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND (p.position != 'P' OR p.position IS NULL)
    """, (team_id,))
    hitters = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return render_template('team.html', team=team, pitchers=pitchers, hitters=hitters)

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
        SELECT p.*, ps.era, ps.whip, ps.k_rate, ps.war
        FROM players p
        LEFT JOIN pitcher_stats ps ON p.player_id = ps.player_id
        WHERE p.team_id = ? AND p.position = 'P'
    """, (team_id,))
    pitchers = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("""
        SELECT p.*, hs.woba, hs.xwoba, hs.wrc_plus, hs.ops, hs.war
        FROM players p
        LEFT JOIN hitter_stats hs ON p.player_id = hs.player_id
        WHERE p.team_id = ? AND (p.position != 'P' OR p.position IS NULL)
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
    
    # Simple projection logic
    home_f5 = 2.5
    away_f5 = 2.5
    
    return jsonify({
        'home_f5_runs': home_f5,
        'away_f5_runs': away_f5,
        'f5_total': home_f5 + away_f5,
        'home_full_runs': home_f5 + 2.0,
        'away_full_runs': away_f5 + 2.0,
        'full_total': (home_f5 + 2.0) + (away_f5 + 2.0),
        'home_win_prob': 0.5,
        'home_matchups': [],
        'away_matchups': [],
        'calculation_steps': ['Projection calculated']
    })

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
