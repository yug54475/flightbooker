import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from agent.config import AMADEUS_CLIENT_ID, AMADEUS_CLIENT_SECRET, http_session

# Global cached token
_cached_token: Optional[str] = None
_token_expires_at: float = 0.0

def get_amadeus_token() -> Optional[str]:
    """Retrieves or refreshes the cached Amadeus OAuth2 Access Token."""
    global _cached_token, _token_expires_at
    
    # If we have no credentials, return None to trigger mock fallback
    if not AMADEUS_CLIENT_ID or not AMADEUS_CLIENT_SECRET:
        return None
        
    # Check if cached token is still valid (with a 30s buffer)
    if _cached_token and time.time() < _token_expires_at - 30:
        return _cached_token
        
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    
    try:
        response = http_session.post(url, data=data, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            _cached_token = res_data.get("access_token")
            expires_in = res_data.get("expires_in", 1800)
            _token_expires_at = time.time() + expires_in
            return _cached_token
    except Exception as e:
        print(f"Failed to generate Amadeus token: {e}")
        
    return None

def search_flight_alternatives(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str
) -> List[Dict[str, Any]]:
    """
    Searches flight alternatives. Hits real Amadeus API if credentials are provided,
    otherwise falls back to generating a realistic, high-fidelity mock flightOffers array.
    """
    token = get_amadeus_token()
    
    if token:
        # Map cabin_class to Amadeus expectations (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
        cabin_mapping = {
            "economy": "ECONOMY",
            "premium_economy": "PREMIUM_ECONOMY",
            "business": "BUSINESS",
            "first": "FIRST"
        }
        amadeus_cabin = cabin_mapping.get(cabin_class.lower(), "ECONOMY")
        
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": 1,
            "travelClass": amadeus_cabin,
            "nonStop": "true"  # Prefer direct flights for business travel rebookings (§2.4)
        }
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            response = http_session.get(url, params=params, headers=headers, timeout=8)
            if response.status_code == 200:
                results = response.json().get("data", [])
                for r in results:
                    r["search_source"] = "amadeus_real"
                return results
            else:
                print(f"Amadeus Flight search API returned status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Amadeus Flight search failed: {e}")

    # High-fidelity mock fallback
    print(f"Amadeus Client: Using realistic fallback flight offers for {origin}->{destination} on {departure_date} ({cabin_class})")
    results = _generate_mock_flight_offers(origin, destination, departure_date, cabin_class)
    for r in results:
        r["search_source"] = "mock_fallback"
    return results


def _generate_mock_flight_offers(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str
) -> List[Dict[str, Any]]:
    """Generates a realistic list of flight offer objects following the Amadeus API schema."""
    offers = []
    cabin_class = cabin_class.lower()
    
    # 1. Option 1: The winning candidate (BA456/similar) - preserves cabin class, slightly higher price (+$90)
    # Let's formulate departure/arrival timestamps to depart next day morning
    dep_dt = datetime.fromisoformat(departure_date)
    next_day_str = (dep_dt + timedelta(days=1)).date().isoformat()
    base_dep = datetime.fromisoformat(f"{next_day_str}T01:00:00")
    base_arr = datetime.fromisoformat(f"{next_day_str}T09:00:00")
    
    offers.append({
        "type": "flight-offer",
        "id": "mock-offer-01",
        "source": "GDS",
        "instantTicketingRequired": False,
        "nonHomogeneous": False,
        "oneWay": False,
        "lastTicketingDate": departure_date,
        "numberOfBookableSeats": 7,
        "itineraries": [{
            "duration": "PT8H0M",
            "segments": [{
                "id": "1",
                "numberOfStops": 0,
                "blacklistedInEU": False,
                "departure": {
                    "iataCode": origin,
                    "terminal": "4",
                    "at": base_dep.isoformat()
                },
                "arrival": {
                    "iataCode": destination,
                    "terminal": "5",
                    "at": base_arr.isoformat()
                },
                "carrierCode": "BA",
                "number": "456",
                "aircraft": {"code": "777"},
                "operating": {"carrierCode": "BA"},
                "duration": "PT8H0M"
            }]
        }],
        "price": {
            "currency": "USD",
            "total": "4910.00",
            "base": "4000.00",
            "fees": [{"amount": "0.00", "type": "SUPPLIER"}],
            "grandTotal": "4910.00"
        },
        "travelerPricings": [{
            "fareDetailsBySegment": [{
                "segmentId": "1",
                "cabin": cabin_class.upper()
            }]
        }]
    })

    # 2. Option 2: Downgrade option (e.g. Economy class, cheaper)
    base_dep_2 = datetime.fromisoformat(f"{next_day_str}T05:15:00")
    base_arr_2 = base_dep_2 + timedelta(hours=8)
    
    offers.append({
        "type": "flight-offer",
        "id": "mock-offer-02",
        "source": "GDS",
        "instantTicketingRequired": False,
        "nonHomogeneous": False,
        "oneWay": False,
        "lastTicketingDate": departure_date,
        "numberOfBookableSeats": 9,
        "itineraries": [{
            "duration": "PT8H0M",
            "segments": [{
                "id": "1",
                "numberOfStops": 0,
                "blacklistedInEU": False,
                "departure": {
                    "iataCode": origin,
                    "at": base_dep_2.isoformat()
                },
                "arrival": {
                    "iataCode": destination,
                    "at": base_arr_2.isoformat()
                },
                "carrierCode": "BA",
                "number": "458",
                "aircraft": {"code": "777"},
                "operating": {"carrierCode": "BA"},
                "duration": "PT8H0M"
            }]
        }],
        "price": {
            "currency": "USD",
            "total": "1280.00",
            "base": "1000.00",
            "fees": [{"amount": "0.00", "type": "SUPPLIER"}],
            "grandTotal": "1280.00"
        },
        "travelerPricings": [{
            "fareDetailsBySegment": [{
                "segmentId": "1",
                "cabin": "ECONOMY"
            }]
        }]
    })

    # 3. Option 3: Alternate routing or slightly different time
    base_dep_3 = datetime.fromisoformat(f"{next_day_str}T10:45:00")
    base_arr_3 = base_dep_3 + timedelta(hours=9)
    
    offers.append({
        "type": "flight-offer",
        "id": "mock-offer-03",
        "source": "GDS",
        "instantTicketingRequired": False,
        "nonHomogeneous": False,
        "oneWay": False,
        "lastTicketingDate": departure_date,
        "numberOfBookableSeats": 2,
        "itineraries": [{
            "duration": "PT9H0M",
            "segments": [{
                "id": "1",
                "numberOfStops": 0,
                "blacklistedInEU": False,
                "departure": {
                    "iataCode": origin,
                    "at": base_dep_3.isoformat()
                },
                "arrival": {
                    "iataCode": destination,
                    "at": base_arr_3.isoformat()
                },
                "carrierCode": "AF",
                "number": "009",
                "aircraft": {"code": "350"},
                "operating": {"carrierCode": "AF"},
                "duration": "PT9H0M"
            }]
        }],
        "price": {
            "currency": "USD",
            "total": "5120.00",
            "base": "4500.00",
            "fees": [{"amount": "0.00", "type": "SUPPLIER"}],
            "grandTotal": "5120.00"
        },
        "travelerPricings": [{
            "fareDetailsBySegment": [{
                "segmentId": "1",
                "cabin": cabin_class.upper()
            }]
        }]
    })

    return offers


