from typing import Dict, Any, Optional, Tuple
import requests
from agent.config import BACKEND_BASE_URL, http_session

def book_flight(
    flight_offer: Dict[str, Any], 
    traveler_name: str, 
    card_token: str
) -> Tuple[Optional[str], str]:
    """
    Calls the mock flight booking endpoint of the backend.
    POST /mock/v1/booking/flight-orders
    Returns a tuple of (booking_reference, status_string).
    Raises requests.RequestException on network or system-level outages.
    """
    url = f"{BACKEND_BASE_URL}/mock/v1/booking/flight-orders"
    
    parts = traveler_name.split(" ", 1)
    first_name = parts[0] if len(parts) > 0 else "Amir"
    last_name = parts[1] if len(parts) > 1 else "Khan"
    
    payload = {
        "data": {
            "type": "flight-order",
            "flightOffers": [flight_offer],
            "travelers": [
                {
                    "id": "1",
                    "name": {
                        "firstName": first_name,
                        "lastName": last_name
                    }
                }
            ],
            "card_token": card_token
        }
    }
    
    print(f"Mock Booking Client: POST {url} for flight {flight_offer.get('id')} with card_token=REDACTED")
    
    try:
        # Utilize resilient HTTP connection pool (Issue 2)
        response = http_session.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            booking_ref = res_data.get("data", {}).get("reference")
            print(f"Mock Booking Client: Flight booking success, reference={booking_ref}")
            return booking_ref, "success"
        elif response.status_code == 422:
            print("Mock Booking Client: Flight booking failed (422 - seat sold out)")
            return None, "sold_out"
        else:
            print(f"Mock Booking Client: Flight booking unexpected status={response.status_code}")
            response.raise_for_status()
    except requests.RequestException as e:
        print(f"Mock Booking Client: Flight booking network/system error: {e}")
        raise e

def book_hotel(
    hotel_id: str,
    hotel_name: str,
    user_id: str,
    check_in: str,
    check_out: str,
    card_token: str
) -> Tuple[Optional[str], str]:
    """
    Calls the mock hotel booking endpoint of the backend.
    POST /mock/v1/booking/hotel-orders
    Returns a tuple of (booking_reference, status_string).
    Raises requests.RequestException on network or system-level outages.
    """
    url = f"{BACKEND_BASE_URL}/mock/v1/booking/hotel-orders"
    
    payload = {
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "user_id": user_id,
        "check_in": check_in,
        "check_out": check_out,
        "card_token": card_token
    }
    
    print(f"Mock Booking Client: POST {url} for hotel {hotel_id} with card_token=REDACTED")
    
    try:
        # Utilize resilient HTTP connection pool (Issue 2)
        response = http_session.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            booking_ref = res_data.get("booking_reference")
            print(f"Mock Booking Client: Hotel booking success, reference={booking_ref}")
            return booking_ref, "success"
        elif response.status_code == 422:
            print("Mock Booking Client: Hotel booking failed (422)")
            return None, "sold_out"
        else:
            print(f"Mock Booking Client: Hotel booking unexpected status={response.status_code}")
            response.raise_for_status()
    except requests.RequestException as e:
        print(f"Mock Booking Client: Hotel booking network/system error: {e}")
        raise e
