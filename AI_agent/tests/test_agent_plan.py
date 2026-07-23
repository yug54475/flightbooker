import pytest
import requests
from unittest import mock
from fastapi.testclient import TestClient

from agent.main import app, completed_proposals_cache, processing_locks
from agent.config import cancelled_disruption_ids

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_caches_and_locks():
    """Autouse fixture to reset the FastAPI in-memory proposal caches and locks between tests."""
    completed_proposals_cache.clear()
    processing_locks.clear()
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
      "name": "Amir Khan"
    }
  }
}

@mock.patch("agent.graph.book_flight")
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_auto_approved_path(mock_connect, mock_book):
    # Set up mock database connection (returning no hotel rows)
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    # First query is for user_policies, second is for hotel_bookings (which returns None)
    mock_cur.fetchone.side_effect = [
        (150.00, False, 100.00), # user_policies
        None                      # hotel_bookings
    ]
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    # Mock book_flight returning a valid reference and success status tuple
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
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_pending_approval_path(mock_connect, mock_book):
    # Set up mock database connection
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    mock_cur.fetchone.side_effect = [
        (50.00, False, 100.00), # user_policies
        None                     # hotel_bookings
    ]
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["confidence_score"] <= 0.9
    assert res_data["proposed_flight_segment"] is not None
    
    proposed_seg = res_data["proposed_flight_segment"]
    assert proposed_seg["booking_reference"] is None
    mock_book.assert_not_called()

@mock.patch("agent.graph.search_flight_alternatives")
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_no_alternatives_found(mock_connect, mock_search):
    # Set up mock database connection
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    mock_cur.fetchone.side_effect = [
        (150.00, False, 100.00), # user_policies
        None                      # hotel_bookings
    ]
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    mock_search.return_value = []
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["confidence_score"] == 0.0
    assert res_data["proposed_flight_segment"] is None
    assert res_data["proposed_hotel_booking"] is None

@mock.patch("agent.graph.book_flight")
@mock.patch("agent.graph.search_flight_alternatives")
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_connecting_itinerary(mock_connect, mock_search, mock_book):
    # Verify that a 2-segment connection is parsed correctly
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    mock_cur.fetchone.side_effect = [
        (150.00, False, 100.00), # user_policies
        None                      # hotel_bookings
    ]
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    mock_book.return_value = ("MOCK-BK-9182", "success")
    
    # Mocking Amadeus returning a 2-segment flight (JFK -> CDG -> LHR)
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
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_hotel_rebooking(mock_connect, mock_book_flight, mock_book_hotel):
    # Set up mock database connection returning a hotel booking
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    mock_cur.fetchone.side_effect = [
        (150.00, False, 100.00), # user_policies
        ("hb-1234", "The Cadogan, London", "2026-07-29T15:00:00Z", "2026-08-01T11:00:00Z", "scheduled", "HTL-4471") # hotel_bookings
    ]
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    mock_book_flight.return_value = ("MOCK-BK-FL", "success")
    mock_book_hotel.return_value = ("MOCK-BK-HTL", "success")
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    res_data = response.json()
    
    proposed_hotel = res_data["proposed_hotel_booking"]
    assert proposed_hotel is not None
    assert proposed_hotel["hotel_name"] == "The Cadogan, London"
    assert proposed_hotel["status"] == "changed"
    assert proposed_hotel["booking_reference"] == "MOCK-BK-HTL"

@mock.patch("agent.graph.book_flight")
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_timeout_cancellation(mock_connect, mock_book_flight):
    # Set up mock database connection
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    mock_cur.fetchone.side_effect = [
        (150.00, False, 100.00), # user_policies
        None                      # hotel_bookings
    ]
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    # Proactively register the disruption ID as timed out/cancelled (Issue 5)
    cancelled_disruption_ids.add("de-0001")
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    res_data = response.json()
    
    # Flight segment should not have any booking reference because booking was aborted
    assert res_data["proposed_flight_segment"] is None
    mock_book_flight.assert_not_called()

@mock.patch("agent.graph.book_flight")
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_booking_outage_propagation(mock_connect, mock_book):
    # Test that connection outages during bookings propagate as 500 exceptions (Issue 1)
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    mock_cur.fetchone.side_effect = [
        (150.00, False, 100.00), # user_policies
        None                      # hotel_bookings
    ]
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    # Simulate a network/outage Exception
    mock_book.side_effect = requests.RequestException("Connection timed out to booking service")
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 500
    res_data = response.json()
    assert res_data["error"]["code"] == "internal_error"
    assert "Connection timed out to booking service" in res_data["error"]["message"]
