from flask import Blueprint, render_template, session, redirect, url_for, request
from db import get_db_connection
from psycopg2.extras import RealDictCursor
from datetime import date, datetime

goals_bp = Blueprint('goals', __name__, url_prefix='/goals')


@goals_bp.route('/', methods=['GET'])
def goals_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    today = date.today()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ----------------------------
    # Fetch goals
    # ----------------------------
    cur.execute("""
        SELECT
            g.id,
            g.name,
            g.goal_type,
            g.target_amount,
            g.current_amount,
            g.start_date,
            g.target_date,
            g.linked_account_id,
            a.name AS linked_name,
            a.balance AS linked_balance
        FROM financial_goals g
        LEFT JOIN accounts a ON g.linked_account_id = a.id
        WHERE g.user_id = %s
          AND g.is_active = TRUE
        ORDER BY g.created_at DESC
    """, (user_id,))

    raw_goals = cur.fetchall()

    # ----------------------------
    # Fetch ALL accounts (for Add Goal popup)
    # ----------------------------
    cur.execute("""
        SELECT id, name, type, balance
        FROM accounts
        WHERE user_id = %s
        ORDER BY name
    """, (user_id,))
    accounts = cur.fetchall()

    goals = []
    total_goals = 0
    completed_count = 0
    on_track_count = 0
    at_risk_count = 0

    goal_type_labels = {
        'savings': 'Savings Goal',
        'debt': 'Debt Reduction',
        'net_worth': 'Net Worth',
        'investment': 'Investment Goal',
        'income': 'Income Target',
    }
    
    
    def calculate_net_worth_goal_progress(g, accounts):
        """Calculate progress for net worth goals."""

        # Target from the goal row
        target = float(g['target_amount'])

        # Define asset and liability categories
        ASSET_CATEGORIES = {
            'Cash and Equivalents': ['cash', 'ewallet', 'savings'],
            'Investments': ['investment'],
            'Real Estate': ['real estate'],
            'Personal Property': ['property'],
            'Other Assets': ['other assets']
        }

        LIABILITY_CATEGORIES = {
            'Short-term Debt': ['short-term loan', 'credit'],
            'Long-term Debt': ['long-term loan']
        }

        # Sum total assets
        total_assets = 0
        for types in ASSET_CATEGORIES.values():
            total_assets += sum(
                float(acc.get('balance', 0)) 
                for acc in accounts 
                if acc.get('type') in types
            )

        # Sum total liabilities
        total_liabilities = 0
        for types in LIABILITY_CATEGORIES.values():
            total_liabilities += sum(
                float(acc.get('balance', 0)) 
                for acc in accounts 
                if acc.get('type') in types
            )

        # Current net worth
        current = total_assets + total_liabilities

        # Progress for UI
        progress_ratio = max(0, min(1, current / target))
        remaining_amount = max(0, target - current)
        delta_label = 'RM {:,.2f} to go'.format(remaining_amount)

        return current, target, progress_ratio, delta_label



    def calculate_debt_goal_progress(g):
        """Calculate progress for debt reduction goals."""
        # Target should always be positive
        target = abs(float(g['target_amount']))

        # Current balance from linked account
        linked_balance = float(g['linked_balance']) if g['linked_balance'] is not None else 0.0
        # Initial amount when goal was created (stored in the goal row)
        initial_amount = float(g.get('initial_amount', target))  # fallback to target if not present

        # Current amount = how much debt has been reduced
        current = initial_amount - abs(linked_balance)
        current = max(0, current)  # cannot be negative

        # Remaining = amount left to pay
        remaining_amount = max(0, target - current)

        # Progress ratio for UI
        progress_ratio = max(0, min(1, current / target))
        delta_label = 'RM {:,.2f} remaining'.format(remaining_amount)

        return current, target, progress_ratio, delta_label


    def calculate_regular_goal_progress(g):
        """Calculate progress for all other goal types."""
        target = float(g['target_amount'])

        # Update current_amount if linked to an account
        if g['linked_account_id']:
            current = float(g['linked_balance']) if g['linked_balance'] is not None else 0.0
        else:
            current = float(g['current_amount'])

        progress_ratio = max(0, min(1, current / target))
        delta_label = 'RM {:,.2f} to go'.format(target - current)

        return current, target, progress_ratio, delta_label


    # ----------------------------
    # Main loop
    # ----------------------------
    for g in raw_goals:
        total_goals += 1
        start_date = g['start_date']
        target_date = g['target_date']
        goal_type = g['goal_type']

        if goal_type == 'debt':
            current, target, progress_ratio, delta_label = calculate_debt_goal_progress(g)
        elif goal_type == 'net_worth':
            current, target, progress_ratio, delta_label = calculate_net_worth_goal_progress(g, accounts)
        else:
            current, target, progress_ratio, delta_label = calculate_regular_goal_progress(g)

        progress_percent = round(progress_ratio * 100)


        # ----------------------------
        # Status calculation
        # ----------------------------
        if progress_ratio >= 1:
            status = 'completed'
            status_label = 'Completed'
            completed_count += 1
        else:
            total_days = (target_date - start_date).days
            elapsed_days = (today - start_date).days

            if total_days <= 0 or elapsed_days < 0:
                status = 'at_risk'
                status_label = 'At Risk'
                at_risk_count += 1
            else:
                expected_progress = elapsed_days / total_days
                if progress_ratio >= expected_progress:
                    status = 'on_track'
                    status_label = 'On Track'
                    on_track_count += 1
                else:
                    status = 'at_risk'
                    status_label = 'At Risk'
                    at_risk_count += 1

        goals.append({
            'id': g['id'],
            'name': g['name'],
            'goal_type': goal_type,
            'goal_type_label': goal_type_labels.get(goal_type, 'Goal'),
            'linked_account_id': g['linked_account_id'],
            'linked_name': g['linked_name'],
            'current_amount': current,
            'target_amount': target,
            'progress_percent': progress_percent,
            'status': status,
            'status_label': status_label,
            'target_label': 'Target by {}'.format(target_date.strftime('%d %b %Y')),
            'delta_label': delta_label
        })


    cur.close()
    conn.close()

    return render_template(
        'goals.html',
        goals=goals,
        accounts=accounts,
        total_goals=total_goals,
        on_track_count=on_track_count,
        at_risk_count=at_risk_count,
        completed_count=completed_count,
        current_page='goals'
    )



