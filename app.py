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

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # If already logged in as admin, show admin panel
    if session.get('admin'):
        try:
            conn = db_conn()
            c = conn.cursor()

            # Add balance if requested
            if request.args.get('adduser') and request.args.get('amount'):
                user = request.args['adduser']
                amount = float(request.args['amount'])
                c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, user))
                conn.commit()

            c.execute("SELECT username, balance FROM users")
            users = c.fetchall()
            conn.close()

            return render_template('admin.html', users=users)

        except Exception as e:
            return f"An error occurred in /admin: {e}"

    # Handle login form submission
    if request.method == 'POST':
        if request.form.get('password') == 'Jcrx2009':
            session['admin'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error="Wrong password.")

    # Show login form
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/')

@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/')
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT symbols, payout, timestamp FROM spins WHERE username = ? ORDER BY id DESC LIMIT 20", (session['user'],))
    history = c.fetchall()
    conn.close()
    return render_template('history.html', history=history)

@app.route('/info')
def info():
    return render_template('info.html')

import json
import uuid

# Mines game storage (temporary in memory)
active_mines_games = {}

@app.route('/mines')
def mines():
    if 'user' not in session:
        return redirect('/')
    return render_template('mines.html', user=session['user'])

@app.route('/mines/start', methods=['POST'])
def mines_start():
    if 'user' not in session:
        return jsonify({'error': 'Login required'})

    data = request.json
    bet = float(data.get('bet'))
    bombs = int(data.get('bombs'))

    if bet < 0.1 or bet > 1000:
        return jsonify({'error': 'Invalid bet size'})
    if bombs < 1 or bombs > 24:
        return jsonify({'error': 'Invalid bomb count'})

    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username = ?", (session['user'],))
    user = c.fetchone()
    if not user or user[0] < bet:
        conn.close()
        return jsonify({'error': 'Insufficient balance'})

    # Deduct bet
    new_balance = user[0] - bet
    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, session['user']))
    conn.commit()
    conn.close()

    # Create grid with bombs
    all_cells = [(r, c) for r in range(5) for c in range(5)]
    bomb_cells = random.sample(all_cells, bombs)

    game_id = str(uuid.uuid4())
    active_mines_games[game_id] = {
        'bombs': bomb_cells,
        'revealed': [],
        'bet': bet,
        'user': session['user']
    }

    return jsonify({'game_id': game_id})

@app.route('/mines/click', methods=['POST'])
def mines_click():
    if 'user' not in session:
        return jsonify({'error': 'Login required'})

    data = request.json
    game_id = data.get('game_id')
    row = int(data.get('row'))
    col = int(data.get('col'))

    game = active_mines_games.get(game_id)
    if not game or game['user'] != session['user']:
        return jsonify({'error': 'Game not found'})

    coord = (row, col)
    if coord in game['revealed']:
        return jsonify({'error': 'Already revealed'})

    if coord in game['bombs']:
        del active_mines_games[game_id]
        return jsonify({'bomb': True, 'revealed': coord})

    game['revealed'].append(coord)
    multiplier = round(1 + 0.2 * len(game['revealed']), 2)

    return jsonify({
        'bomb': False,
        'revealed': coord,
        'multiplier': multiplier,
        'safe_count': len(game['revealed'])
    })

@app.route('/mines/cashout', methods=['POST'])
def mines_cashout():
    if 'user' not in session:
        return jsonify({'error': 'Login required'})

    data = request.json
    game_id = data.get('game_id')
    game = active_mines_games.pop(game_id, None)
    if not game or game['user'] != session['user']:
        return jsonify({'error': 'Invalid game'})

    payout = round(game['bet'] * (1 + 0.2 * len(game['revealed'])), 2)

    conn = db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (payout, session['user']))
    conn.commit()
    conn.close()

    return jsonify({'payout': payout})

# ✅ Required for Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
