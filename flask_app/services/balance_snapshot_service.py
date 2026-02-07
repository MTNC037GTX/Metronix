from datetime import datetime
from calendar import monthrange
from db import get_db_connection

ASSET_TYPES = ['cash','ewallet','savings','investment','real estate','property','other assets']
LIABILITY_TYPES = ['short-term loan','credit','long-term loan']

def create_monthly_snapshot(user_id, year, month):
    """
    Create a snapshot for the given month and user if it does not exist.
    Includes final balances for that month.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    last_day = monthrange(year, month)[1]
    snapshot_date = datetime(year, month, last_day, 23, 59, 59)

    # Idempotency check: skip if snapshot already exists
    cur.execute("""
        SELECT 1 FROM balance_snapshots
        WHERE user_id = %s
          AND EXTRACT(YEAR FROM snapshot_date) = %s
          AND EXTRACT(MONTH FROM snapshot_date) = %s
        LIMIT 1
    """, (user_id, year, month))

    if cur.fetchone():
        cur.close()
        conn.close()
        return  # Already exists

    # Calculate total balances as of snapshot_date
    cur.execute("""
        SELECT a.type, a.balance
        FROM accounts a
        WHERE a.user_id = %s
    """, (user_id,))

    total_assets = 0
    total_liabilities = 0
    net_worth = 0

    rows = cur.fetchall()
    for r in rows:
        acc_type = r['type']
        acc_balance = float(r['balance'])
        net_worth += acc_balance

        if acc_type in ASSET_TYPES:
            total_assets += acc_balance
        elif acc_type in LIABILITY_TYPES:
            total_liabilities += acc_balance


    # Insert snapshot
    cur.execute("""
        INSERT INTO balance_snapshots
            (user_id, snapshot_date, total_assets, total_liabilities, net_worth)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, snapshot_date, total_assets, total_liabilities, net_worth))

    conn.commit()
    cur.close()
    conn.close()
