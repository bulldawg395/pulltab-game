from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

def init_db():
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
                     id INTEGER PRIMARY KEY,
                     username TEXT UNIQUE,
                     password TEXT,
                     balance REAL DEFAULT 0
        )""")
        conn.commit()

init_db()

@app.route("/")
def home():
    if "user" not in session:
        return render_template("index.html", logged_in=False)
    return render_template("index.html", logged_in=True, username=session["user"])

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    password = request.form["password"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            return redirect("/")
        except:
            return "Username taken"

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        result = c.fetchone()
        if result:
            session["user"] = username
    return redirect("/")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route("/balance")
def balance():
    if "user" not in session:
        return "Not logged in"
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE username=?", (session["user"],))
        bal = c.fetchone()[0]
        return jsonify({"balance": round(bal, 2)})

@app.route("/play", methods=["POST"])
def play():
    if "user" not in session:
        return jsonify({"error": "Not logged in"})
    import random
    combos = [
        ["🏖️", "🌊", "🍍"], ["🐚", "🌊", "🌴"], ["🌴", "🏖️", "🐚"],
        ["🌊", "🍍", "🌞"], ["🐚", "🏖️", "🌴"], ["🌞", "🌊", "🍍"],
        ["🌊", "🌊", "🌊"], ["🏖️", "🏖️", "🏖️"], ["🐚", "🐚", "🐚"],
        ["🌴", "🌴", "🌴"], ["🍍", "🍍", "🍍"], ["🌞", "🌞", "🌞"]
    ]
    winning = {"🌴🌴🌴": 5, "🍍🍍🍍": 10, "🌞🌞🌞": 50}
    combo = random.choice(combos)
    result = "".join(combo)
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE username=?", (session["user"],))
        bal = c.fetchone()[0]
        if bal < 1:
            return jsonify({"error": "Insufficient balance"})
        new_bal = bal - 1 + winning.get(result, 0)
        c.execute("UPDATE users SET balance=? WHERE username=?", (new_bal, session["user"]))
        conn.commit()
    return jsonify({
        "symbols": combo,
        "payout": winning.get(result, 0),
        "balance": round(new_bal, 2)
    })

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "GET":
        return render_template("admin.html")
    if request.form["password"] != "Jcrx2009":
        return "Wrong password"
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT username, balance FROM users")
        users = c.fetchall()
        return render_template("admin.html", users=users, access=True)

@app.route("/admin/fund", methods=["POST"])
def admin_fund():
    if request.form["password"] != "Jcrx2009":
        return "Wrong password"
    username = request.form["username"]
    amount = float(request.form["amount"])
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ? WHERE username=?", (amount, username))
        conn.commit()
    return redirect("/admin")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
