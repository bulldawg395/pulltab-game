from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3, random, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'casino.db'

def db_conn():
    return sqlite3.connect(DATABASE)

def init_db():
    conn = db_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS spins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            symbols TEXT,
            payout REAL,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

SYMBOLS = ['🌴', '🍍', '🌞', '🌊', '🏖️', '🐚']
WINNING_COMBOS = {
    ('🌴', '🌴', '🌴'): 5,
    ('🍍', '🍍', '🍍'): 10,
    ('🌞', '🌞', '🌞'): 50
}

@app.route('/')
def home():
    return render_template('index.html', logged='user' in session, user=session.get('user'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    conn = db_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        session['user'] = username
    except sqlite3.IntegrityError:
        return "Username already taken."
    conn.close()
    return redirect('/')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session['user'] = username
        return redirect('/')
    return "Invalid credentials"

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/balance')
def balance():
    if 'user' not in session:
        return jsonify({'balance': 0})
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username = ?", (session['user'],))
    result = c.fetchone()
    conn.close()
    return jsonify({'balance': result[0] if result else 0})

@app.route('/play', methods=['POST'])
def play():
    if 'user' not in session:
        return jsonify({'error': 'Login required'})

    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username = ?", (session['user'],))
    row = c.fetchone()
    if not row or row[0] < 1:
        conn.close()
        return jsonify({'error': 'Insufficient balance'})

    symbols = tuple(random.choices(SYMBOLS, k=3))
    payout = WINNING_COMBOS.get(symbols, 0)
    new_balance = row[0] - 1 + payout

    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, session['user']))
    c.execute("INSERT INTO spins (username, symbols, payout, timestamp) VALUES (?, ?, ?, ?)",
              (session['user'], ''.join(symbols), payout, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({'symbols': symbols, 'payout': payout})

@app.route('/tower')
def tower():
    if 'user' not in session:
        return redirect('/')
    return render_template('tower.html')

@app.route('/tower_play', methods=['POST'])
def tower_play():
    if 'user' not in session:
        return jsonify({'error': 'Login required'})

    data = request.get_json()
    difficulty = data.get('difficulty')
    wager = float(data.get('wager', 0))
    path = data.get('path', [])

    if not difficulty or not path or wager <= 0:
        return jsonify({'error': 'Invalid data'})

    multipliers = {
        'easy': [1.00, 1.13, 1.27, 1.42, 1.58, 1.75, 1.93, 2.12, 2.32],
        'medium': [1.00, 1.21, 1.47, 1.78, 2.14, 2.56, 3.06, 3.63, 4.30],
        'hard': [1.00, 1.39, 1.93, 2.67, 3.70, 5.13, 7.12, 9.89, 13.72]
    }

    if difficulty not in multipliers:
        return jsonify({'error': 'Invalid difficulty'})

    multiplier_list = multipliers[difficulty]
    level = len(path)
    if level == 0 or level > 9:
        return jsonify({'error': 'Invalid path length'})

    multiplier = multiplier_list[level - 1]
    payout = round(wager * multiplier, 2)

    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username = ?", (session['user'],))
    balance_row = c.fetchone()
    if not balance_row or balance_row[0] < wager:
        conn.close()
        return jsonify({'error': 'Insufficient balance'})

    new_balance = balance_row[0] - wager + payout
    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, session['user']))
    c.execute("INSERT INTO spins (username, symbols, payout, timestamp) VALUES (?, ?, ?, ?)",
              (session['user'], f"TOWER-{difficulty}-{path}", payout, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'payout': payout})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if request.form.get('password') != 'Jcrx2009':
            return render_template('admin_login.html', error="Wrong password.")
        session['admin'] = True

    if not session.get('admin'):
        return render_template('admin_login.html')

    conn = db_conn()
    c = conn.cursor()

    # Add or subtract balance
    if request.method == 'GET' and request.args.get('adduser') and request.args.get('amount'):
        user = request.args['adduser']
        try:
            amount = float(request.args['amount'])
            c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, user))
            conn.commit()
        except:
            pass

    # Fetch users for balance management
    c.execute("SELECT username, balance FROM users")
    users = c.fetchall()

    # Fetch tower plays
    c.execute("""
        SELECT username, symbols, payout, timestamp 
        FROM spins 
        WHERE symbols LIKE 'TOWER-%'
        ORDER BY timestamp DESC LIMIT 50
    """)
    tower_plays = c.fetchall()

    conn.close()

    return render_template('admin.html', users=users, tower_plays=tower_plays)

@app.route('/admin_tower_history')
def admin_tower_history():
    if not session.get('admin'):
        return jsonify({'error': 'Access denied'})

    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'})

    conn = db_conn()
    c = conn.cursor()
    c.execute("""
        SELECT symbols, payout, timestamp FROM spins 
        WHERE username = ? AND symbols LIKE 'TOWER-%' ORDER BY timestamp DESC LIMIT 100
    """, (username,))
    rows = c.fetchall()
    conn.close()

    history = []
    for symbols, payout, timestamp in rows:
        parts = symbols.split('-')
        difficulty = parts[1] if len(parts) > 1 else 'unknown'
        path_raw = parts[2] if len(parts) > 2 else '[]'
        path = path_raw[1:-1]  # Strip brackets
        history.append({
            'difficulty': difficulty,
            'path': path,
            'payout': payout,
            'timestamp': timestamp
        })

    return jsonify({'history': history})

# Required for Render or similar deployment
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
