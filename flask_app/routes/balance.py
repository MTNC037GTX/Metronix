from flask import Blueprint, render_template, session, redirect, url_for, request
from db import get_db_connection
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dateutil.relativedelta import relativedelta

balance_bp = Blueprint('balance', __name__, url_prefix='/balance')


@balance_bp.route('/', methods=['GET'])
def balance_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT name, type, balance, updated_at
        FROM accounts
        WHERE user_id = %s
        ORDER BY name
    """, (user_id,))

    accounts = cur.fetchall()

    # Define categories
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

    # Organize accounts per category
    assets = []
    liabilities = []

    total_assets = 0
    total_liabilities = 0

    for cat, types in ASSET_CATEGORIES.items():
        cat_accounts = [{'name': acc['name'], 'amount': acc['balance']} 
                        for acc in accounts if acc['type'] in types]
        if cat_accounts:
            assets.append({'category': cat, 'accounts': cat_accounts})
            total_assets += sum(acc['amount'] or 0 for acc in cat_accounts)

    for cat, types in LIABILITY_CATEGORIES.items():
        cat_accounts = [{'name': acc['name'], 'amount': acc['balance']} 
                        for acc in accounts if acc['type'] in types]
        if cat_accounts:
            liabilities.append({'category': cat, 'accounts': cat_accounts})
            total_liabilities += sum(acc['amount'] or 0 for acc in cat_accounts)

    net_worth = total_assets + total_liabilities
    
    
    # --- Line Chart Data ---
    selected_year = request.args.get('year', datetime.now().year, type=int)

    current_year = datetime.now().year
    current_month = datetime.now().month

    balance_history = []

    asset_types = sum(ASSET_CATEGORIES.values(), [])
    liability_types = sum(LIABILITY_CATEGORIES.values(), [])

    # Cache current month live data once (used for future months)
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type = ANY(%s) THEN balance ELSE 0 END), 0) AS total_assets,
            COALESCE(SUM(CASE WHEN type = ANY(%s) THEN balance ELSE 0 END), 0) AS total_liabilities,
            COALESCE(SUM(balance), 0) AS net_worth
        FROM accounts
        WHERE user_id = %s
    """, (asset_types, liability_types, user_id))
    current_row = cur.fetchone()

    current_assets = current_row['total_assets']
    current_liabilities = abs(current_row['total_liabilities'])   # normalize to positive
    current_net_worth = current_row['net_worth']

    for month in range(1, 13):

        # CURRENT MONTH OR FUTURE MONTHS -> LIVE DATA
        if selected_year > current_year or \
        (selected_year == current_year and month >= current_month):

            total_assets = current_assets
            total_liabilities = current_liabilities
            net_worth = current_net_worth

        # PAST MONTHS -> SNAPSHOT DATA
        else:
            cur.execute("""
                SELECT total_assets, total_liabilities, net_worth
                FROM balance_snapshots
                WHERE user_id = %s
                AND EXTRACT(YEAR FROM snapshot_date) = %s
                AND EXTRACT(MONTH FROM snapshot_date) = %s
            """, (user_id, selected_year, month))
            row = cur.fetchone()

            if row:
                total_assets = row['total_assets']
                total_liabilities = abs(row['total_liabilities'])  # normalize
                net_worth = row['net_worth']
            else:
                total_assets = 0
                total_liabilities = 0
                net_worth = 0

        balance_history.append({
            'month': datetime(selected_year, month, 1).strftime('%b'),
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'net_worth': net_worth
        })

    # --- Available years for dropdown ---
    cur.execute("""
        SELECT DISTINCT EXTRACT(YEAR FROM snapshot_date)::int AS year
        FROM balance_snapshots
        WHERE user_id = %s
        ORDER BY year DESC
    """, (user_id,))
    years = [r['year'] for r in cur.fetchall()]

    if selected_year not in years:
        years.insert(0, selected_year)
        
        
    # --- Pie Chart Data (Asset & Liability Breakdown) ---

    asset_pie_data = []
    liability_pie_data = []

    for acc in accounts:
        amount = acc['balance'] or 0

        # Assets (positive values only)
        if acc['type'] in sum(ASSET_CATEGORIES.values(), []):
            if amount > 0:
                asset_pie_data.append({
                    'name': acc['name'],
                    'value': amount
                })

        # Liabilities (store as positive for chart clarity)
        elif acc['type'] in sum(LIABILITY_CATEGORIES.values(), []):
            if amount != 0:
                liability_pie_data.append({
                    'name': acc['name'],
                    'value': abs(amount)
                })


    cur.close()
    conn.close()

    return render_template(
        'balance.html',
        assets=assets,
        liabilities=liabilities,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        balance_history=balance_history,
        asset_pie_data=asset_pie_data,
        liability_pie_data=liability_pie_data,
        selected_year=selected_year,
        years=years,
        current_page='balance'
    )