@goals_bp.route('/add', methods=['POST'])
def add_goal():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    today = date.today()

    name = request.form.get('name')
    goal_type = request.form.get('goal_type')
    target_amount = request.form.get('target_amount')
    linked_account_id = request.form.get('linked_account_id')
    target_date = request.form.get('target_date')

    # ----------------------------
    # Validation
    # ----------------------------
    if not name or not goal_type or not target_date:
        return redirect(url_for('goals.goals_page'))

    linked_required_types = ['savings', 'debt', 'investment']
    if goal_type in linked_required_types and not linked_account_id:
        return redirect(url_for('goals.goals_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ----------------------------
    # Set current and target for debt goal
    # ----------------------------
    if goal_type == 'debt' and linked_account_id:
        # Fetch current balance of linked account
        cur.execute("SELECT balance FROM accounts WHERE id = %s", (linked_account_id,))
        row = cur.fetchone()
        if row:
            current_amount = float(row['balance'])
            target_amount = current_amount  # target = current balance for debt
        else:
            current_amount = 0.0
            target_amount = 0.0
    else:
        current_amount = 0.0
        target_amount = float(target_amount)

    cur.execute("""
        INSERT INTO financial_goals (
            user_id,
            name,
            goal_type,
            target_amount,
            current_amount,
            start_date,
            target_date,
            linked_account_id,
            is_active,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
    """, (
        user_id,
        name,
        goal_type,
        target_amount,
        current_amount,
        today,
        target_date,
        linked_account_id if linked_account_id else None
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('goals.goals_page'))
