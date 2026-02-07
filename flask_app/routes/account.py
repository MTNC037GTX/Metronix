from flask import Blueprint, render_template, session, redirect, url_for, request
from db import get_db_connection
from psycopg2.extras import RealDictCursor
from collections import defaultdict
from datetime import datetime, timedelta

account_bp = Blueprint('account', __name__, template_folder='../templates')

ICON_MAP = {
    'cash': {
        'icon': 'fas fa-wallet',
        'bg_color': 'bg-income/20',
        'icon_color': 'text-income'
    },
    'credit': {
        'icon': 'fas fa-credit-card',
        'bg_color': 'bg-red-400/20',
        'icon_color': 'text-red-400'
    },
    'ewallet': {
        'icon': 'fa-solid fa-mobile-screen-button',
        'bg_color': 'bg-purple-500/20',
        'icon_color': 'text-purple-500'
    },
    'savings': {
        'icon': 'fas fa-piggy-bank',
        'bg_color': 'bg-teal-500/20',
        'icon_color': 'text-teal-500'
    },
    'investment': {
        'icon': 'fas fa-chart-line',
        'bg_color': 'bg-amber-500/20',
        'icon_color': 'text-amber-500'
    },
    'real estate': {
        'icon': 'fas fa-building',
        'bg_color': 'bg-indigo-500/20',
        'icon_color': 'text-indigo-500'
    },
    'property': {
        'icon': 'fas fa-coins',
        'bg_color': 'bg-cyan-500/20',
        'icon_color': 'text-cyan-500'
    },
    'other assets': {
        'icon': 'fas fa-box-archive',
        'bg_color': 'bg-slate-500/20',
        'icon_color': 'text-slate-500'
    },
    'short-term loan': {
        'icon': 'fas fa-hand-holding-dollar',
        'bg_color': 'bg-red-500/20',
        'icon_color': 'text-red-500'
    },
    'long-term loan': {
        'icon': 'fas fa-file-invoice-dollar',
        'bg_color': 'bg-rose-600/20',
        'icon_color': 'text-rose-600'
    },
}

LIABILITIES = ['credit', 'short-term loan', 'long-term loan']

@account_bp.route('/')
def account_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id, name, type, opening_balance, balance, is_active, created_at
        FROM accounts
        WHERE user_id = %s
        ORDER BY created_at ASC
    """, (user_id,))
    accounts = cur.fetchall()

    for acct in accounts:
        key = acct['type'].lower()
        mapping = ICON_MAP.get(key, {})
        acct['icon'] = mapping.get('icon', 'fas fa-exchange-alt')
        acct['bg_color'] = mapping.get('bg_color', 'bg-gray-500/20')
        acct['icon_color'] = mapping.get('icon_color', 'text-gray-500')

        cur.execute("""
            SELECT
                id,
                description,
                amount,
                type,
                account_id,
                transfer_account_id,
                created_at,
                CASE
                    WHEN type = 'transfer' AND account_id = %s THEN 'out'
                    WHEN type = 'transfer' AND transfer_account_id = %s THEN 'in'
                    ELSE type
                END AS direction
            FROM transactions
            WHERE user_id = %s
              AND (
                    account_id = %s
                 OR transfer_account_id = %s
              )
            ORDER BY created_at DESC
            LIMIT 5
        """, (
            acct['id'],
            acct['id'],
            user_id,
            acct['id'],
            acct['id']
        ))

        txns = cur.fetchall()

        for txn in txns:
            txn['created_at'] = txn['created_at'].strftime('%Y-%m-%d %H:%M')

        acct['transactions'] = txns

    cur.close()
    conn.close()

    accounts_by_type = defaultdict(list)
    for acct in accounts:
        type_title = 'E-wallet' if acct['type'].lower() == 'ewallet' else acct['type'].title()
        accounts_by_type[type_title].append(acct)

    total_accounts = len(accounts)
    # Only sum balances for active accounts that are NOT liabilities
    LIQUID_ASSETS = {
        'cash',
        'savings',
        'ewallet',
        'investment'
    }

    total_active_balance = sum(
        acct['balance']
        for acct in accounts
        if acct['is_active']
        and acct['type'].lower() in LIQUID_ASSETS
    )


    accounts_this_month = sum(
        1 for acct in accounts
        if acct['created_at'].month == datetime.now().month
        and acct['created_at'].year == datetime.now().year
    )

    first_day_of_current_month = datetime(datetime.now().year, datetime.now().month, 1)
    prev_month_last_day = first_day_of_current_month - timedelta(days=1)

    prev_month_balance = sum(
        acct['balance'] for acct in accounts
        if acct['is_active'] and acct['created_at'] <= prev_month_last_day
    )

    return render_template(
        'account.html',
        accounts_by_type=accounts_by_type,
        total_accounts=total_accounts,
        total_active_balance=total_active_balance,
        prev_month_balance=prev_month_balance,
        accounts_this_month=accounts_this_month,
        current_page='account'
    )


# Add new account
@account_bp.route('/add', methods=['POST'])
def add_account():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    name = request.form.get('name')
    type_ = request.form.get('type')
    opening_balance = request.form.get('opening_balance', 0)

    try:
        opening_balance = float(opening_balance)
    except (TypeError, ValueError):
        opening_balance = 0

    liability_types = {
        'credit',
        'short-term loan',
        'long-term loan'
    }

    if type_ in liability_types and opening_balance > 0:
        opening_balance = -opening_balance

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO accounts (
            user_id,
            name,
            type,
            opening_balance,
            balance,
            is_active,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
    """, (
        user_id,
        name,
        type_,
        opening_balance,
        opening_balance
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('account.account_dashboard'))
