import psycopg2
from psycopg2.extras import RealDictCursor

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'metronix',
    'user': 'metronix_user',
    'password': 'abc123456'
}

def get_db_connection():
    """
    Returns a PostgreSQL database connection.
    Uses RealDictCursor to fetch results as dictionaries.
    """
    conn = psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        cursor_factory=RealDictCursor
    )
    return conn
