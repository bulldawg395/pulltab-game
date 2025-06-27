from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3, random, os
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'casino.db'
active_mines_games = {}

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

def get_mines_multipliers(bombs, rtp=0.94, total_tiles=25):
    safe_tiles = total_tiles - bombs
    multipliers = []

    for k in range(1, safe_tiles + 1):
        prob = 1.0
        for i in range(k):
            prob *= (safe_tiles - i) / (total_tiles - i)

        if prob == 0:
            multipliers.append(0)
        else:
            multiplier = rtp / prob
            multipliers.append(round(multiplier, 2))

    return multipliers

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
    if request.method == 'POST':
        if request.form.get('password') != 'Jcrx2009':
            return render_template('admin_login.html', error="Wrong password.")
        session['admin'] = True

    if not session.get('admin'):
        return render_template('admin_login.html')

    try:
        conn = db_conn()
        c = conn.cursor()
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

@app.route('/mines')
def mines_page():
    if 'user' not in session:
        return redirect('/')
    return render_template('mines.html')

@app.route('/mines/start', methods=['POST'])
def mines_start():
    data = request.get_json()
    bet = float(data['bet'])
    bombs = int(data['bombs'])

    if 'user' not in session:
        return jsonify({'error': 'Login required'})

    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username = ?", (session['user'],))
    row = c.fetchone()
    if not row or row[0] < bet:
        conn.close()
        return jsonify({'error': 'Insufficient balance'})

    new_balance = row[0] - bet
    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, session['user']))
    conn.commit()
    conn.close()

    bomb_cells = random.sample([(r, c) for r in range(5) for c in range(5)], bombs)
    game_id = str(uuid.uuid4())
    multipliers = get_mines_multipliers(bombs)

    active_mines_games[game_id] = {
        'bombs': bomb_cells,
        'revealed': [],
        'bet': bet,
        'user': session['user'],
        'multipliers': multipliers,
        'bomb_count': bombs
    }

    return jsonify({'game_id': game_id})

@app.route('/mines/click', methods=['POST'])
def mines_click():
    data = request.get_json()
    game_id = data['game_id']
    coord = (data['row'], data['col'])

    if game_id not in active_mines_games:
        return jsonify({'error': 'Invalid game ID'})

    game = active_mines_games[game_id]
    if coord in game['revealed']:
        return jsonify({'error': 'Already revealed'})

    if coord in game['bombs']:
        del active_mines_games[game_id]
        return jsonify({'bomb': True, 'revealed': coord})

    game['revealed'].append(coord)
    safe_clicks = len(game['revealed'])

    if safe_clicks <= len(game['multipliers']):
        multiplier = game['multipliers'][safe_clicks - 1]
    else:
        multiplier = game['multipliers'][-1]

    return jsonify({
        'bomb': False,
        'revealed': coord,
        'multiplier': round(multiplier, 2),
        'safe_count': safe_clicks
    })

@app.route('/mines/cashout', methods=['POST'])
def mines_cashout():
    data = request.get_json()
    game_id = data['game_id']

    if game_id not in active_mines_games:
        return jsonify({'error': 'Invalid game ID'})

    game = active_mines_games[game_id]
    if game['user'] != session['user']:
        return jsonify({'error': 'Not your game'})

    safe_clicks = len(game['revealed'])
    if safe_clicks == 0:
        payout = 0
    elif safe_clicks <= len(game['multipliers']):
        payout = round(game['bet'] * game['multipliers'][safe_clicks - 1], 2)
    else:
        payout = round(game['bet'] * game['multipliers'][-1], 2)

    conn = db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (payout, session['user']))
    conn.commit()
    conn.close()

    del active_mines_games[game_id]
    return jsonify({'payout': payout})

@app.route('/admin/remove')
def admin_remove_balance():
    if not session.get('admin'):
        return redirect('/admin')

    user = request.args.get('removeuser')
    amount = float(request.args.get('amount', 0))

    conn = db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (amount, user))
    conn.commit()
    conn.close()

    return redirect('/admin')


@app.route('/admin/user/<username>')
def user_history(username):
    if not session.get('admin'):
        return redirect('/admin')

    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT symbols, payout, timestamp FROM spins WHERE username = ? ORDER BY id DESC", (username,))
    history = c.fetchall()
    conn.close()

    return render_template('user_history.html', username=username, history=history)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
