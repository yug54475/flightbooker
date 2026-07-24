import os
import requests
from dotenv import load_dotenv
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# Load .env if present
load_dotenv()

BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL", 
    "http://localhost:8000"
)
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID", "")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET", "")

# Thread-safe cancellation token class to stop background threads on timeout
class CancellationToken:
    def __init__(self):
        self.is_cancelled = False

# Global thread-safe set to register disruptions that timed out
cancelled_disruption_ids = set()


# ==========================================
# Resilient HTTP Client Session
# ==========================================

def _create_resilient_session() -> requests.Session:
    """Creates a requests.Session configured with automatic retries and exponential backoff."""
    session = requests.Session()
    # Retry up to 2 times on transient server issues (502, 503, 504) or rate limits (429)
    # Explicitly include POST calls (allowed_methods) to resiliently cover mock bookings
    retries = Retry(
        total=2,
        backoff_factor=1,  # Wait 1s, then 2s
        status_forcelist=[429, 502, 503, 504],
        allowed_methods=frozenset(['GET', 'POST']),
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Globally shared resilient session
http_session = _create_resilient_session()
