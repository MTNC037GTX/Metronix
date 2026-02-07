from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from psycopg2.extras import RealDictCursor

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Please enter both email and password', 'error')
            return render_template('landing.html')

        # Connect to DB
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check if user exists
        cur.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s;",
            (email, password)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            # Store user info in session
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'error')
            return render_template('landing.html')

    # GET request
    return render_template('landing.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
