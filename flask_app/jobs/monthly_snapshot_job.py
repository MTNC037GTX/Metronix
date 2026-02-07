from datetime import datetime
from calendar import monthrange
from db import get_db_connection
from services.balance_snapshot_service import create_monthly_snapshot

def run_monthly_snapshot():
    today = datetime.now()

    # Last completed month
    if today.month == 1:
        last_month_year = today.year - 1
        last_month = 12
    else:
        last_month_year = today.year
        last_month = today.month - 1

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT user_id FROM accounts")
    
    # Fetch column safely
    try:
        users = [row['user_id'] for row in cur.fetchall()]  # for dict-like cursor
    except TypeError:
        users = [row[0] for row in cur.fetchall()]         # for tuple cursor

    cur.close()
    conn.close()

    for user_id in users:
        create_monthly_snapshot(user_id, last_month_year, last_month)
