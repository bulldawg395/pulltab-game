from flask import Flask, render_template, request, session, redirect, jsonify
import sqlite3, random, datetime

app = Flask(__name__, static_folder="static")
app.secret_key = "secretkey"

db = sqlite3.connect("data.db", check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, password TEXT, balance REAL DEFAULT 0)""")
db.execute("""CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY, user TEXT, combination TEXT, payout REAL, ts TEXT)""")

@app.route("/")
def index():
    return render_template("index.html", logged="user" in session, user=session.get("user"))

@app.route("/register", methods=["POST"])
def register():
    u, p = request.form["username"], request.form["password"]
    try:
        db.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
        db.commit()
        session["user"] = u
    except: pass
    return redirect("/")

@app.route("/login", methods=["POST"])
def login():
    u, p = request.form["username"], request.form["password"]
    row = db.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p)).fetchone()
    if row: session["user"] = u
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear(); return redirect("/")

@app.route("/balance")
def balance():
    if "user" not in session: return jsonify({"balance":0})
    r = db.execute("SELECT balance FROM users WHERE username=?",(session["user"],)).fetchone()[0]
    return jsonify({"balance":round(r,2)})

@app.route("/play", methods=["POST"])
def play():
    if "user" not in session: return jsonify({"error":"Log in"})
    u=session["user"]; row=db.execute("SELECT balance FROM users WHERE username=?",(u,)).fetchone()[0]
    if row<1: return jsonify({"error":"Insufficient funds"})
    symbols=random.choices(["🌴","🍍","🌞","🌊","🏖️","🐚"],k=3)
    combo="".join(symbols)
    payout={"🌴🌴🌴":5,"🍍🍍🍍":10,"🌞🌞🌞":50}.get(combo,0)
    row=row-1+payout
    db.execute("UPDATE users SET balance=? WHERE username=?",(row,u))
    db.execute("INSERT INTO history(user,combination,payout,ts) VALUES(?,?,?,?)",
               (u,combo,payout,datetime.datetime.now().isoformat()))
    db.commit()
    return jsonify({"symbols":symbols,"payout":payout,"balance":round(row,2)})

@app.route("/history")
def history():
    if "user" not in session: return redirect("/")
    h = db.execute("SELECT combination,payout,ts FROM history WHERE user=? ORDER BY id DESC LIMIT 20",
                   (session["user"],)).fetchall()
    return render_template("history.html", hist=h)

@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method=="POST" and request.form.get("password")=="Jcrx2009":
        users=db.execute("SELECT username,balance FROM users").fetchall()
        return render_template("admin.html", access=True, users=users)
    return render_template("admin.html", access=False)

@app.route("/admin/fund", methods=["POST"])
def fund():
    if request.form.get("password")!="Jcrx2009": return redirect("/admin")
    u,a=request.form["username"],float(request.form["amount"])
    db.execute("UPDATE users SET balance=balance+? WHERE username=?",(a,u)); db.commit()
    return redirect("/admin")

app.run(host="0.0.0.0", port=3000)

@app.route("/info")
def info():
    return render_template("info.html")
