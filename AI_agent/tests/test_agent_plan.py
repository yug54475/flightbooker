import copy
import pytest
import requests
from unittest import mock
from fastapi.testclient import TestClient

from agent.main import app
from agent.config import cancelled_disruption_ids

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_caches_and_locks():
    """Autouse fixture to reset the FastAPI timeout cancellation set between tests."""
    cancelled_disruption_ids.clear()

SAMPLE_REQUEST_PAYLOAD = {
  "disruption_event": {
    "id": "de-0001",
    "type": "cancelled",
    "delay_minutes": None,
    "flight_segment": {
      "id": "fs-0001",
      "flight_number": "BA112",
      "origin": "JFK",
      "destination": "LHR",
      "departure_time": "2026-07-28T21:10:00Z",
      "arrival_time": "2026-07-29T09:05:00Z",
      "cabin_class": "business",
      "loyalty_program": "BA Executive Club",
      "original_price": 4820.00,
      "booking_reference": "QF7X2K"
    },
    "user": {
      "id": "9d3f1b2a-2222-4a3e-8b1a-111111111111",
      "card_tier": "premium",
      "card_token": "tok_demo_premium_001",
      "loyalty_program": "BA Executive Club",
      "name": "Amir Khan",
      "max_price_delta": 150.00,
      "allow_cabin_downgrade": False
    }
  }
}

@mock.patch("agent.graph.book_flight")
def test_agent_plan_auto_approved_path(mock_book):
    mock_book.return_value = ("MOCK-BK-9182", "success")
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["confidence_score"] > 0.9
    assert res_data["proposed_flight_segment"] is not None
    
    proposed_seg = res_data["proposed_flight_segment"]
    assert proposed_seg["flight_number"] == "BA456"
    assert proposed_seg["origin"] == "JFK"
    assert proposed_seg["destination"] == "LHR"
    assert proposed_seg["booking_reference"] == "MOCK-BK-9182"
    assert "Amadeus real API" not in res_data["reasoning_steps"][0]["output"]
    assert "synthetic fallback" in res_data["reasoning_steps"][0]["output"]

@mock.patch("agent.graph.book_flight")
def test_agent_plan_pending_approval_path(mock_book):
    payload = copy.deepcopy(SAMPLE_REQUEST_PAYLOAD)
    payload["disruption_event"]["user"]["max_price_delta"] = 50.00  # Lower limit forces pending approval
    
    response = client.post("/agent/plan", json=payload)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["confidence_score"] <= 0.9
    assert res_data["proposed_flight_segment"] is not None
    
    proposed_seg = res_data["proposed_flight_segment"]
    assert proposed_seg["booking_reference"] is None
    mock_book.assert_not_called()

@mock.patch("agent.graph.search_flight_alternatives")
def test_agent_plan_no_alternatives_found(mock_search):
    mock_search.return_value = []
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["confidence_score"] == 0.0
    assert res_data["proposed_flight_segment"] is None
    assert res_data["proposed_hotel_booking"] is None

@mock.patch("agent.graph.book_flight")
@mock.patch("agent.graph.search_flight_alternatives")
def test_agent_plan_connecting_itinerary(mock_search, mock_book):
    mock_book.return_value = ("MOCK-BK-9182", "success")
    
    mock_search.return_value = [
        {
            "type": "flight-offer",
            "id": "mock-offer-connect",
            "source": "GDS",
            "itineraries": [{
                "duration": "PT11H0M",
                "segments": [
                    {
                        "departure": {"iataCode": "JFK", "at": "2026-07-29T01:00:00"},
                        "arrival": {"iataCode": "CDG", "at": "2026-07-29T05:00:00"},
                        "carrierCode": "BA", "number": "112"
                    },
                    {
                        "departure": {"iataCode": "CDG", "at": "2026-07-29T07:00:00"},
                        "arrival": {"iataCode": "LHR", "at": "2026-07-29T09:00:00"},
                        "carrierCode": "BA", "number": "304"
                    }
                ]
            }],
            "price": {"currency": "USD", "total": "4910.00"},
            "travelerPricings": [{"fareDetailsBySegment": [{"segmentId": "1", "cabin": "BUSINESS"}]}]
        }
    ]
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    res_data = response.json()
    
    proposed_seg = res_data["proposed_flight_segment"]
    assert proposed_seg is not None
    assert proposed_seg["flight_number"] == "BA112 / BA304"
    assert proposed_seg["origin"] == "JFK"
    assert proposed_seg["destination"] == "LHR"

@mock.patch("agent.graph.book_hotel")
@mock.patch("agent.graph.book_flight")
def test_agent_plan_hotel_rebooking(mock_book_flight, mock_book_hotel):
    payload = dict(SAMPLE_REQUEST_PAYLOAD)
    payload["disruption_event"]["existing_hotel"] = {
        "id": "hb-1234",
        "hotel_name": "The Cadogan, London",
        "check_in": "2026-07-29T15:00:00Z",
        "check_out": "2026-08-01T11:00:00Z",
        "status": "scheduled",
        "booking_reference": "HTL-4471"
    }
    
    mock_book_flight.return_value = ("MOCK-BK-FL", "success")
    mock_book_hotel.return_value = ("MOCK-BK-HTL", "success")
    
    response = client.post("/agent/plan", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    
    proposed_hotel = res_data["proposed_hotel_booking"]
    assert proposed_hotel is not None
    assert proposed_hotel["hotel_name"] == "The Cadogan, London"
    assert proposed_hotel["status"] == "changed"
    assert proposed_hotel["booking_reference"] == "MOCK-BK-HTL"

@mock.patch("agent.graph.book_flight")
def test_agent_plan_timeout_cancellation(mock_book_flight):
    cancelled_disruption_ids.add("de-0001")
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    res_data = response.json()
    
    assert res_data["proposed_flight_segment"] is None
    mock_book_flight.assert_not_called()

@mock.patch("agent.graph.book_flight")
def test_agent_plan_booking_outage_propagation(mock_book):
    mock_book.side_effect = requests.RequestException("Connection timed out to booking service")
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 500
    res_data = response.json()
    assert res_data["error"]["code"] == "internal_error"
    assert "Connection timed out to booking service" in res_data["error"]["message"]
