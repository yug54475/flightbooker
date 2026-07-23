import requests
from typing import Dict, Any, Optional, List
from agent.config import BACKEND_BASE_URL

def book_flight(
    flight_offer: Dict[str, Any], 
    traveler_name: str, 
    card_token: str
) -> Optional[str]:
    """
    Calls the mock flight booking endpoint of the backend.
    POST /mock/v1/booking/flight-orders
    """
    url = f"{BACKEND_BASE_URL}/mock/v1/booking/flight-orders"
    
    # Split name into first/last for the traveler structure
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
    
    # Redact card_token in print/log per security rules
    print(f"Mock Booking Client: POST {url} for flight {flight_offer.get('id')} with card_token=REDACTED")
    
    try:
        response = requests.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            booking_ref = res_data.get("data", {}).get("reference")
            print(f"Mock Booking Client: Flight booking success, reference={booking_ref}")
            return booking_ref
        elif response.status_code == 422:
            print("Mock Booking Client: Flight booking failed (422 - seat sold out)")
            return None
        else:
            print(f"Mock Booking Client: Flight booking unexpected status={response.status_code}")
    except Exception as e:
        print(f"Mock Booking Client: Flight booking error: {e}")
        
    return None

def book_hotel(
    hotel_id: str,
    hotel_name: str,
    user_id: str,
    check_in: str,
    check_out: str,
    card_token: str
) -> Optional[str]:
    """
    Calls the mock hotel booking endpoint of the backend.
    POST /mock/v1/booking/hotel-orders
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
        response = requests.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            booking_ref = res_data.get("booking_reference")
            print(f"Mock Booking Client: Hotel booking success, reference={booking_ref}")
            return booking_ref
        elif response.status_code == 422:
            print("Mock Booking Client: Hotel booking failed (422)")
            return None
        else:
            print(f"Mock Booking Client: Hotel booking unexpected status={response.status_code}")
    except Exception as e:
        print(f"Mock Booking Client: Hotel booking error: {e}")
        
    return None
