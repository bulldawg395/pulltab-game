from flask import Flask, render_template, request, session, redirect, jsonify
import sqlite3
import random

app = Flask(__name__, static_folder="static")
app.secret_key = "supersecretkey"

def db():
    conn = sqlite3.connect("data.db", check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, balance REAL DEFAULT 0
    )""")
    return conn

db_conn = db()

@app.route("/")
def index():
    return render_template("index.html", logged_in="user" in session, username=session.get("user"))

@app.route("/register", methods=["POST"])
def register():
    u = request.form["username"]
    p = request.form["password"]
    try:
        db_conn.execute("INSERT INTO users(username, password) VALUES(?,?)", (u, p))
        db_conn.commit()
    except:
        pass
    return redirect("/")

@app.route("/login", methods=["POST"])
def login():
    u = request.form["username"]
    p = request.form["password"]
    row = db_conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
    if row: session["user"] = u
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/balance")
def balance():
    if "user" not in session: return jsonify({"balance": 0})
    bal = db_conn.execute("SELECT balance FROM users WHERE username=?", (session["user"],)).fetchone()[0]
    return jsonify({"balance": round(bal, 2)})

@app.route("/play", methods=["POST"])
def play():
    if "user" not in session: return jsonify({"error": "Login required"})
    u = session["user"]
    bal = db_conn.execute("SELECT balance FROM users WHERE username=?", (u,)).fetchone()[0]
    if bal < 1: return jsonify({"error": "Not enough funds"})

    symbols = random.choices(["🌴", "🍍", "🌞", "🌊", "🏖️", "🐚"], k=3)
    result = "".join(symbols)
    payouts = {"🌴🌴🌴": 5, "🍍🍍🍍": 10, "🌞🌞🌞": 50}
    payout = payouts.get(result, 0)

    bal = bal - 1 + payout
    db_conn.execute("UPDATE users SET balance=? WHERE username=?", (bal, u))
    db_conn.commit()

    return jsonify({"symbols": symbols, "payout": payout})

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and request.form.get("password") == "Jcrx2009":
        users = db_conn.execute("SELECT username, balance FROM users").fetchall()
        return render_template("admin.html", access=True, users=users)
    return render_template("admin.html", access=False)

@app.route("/admin/fund", methods=["POST"])
def fund():
    if request.form.get("password") != "Jcrx2009": return redirect("/admin")
    user = request.form["username"]
    amount = float(request.form["amount"])
    db_conn.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, user))
    db_conn.commit()
    return redirect("/admin")

app.run(host="0.0.0.0", port=3000)
