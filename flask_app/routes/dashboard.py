from flask import Blueprint, render_template, session, request,redirect, url_for
from db import get_db_connection
from psycopg2.extras import RealDictCursor
from datetime import datetime, date, timedelta

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../templates')

@dashboard_bp.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session.get('user_id', 1)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ================================
    # Year filter for dropdown
    # ================================
    cur.execute("""
        SELECT DISTINCT EXTRACT(YEAR FROM date) AS year
        FROM transactions
        WHERE user_id = %s
        ORDER BY year DESC;
    """, (user_id,))
    years = [int(r['year']) for r in cur.fetchall()]
    selected_year = request.args.get('year', datetime.now().year, type=int)

    # ================================
    # Monthly income vs expense (line chart)
    # ================================
    monthly_data = {m: {'income': 0.0, 'expense': 0.0} for m in range(1, 13)}
    cur.execute("""
        SELECT EXTRACT(MONTH FROM date) AS month,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expense
        FROM transactions
        WHERE user_id = %s AND EXTRACT(YEAR FROM date) = %s
        GROUP BY month;
    """, (user_id, selected_year))
    for row in cur.fetchall():
        m = int(row['month'])
        monthly_data[m]['income'] = float(row['income'])
        monthly_data[m]['expense'] = float(row['expense'])

    income_expense = [{
        'month': datetime(1900, m, 1).strftime('%b'),
        'income': monthly_data[m]['income'],
        'expense': monthly_data[m]['expense']
    } for m in range(1, 13)]

    # ================================
    # CURRENT MONTH INCOME & EXPENSE
    # ================================
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type='income' THEN amount END),0) AS income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount END),0) AS expense
        FROM transactions
        WHERE user_id=%s AND date_trunc('month', date)=date_trunc('month', CURRENT_DATE);
    """, (user_id,))
    current_month_totals = cur.fetchone() or {'income': 0, 'expense': 0}
    income = float(current_month_totals['income'])
    expense = float(current_month_totals['expense'])

    # ================================
    # LAST MONTH INCOME & EXPENSE
    # ================================
    last_month = date.today().replace(day=1) - timedelta(days=1)
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type='income' THEN amount END),0) AS income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount END),0) AS expense
        FROM transactions
        WHERE user_id=%s AND date_trunc('month', date)=date_trunc('month', %s::date);
    """, (user_id, last_month))
    last_month_totals = cur.fetchone() or {'income': 0, 'expense': 0}
    last_income = float(last_month_totals['income'])
    last_expense = float(last_month_totals['expense'])

    # ================================
    # TOTAL BALANCE (all accounts except liabilities)
    # ================================
    cur.execute("""
        SELECT COALESCE(SUM(balance),0) AS total_balance
        FROM accounts
        WHERE user_id=%s
        AND LOWER(type) NOT IN ('credit', 'short-term loan', 'long-term loan');
    """, (user_id,))
    total_balance = float(cur.fetchone()['total_balance'] or 0)

    # ================================
    # TOTAL BALANCE LAST MONTH (all accounts except liabilities)
    # ================================
    # sum of balances of accounts as of last month
    cur.execute("""
        SELECT COALESCE(SUM(balance),0) AS prev_balance
        FROM accounts
        WHERE user_id=%s
        AND LOWER(type) NOT IN ('credit', 'short-term loan', 'long-term loan');
    """, (user_id,))
    prev_balance = float(cur.fetchone()['prev_balance'] or 0)

    # ================================
    # Calculate percentage changes
    # ================================
    percent_change = round((total_balance - prev_balance)/abs(prev_balance)*100, 1) if prev_balance != 0 else 0
    income_change = round((income - last_income)/last_income*100, 1) if last_income != 0 else 0
    expense_change = round((expense - last_expense)/last_expense*100, 1) if last_expense != 0 else 0

    # ================================
    # Recent Transactions
    # ================================
    cur.execute("""
        SELECT t.date, t.description, c.name AS category, t.amount, t.type
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id=%s
        ORDER BY t.date DESC
        LIMIT 5;
    """, (user_id,))
    transactions = [{
        'date': r['date'].strftime('%Y-%m-%d'),
        'description': r['description'],
        'category': r['category'],
        'amount': float(r['amount']),
        'type': r['type']
    } for r in cur.fetchall()]

    # ================================
    # Budgets & Financial Goals
    # ================================
    cur.execute("SELECT COALESCE(SUM(amount),0) AS total_budget FROM budgets WHERE user_id=%s;", (user_id,))
    total_budget = float(cur.fetchone()['total_budget'] or 0)

    cur.execute("""
        SELECT COALESCE(SUM(amount),0) AS total_spent
        FROM transactions
        WHERE user_id=%s AND type='expense' AND date_trunc('month', date)=date_trunc('month', CURRENT_DATE);
    """, (user_id,))
    total_spent = float(cur.fetchone()['total_spent'] or 0)

    budget_summary = {'total_budget': total_budget, 'total_spent': total_spent}

    cur.execute("""
        SELECT c.name AS name, b.amount AS budget,
               COALESCE(SUM(t.amount),0) AS spent
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN transactions t
           ON t.category_id=b.category_id
           AND t.user_id=b.user_id
           AND t.type='expense'
           AND date_trunc('month', t.date)=date_trunc('month', CURRENT_DATE)
        WHERE b.user_id=%s
        GROUP BY c.name, b.amount
        ORDER BY c.name;
    """, (user_id,))
    budget_categories = []
    for r in cur.fetchall():
        budget = float(r['budget'])
        spent = float(r['spent'])
        remaining_percent = max(0, round((budget-spent)/budget*100,1)) if budget>0 else 0
        budget_categories.append({
            'name': r['name'],
            'budget': budget,
            'spent': spent,
            'remaining_percent': remaining_percent
        })

    # ================================
    # Financial Goals
    # ================================
    cur.execute("""
        SELECT name, current_amount, target_amount
        FROM financial_goals
        WHERE user_id=%s AND is_active=TRUE;
    """, (user_id,))
    goals = [{
        'name': g['name'],
        'current_amount': float(g['current_amount']),
        'target_amount': float(g['target_amount'])
    } for g in cur.fetchall()]

    cur.close()
    conn.close()

    return render_template(
        'dashboard.html',
        years=years,
        selected_year=selected_year,
        total_balance=total_balance,
        percent_change=percent_change,
        income=income,
        expense=expense,
        income_change=income_change,
        expense_change=expense_change,
        transactions=transactions,
        income_expense=income_expense,
        goals=goals,
        budget_summary=budget_summary,
        budget_categories=budget_categories,
        current_page='dashboard'
    )
