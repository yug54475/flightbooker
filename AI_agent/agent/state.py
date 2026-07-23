from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    # Input data
    disruption_event: Dict[str, Any]
    
    # Parsed flight parameters
    origin: str
    destination: str
    departure_date: str
    cabin_class: str
    loyalty_program: Optional[str]
    original_price: float
    original_arrival_time: str
    
    # Parsed user parameters
    user_id: str
    card_tier: str
    card_token: str
    user_name: str
    
    # Policy thresholds loaded from Postgres
    max_price_delta: float
    allow_cabin_downgrade: bool
    max_hotel_price_delta: float
    
    # Existing hotel booking on the disrupted itinerary (if any)
    existing_hotel: Optional[Dict[str, Any]]
    
    # Search controls & results
    search_mode: str  # 'same_airport' or 'nearby_airport'
    flight_offers: List[Dict[str, Any]]
    hotel_offers: List[Dict[str, Any]]
    
    # Evaluated candidates (ranked by score)
    evaluated_candidates: List[Dict[str, Any]]
    
    # Selected winning proposal
    best_candidate: Optional[Dict[str, Any]]
    confidence_score: float
    
    # Final output shapes (§2)
    proposed_flight_segment: Optional[Dict[str, Any]]
    proposed_hotel_booking: Optional[Dict[str, Any]]
    
    # Traced reasoning steps
    reasoning_steps: List[Dict[str, Any]]
