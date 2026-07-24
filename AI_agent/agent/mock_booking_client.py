from typing import Dict, Any, Optional, Tuple
import requests
from agent.config import BACKEND_BASE_URL, http_session


def _extract_booking_reference(res_data: Dict[str, Any]) -> Optional[str]:
    """
    The backend's mock booking endpoints might return the reference nested
    (Amadeus-style 'data.reference') or flat ('booking_reference') — the exact shape
    for each endpoint hasn't been confirmed against the real backend implementation,
    so this checks both rather than assuming one and silently returning None on a
    shape mismatch.
    """
    if not isinstance(res_data, dict):
        return None
    nested = res_data.get("data")
    if isinstance(nested, dict) and nested.get("reference"):
        return nested["reference"]
    return res_data.get("booking_reference")


def _split_traveler_name(traveler_name: str) -> Tuple[str, str]:
    """
    Splits a traveler's full name into (first, last) for the booking payload.

    Refuses to fabricate a fake identity (e.g. a hardcoded "Amir Khan") when the name
    is missing — that silently books under someone else's name, which is worse than
    failing loudly. Callers (graph.py's parse_disruption_node) are responsible for
    supplying at least a clearly-labeled placeholder if the real name isn't available
    yet; this function just refuses to proceed with nothing at all.
    """
    if not traveler_name or not traveler_name.strip():
        raise ValueError(
            "book_flight()/book_hotel() requires a non-empty traveler_name — "
            "refusing to book under a fabricated identity."
        )
    parts = traveler_name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else "Unknown"
    return first_name, last_name


def book_flight(
    flight_offer: Dict[str, Any],
    traveler_name: str,
    card_token: str,
    disruption_id: str
) -> Tuple[Optional[str], str]:
    """
    Calls the mock flight booking endpoint of the backend.
    POST /mock/v1/booking/flight-orders
    Returns a tuple of (booking_reference, status_string).
    Raises requests.RequestException on network or system-level outages.
    Raises ValueError if traveler_name is missing/blank.
    """
    url = f"{BACKEND_BASE_URL}/mock/v1/booking/flight-orders"

    first_name, last_name = _split_traveler_name(traveler_name)

    # §5.1: single traveler per booking (traveler count is not part of the §4.4 contract)
    travelers = [{
        "id": "1",
        "name": {
            "firstName": first_name,
            "lastName": last_name
        }
    }]

    payload = {
        "data": {
            "type": "flight-order",
            "flightOffers": [flight_offer],
            "travelers": travelers,
            "card_token": card_token
        }
    }

    # Stable, unique Idempotency Key derived from disruption ID (Issue 3)
    headers = {
        "Idempotency-Key": f"flight-booking:{disruption_id}"
    }

    print(f"Mock Booking Client: POST {url} for flight {flight_offer.get('id')} with card_token=REDACTED, Idempotency-Key={headers['Idempotency-Key']}")

    try:
        # Utilize resilient HTTP connection pool with idempotency header (Issue 2 & 3)
        response = http_session.post(url, json=payload, headers=headers, timeout=8)

        # Handle all successful 2xx statuses cleanly to prevent unpack crashes (Issue 1)
        if 200 <= response.status_code < 300:
            try:
                res_data = response.json()
            except ValueError as json_err:
                # A 2xx with an unparseable body is an anomaly worth surfacing loudly rather
                # than silently treating as either a clean success or a clean failure.
                raise requests.RequestException(
                    f"Flight booking returned {response.status_code} but the response body "
                    f"wasn't valid JSON: {json_err}"
                ) from json_err

            booking_ref = _extract_booking_reference(res_data)
            if not booking_ref:
                print(f"Mock Booking Client WARNING: Flight booking returned {response.status_code} "
                      f"but no booking reference could be parsed from the response body: {res_data}")
            else:
                print(f"Mock Booking Client: Flight booking success, reference={booking_ref}")
            return booking_ref, "success"
        elif response.status_code == 422:
            print("Mock Booking Client: Flight booking failed (422 - seat sold out)")
            return None, "sold_out"
        else:
            print(f"Mock Booking Client: Flight booking unexpected status={response.status_code}")
            # Raises requests.HTTPError, a requests.RequestException subclass, so it's caught below.
            response.raise_for_status()
    except requests.RequestException as e:
        print(f"Mock Booking Client: Flight booking request failed: {e}")
        raise e


def book_hotel(
    hotel_id: str,
    hotel_name: str,
    user_id: str,
    check_in: str,
    check_out: str,
    card_token: str,
    disruption_id: str
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

    # Stable, unique Idempotency Key derived from disruption ID (Issue 3)
    headers = {
        "Idempotency-Key": f"hotel-booking:{disruption_id}"
    }

    print(f"Mock Booking Client: POST {url} for hotel {hotel_id} with card_token=REDACTED, Idempotency-Key={headers['Idempotency-Key']}")

    try:
        # Utilize resilient HTTP connection pool with idempotency header (Issue 2 & 3)
        response = http_session.post(url, json=payload, headers=headers, timeout=8)

        # Handle all successful 2xx statuses cleanly to prevent unpack crashes (Issue 1)
        if 200 <= response.status_code < 300:
            try:
                res_data = response.json()
            except ValueError as json_err:
                raise requests.RequestException(
                    f"Hotel booking returned {response.status_code} but the response body "
                    f"wasn't valid JSON: {json_err}"
                ) from json_err

            booking_ref = _extract_booking_reference(res_data)
            if not booking_ref:
                print(f"Mock Booking Client WARNING: Hotel booking returned {response.status_code} "
                      f"but no booking reference could be parsed from the response body: {res_data}")
            else:
                print(f"Mock Booking Client: Hotel booking success, reference={booking_ref}")
            return booking_ref, "success"
        elif response.status_code == 422:
            print("Mock Booking Client: Hotel booking failed (422)")
            return None, "sold_out"
        else:
            print(f"Mock Booking Client: Hotel booking unexpected status={response.status_code}")
            # Raises requests.HTTPError, a requests.RequestException subclass, so it's caught below.
            response.raise_for_status()
    except requests.RequestException as e:
        print(f"Mock Booking Client: Hotel booking request failed: {e}")
        raise e