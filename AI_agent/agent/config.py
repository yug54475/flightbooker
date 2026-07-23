import os
from dotenv import load_dotenv

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
