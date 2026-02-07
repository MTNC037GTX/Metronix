from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
from db import get_db_connection
from psycopg2.extras import RealDictCursor

transaction_bp = Blueprint('transaction', __name__, url_prefix='/transaction')


# -------------------------
# Transaction Page
# -------------------------
@transaction_bp.route('/', methods=['GET'])
def transaction_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']

    # Current year + month
    today = datetime.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))

    # Previous month calculation
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Transactions with account + category, include current balance
    cursor.execute("""
        SELECT
            t.id,
            t.date,
            t.description,
            COALESCE(t.amount, 0) AS amount,
            t.type,
            c.name AS category,
            COALESCE(a.name, '--') AS account,
            COALESCE(ta.name, '--') AS transfer_account_name,
            COALESCE(a.balance, 0) AS account_balance
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts ta ON t.transfer_account_id = ta.id
        WHERE t.user_id = %s
          AND EXTRACT(YEAR FROM t.date) = %s
          AND EXTRACT(MONTH FROM t.date) = %s
        ORDER BY t.date DESC, t.id DESC
    """, (user_id, year, month))
    transactions = cursor.fetchall()

    # Categories
    cursor.execute("""
        SELECT id, name, type
        FROM categories
        WHERE user_id = %s
        ORDER BY name
    """, (user_id,))
    categories = cursor.fetchall()

    # Accounts
    cursor.execute("""
        SELECT id, name, balance
        FROM accounts
        WHERE user_id = %s
        ORDER BY name
    """, (user_id,))
    accounts = cursor.fetchall()

    # Current month summary
    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type='income' THEN amount END),0) AS total_income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount END),0) AS total_expense
        FROM transactions
        WHERE user_id = %s
          AND EXTRACT(YEAR FROM date) = %s
          AND EXTRACT(MONTH FROM date) = %s
    """, (user_id, year, month))
    current_summary = cursor.fetchone()
    total_income = float(current_summary['total_income'] or 0)
    total_expense = float(current_summary['total_expense'] or 0)
    net_cash_flow = total_income - total_expense

    # Previous month summary
    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type='income' THEN amount END),0) AS total_income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount END),0) AS total_expense
        FROM transactions
        WHERE user_id = %s
          AND EXTRACT(YEAR FROM date) = %s
          AND EXTRACT(MONTH FROM date) = %s
    """, (user_id, prev_year, prev_month))
    prev_summary = cursor.fetchone()
    prev_income = float(prev_summary['total_income'] or 0)
    prev_expense = float(prev_summary['total_expense'] or 0)
    prev_net = prev_income - prev_expense

    # Percentage change calculation
    def calc_change(current, previous):
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 1)

    income_change = calc_change(total_income, prev_income)
    expense_change = calc_change(total_expense, prev_expense)
    net_change = calc_change(net_cash_flow, prev_net)

    cursor.close()
    conn.close()

    return render_template(
        'transaction.html',
        transactions=transactions,
        categories=categories,
        accounts=accounts,
        total_income=total_income,
        total_expense=total_expense,
        net_cash_flow=net_cash_flow,
        income_change=income_change,
        expense_change=expense_change,
        net_change=net_change,
        selected_year=year,
        selected_month=month,
        current_page='transaction',
        datetime=datetime
    )


