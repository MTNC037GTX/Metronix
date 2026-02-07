from flask import Blueprint, render_template, redirect, url_for, session, request
from datetime import datetime
from db import get_db_connection
from psycopg2.extras import RealDictCursor

budget_bp = Blueprint('budget', __name__, url_prefix='/budget')


@budget_bp.route('/', methods=['GET'])
def budget_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ---------------------------------------------------
    # Ensure ALL expense categories have a budget row
    # ---------------------------------------------------
    cur.execute("""
        INSERT INTO budgets (user_id, category_id, account_id, amount, created_at)
        SELECT %s, c.id, 1, 0, %s
        FROM categories c
        WHERE c.type = 'expense'
        AND NOT EXISTS (
            SELECT 1 FROM budgets b
            WHERE b.user_id = %s
              AND b.category_id = c.id
              AND b.account_id = 1
        )
    """, (user_id, now, user_id))
    conn.commit()

    # ---------------------------------------------------
    # Summary cards
    # ---------------------------------------------------
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM budgets
        WHERE user_id = %s
    """, (user_id,))
    total_budgeted = cur.fetchone()['total']

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = %s
          AND type = 'expense'
          AND created_at >= %s
    """, (user_id, month_start))
    total_spent = cur.fetchone()['total']

    remaining_budget = total_budgeted - total_spent
    budget_used_percent = round((total_spent / total_budgeted) * 100) if total_budgeted > 0 else 0

    budget_change_percent = 0
    spent_change_percent = 0

    # ---------------------------------------------------
    # Category-level budgets (expense only)
    # ---------------------------------------------------
    cur.execute("""
        SELECT
            c.id AS category_id,
            c.name AS category_name,
            b.amount AS budgeted,
            COALESCE((
                SELECT SUM(t.amount)
                FROM transactions t
                WHERE t.user_id = %s
                  AND t.category_id = c.id
                  AND t.type = 'expense'
                  AND t.created_at >= %s
            ), 0) AS spent
        FROM categories c
        JOIN budgets b
          ON b.category_id = c.id
         AND b.user_id = %s
         AND b.account_id = 1
        WHERE c.type = 'expense'
        ORDER BY c.name
    """, (user_id, month_start, user_id))

    category_budgets = cur.fetchall()

    for item in category_budgets:
        item['remaining'] = item['budgeted'] - item['spent']
        item['used_percent'] = min(
            round((item['spent'] / item['budgeted']) * 100) if item['budgeted'] > 0 else 0,
            100
        )

    cur.close()
    conn.close()

    return render_template(
        'budget.html',
        total_budgeted=total_budgeted,
        total_spent=total_spent,
        remaining_budget=remaining_budget,
        budget_used_percent=budget_used_percent,
        budget_change_percent=budget_change_percent,
        spent_change_percent=spent_change_percent,
        category_budgets=category_budgets,
        current_page='budget'
    )


# ---------------------------------------------------
# Edit Budget
# ---------------------------------------------------
@budget_bp.route('/edit', methods=['POST'])
def edit_budget():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    category_id = request.form.get('category_id')
    amount = request.form.get('amount')

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return redirect(url_for('budget.budget_page'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE budgets
        SET amount = %s
        WHERE user_id = %s
          AND category_id = %s
          AND account_id = 1
    """, (amount, user_id, category_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('budget.budget_page'))
