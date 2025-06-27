from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3, random, os, json
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS tower_plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            difficulty TEXT,
            path TEXT,
            wager REAL,
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
    session.pop('admin', None)
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

    # Adjust balances
    if request.args.get('adduser') and request.args.get('amount'):
        user = request.args['adduser']
        amount = float(request.args['amount'])
        c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, user))
        conn.commit()
    if request.args.get('removeuser') and request.args.get('amount'):
        user = request.args['removeuser']
        amount = float(request.args['amount'])
        c.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (amount, user))
        conn.commit()

    # Get user list
    c.execute("SELECT username, balance FROM users")
    users = c.fetchall()

    # Get tower plays
    c.execute("SELECT username, difficulty, wager, payout, timestamp FROM tower_plays ORDER BY id DESC LIMIT 20")
    towers = c.fetchall()
    conn.close()
    return render_template('admin.html', users=users, towers=towers)

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
    difficulty = data['difficulty']
    wager = float(data['wager'])
    path = data['path']
    username = session['user']

    conn = db_conn()
    c = conn.cursor()

    c.execute("SELECT balance FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if not result or result[0] < wager:
        conn.close()
        return jsonify({'error': 'Insufficient balance'})

    multipliers = {
        'easy': [1.26, 1.68, 2.24, 2.99, 3.98, 5.31, 7.08, 9.44, 12.59],
        'medium': [1.42, 2.13, 3.19, 4.78, 7.18, 10.76, 16.15, 24.22, 36.33],
        'hard': [1.89, 3.78, 7.56, 15.12, 30.24, 60.48, 120.96, 241.92, 483.84]
    }

    multiplier = multipliers[difficulty][len(path)-1]
    payout = round(wager * multiplier, 2)
    new_balance = result[0] + payout

    # Subtract wager at the beginning
    c.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (wager, username))
    conn.commit()

    # Add payout only if game result posted
    c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (payout, username))
    c.execute("INSERT INTO tower_plays (username, difficulty, path, wager, payout, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (username, difficulty, json.dumps(path), wager, payout, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'payout': payout})

@app.route('/mines')
def mines():
    if 'user' not in session:
        return redirect('/')
    return render_template('mines.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
