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

        # Add balance to a user if requested
        if request.args.get('adduser') and request.args.get('amount'):
            user = request.args['adduser']
            amount = float(request.args['amount'])
            c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, user))
            conn.commit()

        # Show all users
        c.execute("SELECT username, balance FROM users")
        users = c.fetchall()
        conn.close()

        return render_template('admin.html', users=users)

    except Exception as e:
        return f"An error occurred in /admin: {e}"
