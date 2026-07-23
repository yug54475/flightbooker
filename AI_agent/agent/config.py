import os
import psycopg2.pool
import requests
from dotenv import load_dotenv
from contextlib import contextmanager
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# Load .env if present
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgres://flightbooker:flightbooker@localhost:5432/flightbooker?sslmode=disable"
)
BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL", 
    "http://localhost:8000"
)
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID", "")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET", "")

# Global thread-safe set to register disruptions that timed out
# Ensures background threads immediately skip any actual bookings (Issue 5)
cancelled_disruption_ids = set()

# Thread-safe PostgreSQL connection pool
_db_pool = None

def init_db_pool():
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=15,
                dsn=DATABASE_URL
            )
            print("PostgreSQL ThreadedConnectionPool initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize PostgreSQL connection pool: {e}")

@contextmanager
def get_db_conn():
    """Context manager to lease and safely release a database connection from the pool."""
    global _db_pool
    if _db_pool is None:
        init_db_pool()
        
    conn = None
    if _db_pool:
        conn = _db_pool.getconn()
    else:
        # Fallback to direct connection if pool couldn't be initialized
        conn = psycopg2.connect(DATABASE_URL)
        
    try:
        yield conn
    finally:
        if _db_pool and conn:
            _db_pool.putconn(conn)
        elif conn:
            conn.close()

def close_db_pool():
    """Closes all connections in the pool on shutdown."""
    global _db_pool
    if _db_pool:
        _db_pool.closeall()
        print("PostgreSQL ThreadedConnectionPool closed successfully.")


# ==========================================
# Resilient HTTP Client Session
# ==========================================

def _create_resilient_session() -> requests.Session:
    """Creates a requests.Session configured with automatic retries and exponential backoff."""
    session = requests.Session()
    # Retry up to 2 times on transient server issues (502, 503, 504) or rate limits (429)
    retries = Retry(
        total=2,
        backoff_factor=1,  # Wait 1s, then 2s
        status_forcelist=[429, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Globally shared resilient session
http_session = _create_resilient_session()
