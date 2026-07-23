import pytest
from unittest import mock
from fastapi.testclient import TestClient

from agent.main import app

client = TestClient(app)

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
    # Set up mock database connection
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    # Mock row returned: max_price_delta = 150.00, allow_cabin_downgrade = False, max_hotel_price_delta = 100.00
    mock_cur.fetchone.return_value = (150.00, False, 100.00)
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    # Mock book_flight returning a valid reference
    mock_book.return_value = "MOCK-BK-9182"
    
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
    
    assert len(res_data["reasoning_steps"]) >= 3
    assert res_data["proposed_hotel_booking"] is None

@mock.patch("agent.graph.book_flight")
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_pending_approval_path(mock_connect, mock_book):
    # Set up mock database connection
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    # Mock row returned with max_price_delta = 50.00, which will make price delta score 0
    # Price delta is $90 increase, so delta of 90 > max_price_delta of 50. Thus score goes down.
    mock_cur.fetchone.return_value = (50.00, False, 100.00)
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    
    res_data = response.json()
    # Confidence should be lower than 0.9 because of low price delta limit
    assert res_data["confidence_score"] <= 0.9
    assert res_data["proposed_flight_segment"] is not None
    
    proposed_seg = res_data["proposed_flight_segment"]
    # booking_reference must be null because it's not auto-approved and we shouldn't book
    assert proposed_seg["booking_reference"] is None
    # Verify book_flight mock was not called
    mock_book.assert_not_called()

@mock.patch("agent.graph.search_flight_alternatives")
@mock.patch("agent.graph.psycopg2.connect")
def test_agent_plan_no_alternatives_found(mock_connect, mock_search):
    # Set up mock database connection
    mock_conn = mock.MagicMock()
    mock_cur = mock.MagicMock()
    mock_cur.fetchone.return_value = (150.00, False, 100.00)
    mock_conn.cursor.return_value = mock_cur
    mock_connect.return_value = mock_conn
    
    # Mock search_flight_alternatives returning empty list
    mock_search.return_value = []
    
    response = client.post("/agent/plan", json=SAMPLE_REQUEST_PAYLOAD)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["confidence_score"] == 0.0
    assert res_data["proposed_flight_segment"] is None
    assert res_data["proposed_hotel_booking"] is None