def search_hotel_alternatives(
    city_code: str,
    check_in: str,
    check_out: str
) -> List[Dict[str, Any]]:
    """
    Searches hotel alternatives. Hits real Amadeus Hotel Search API if credentials are provided,
    otherwise falls back to generating a realistic, high-fidelity mock hotelOffers list.
    """
    token = get_amadeus_token()
    
    if token:
        # Step 1: Query locations/hotels/by-city to find hotel IDs in the destination city
        by_city_url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city"
        by_city_params = {
            "cityCode": city_code,
            "radius": 5,
            "radiusUnit": "KM",
            "hotelSource": "ALL"
        }
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            city_resp = http_session.get(by_city_url, params=by_city_params, headers=headers, timeout=8)
            if city_resp.status_code == 200:
                hotels_data = city_resp.json().get("data", [])
                hotel_ids = [h["hotelId"] for h in hotels_data[:3]] # Query up to 3 hotels
                
                if hotel_ids:
                    # Step 2: Query shopping/hotel-offers for actual pricing
                    offers_url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
                    offers_params = {
                        "hotelIds": ",".join(hotel_ids),
                        "adults": 1,
                        "checkInDate": check_in,
                        "checkOutDate": check_out,
                        "roomQuantity": 1
                    }
                    offers_resp = http_session.get(offers_url, params=offers_params, headers=headers, timeout=8)
                    
                    if offers_resp.status_code == 200:
                        raw_offers = offers_resp.json().get("data", [])
                        parsed_offers = []
                        for h_off in raw_offers:
                            h_id = h_off.get("hotel", {}).get("hotelId", "unknown")
                            h_name = h_off.get("hotel", {}).get("name", "Boutique Hotel")
                            offers_list = h_off.get("offers", [])
                            if offers_list:
                                rate = offers_list[0].get("price", {}).get("total", "150.00")
                                parsed_offers.append({
                                    "hotel_id": h_id,
                                    "hotel_name": h_name,
                                    "price": float(rate),
                                    "check_in": check_in,
                                    "check_out": check_out,
                                    "search_source": "amadeus_real"
                                })
                        if parsed_offers:
                            return parsed_offers
            else:
                print(f"Amadeus Hotel search API returned status {city_resp.status_code}: {city_resp.text}")
        except Exception as e:
            print(f"Amadeus Hotel search failed: {e}")

    # Fallback to high-fidelity mock list of hotel offers
    print(f"Amadeus Client: Returning fallback hotel search results for city {city_code} ({check_in} to {check_out})")
    
    # Map the city code to seeded hotel name for high-fidelity matching
    fallback_hotel_name = "The Cadogan, London"
    if city_code == "PAR":
        fallback_hotel_name = "Le Marais Boutique, Paris"
    elif city_code == "TYO":
        fallback_hotel_name = "Park Hotel Tokyo"
        
    return [
        {
            "hotel_id": f"AMAD-HTL-{city_code}-01",
            "hotel_name": fallback_hotel_name,
            "price": 350.00,
            "check_in": check_in,
            "check_out": check_out,
            "search_source": "mock_fallback"
        },
        {
            "hotel_id": f"AMAD-HTL-{city_code}-02",
            "hotel_name": f"Park Hotel, {city_code}",
            "price": 280.00,
            "check_in": check_in,
            "check_out": check_out,
            "search_source": "mock_fallback"
        }
    ]