# -------------------------
# Add transaction
# -------------------------
@transaction_bp.route('/add', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    date_val = request.form.get('date') or datetime.today().strftime('%Y-%m-%d')
    category_id = int(request.form.get('category_id')) if request.form.get('category_id') else None
    account_id = int(request.form.get('account_id')) if request.form.get('account_id') else None
    description = request.form.get('description') or ''
    amount = float(request.form.get('amount') or 0)
    txn_type = request.form.get('type') or 'expense'
    notes = request.form.get('notes') or ''

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Insert transaction
    cursor.execute("""
        INSERT INTO transactions
        (user_id, date, category_id, account_id, description, amount, type, notes, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
        RETURNING id
    """, (user_id, date_val, category_id, account_id, description, amount, txn_type, notes))
    txn_id = cursor.fetchone()['id']

    # Update account balance
    if account_id:
        if txn_type == 'income':
            cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s", (amount, account_id))
        elif txn_type == 'expense':
            cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id=%s", (amount, account_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('transaction.transaction_page'))


# -------------------------
# Add transfer
# -------------------------
@transaction_bp.route('/add_transfer', methods=['POST'])
def add_transfer():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    from_account_id = int(request.form.get('from_account_id')) if request.form.get('from_account_id') else None
    to_account_id = int(request.form.get('to_account_id')) if request.form.get('to_account_id') else None
    amount = float(request.form.get('amount') or 0)
    date_val = request.form.get('date') or datetime.today().strftime('%Y-%m-%d')
    notes = request.form.get('notes') or ''

    if not from_account_id or not to_account_id or amount <= 0:
        return redirect(url_for('transaction.transaction_page'))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Insert transfer transaction
    cursor.execute("""
        INSERT INTO transactions
        (user_id, date, account_id, transfer_account_id, amount, type, description, notes, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,'transfer','Transfer',%s,NOW(),NOW())
        RETURNING id
    """, (user_id, date_val, from_account_id, to_account_id, amount, notes))
    txn_id = cursor.fetchone()['id']

    # Update balances
    cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id=%s", (amount, from_account_id))
    cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s", (amount, to_account_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('transaction.transaction_page'))


# -------------------------
# Delete transaction
# -------------------------
@transaction_bp.route('/delete/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get transaction info
    cursor.execute("SELECT * FROM transactions WHERE id=%s AND user_id=%s", (transaction_id, user_id))
    txn = cursor.fetchone()
    if not txn:
        cursor.close()
        conn.close()
        return redirect(url_for('transaction.transaction_page'))

    # Update balances before delete
    account_id = txn['account_id']
    transfer_account_id = txn['transfer_account_id']
    amount = float(txn['amount'] or 0)
    txn_type = txn['type']

    if txn_type == 'income' and account_id:
        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id=%s", (amount, account_id))
    elif txn_type == 'expense' and account_id:
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s", (amount, account_id))
    elif txn_type == 'transfer' and account_id and transfer_account_id:
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s", (amount, account_id))
        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE id=%s", (amount, transfer_account_id))

    # Delete transaction
    cursor.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (transaction_id, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('transaction.transaction_page'))


# -------------------------
# Get account balance API
# -------------------------
@transaction_bp.route('/account_balance/<int:account_id>', methods=['GET'])
def get_account_balance(account_id):
    if 'user_id' not in session:
        return jsonify({"balance": 0})

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT COALESCE(balance,0) AS balance
        FROM accounts
        WHERE id=%s AND user_id=%s
    """, (account_id, user_id))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    balance = float(result['balance']) if result else 0
    return jsonify({"balance": balance})


# -------------------------
# Month filter API
# -------------------------
@transaction_bp.route('/transactions_data', methods=['GET'])
def transactions_data():
    if 'user_id' not in session:
        return {"transactions": []}

    user_id = session['user_id']
    month_param = request.args.get('month')
    type_filter = request.args.get('type', 'all')
    search = request.args.get('search', '').lower()

    if not month_param:
        today = datetime.today()
        year, month_num = today.year, today.month
    else:
        try:
            year, month_num = (int(x) for x in month_param.split('-'))
        except ValueError:
            return {"transactions": []}

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            t.id,
            t.date,
            t.description,
            COALESCE(t.amount,0) AS amount,
            t.type,
            c.name AS category,
            COALESCE(a.name, '--') AS account,
            COALESCE(ta.name, '--') AS transfer_account_name,
            COALESCE(a.balance,0) AS account_balance
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts ta ON t.transfer_account_id = ta.id
        WHERE t.user_id = %s
          AND EXTRACT(YEAR FROM t.date) = %s
          AND EXTRACT(MONTH FROM t.date) = %s
        ORDER BY t.date DESC, t.id DESC
    """, (user_id, year, month_num))

    transactions = cursor.fetchall()
    cursor.close()
    conn.close()

    # Type and search filter
    if type_filter != 'all':
        transactions = [t for t in transactions if t['type'].lower() == type_filter.lower()]

    if search:
        transactions = [
            t for t in transactions
            if search in (t['description'] or '').lower()
            or search in (t['category'] or '').lower()
            or search in (t['account'] or '').lower()
        ]

    # Format date and amounts for frontend
    for t in transactions:
        t['date'] = t['date'].strftime('%Y-%m-%d') if t['date'] else ''
        t['amount'] = float(t['amount'] or 0)
        t['account_balance'] = float(t['account_balance'] or 0)

    return {"transactions": transactions}
