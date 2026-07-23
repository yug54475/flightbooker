from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# ==========================================
# Input Request Models (§2.1 / §4.4)
# ==========================================

class FlightSegmentPayload(BaseModel):
    id: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    cabin_class: Literal["economy", "premium_economy", "business", "first"]
    loyalty_program: Optional[str] = None
    original_price: float
    booking_reference: Optional[str] = None
    traveler_count: int = 1  # Modeled field to handle multiple passengers securely

class UserPayload(BaseModel):
    id: str
    card_tier: Literal["premium", "mid", "entry"]
    card_token: str
    name: str
    loyalty_program: Optional[str] = None

class DisruptionEventPayload(BaseModel):
    id: str
    type: Literal["cancelled", "delayed", "missed_connection"]
    delay_minutes: Optional[int] = None
    flight_segment: FlightSegmentPayload
    user: UserPayload

class AgentPlanRequest(BaseModel):
    disruption_event: DisruptionEventPayload


# ==========================================
# Output Response Models (§2.2 / §2.3 / §4.5)
# ==========================================

class ProposedFlightSegment(BaseModel):
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    cabin_class: str
    original_price: float
    booking_reference: Optional[str] = None

class ProposedHotelBooking(BaseModel):
    id: Optional[str] = None
    hotel_name: str
    check_in: str
    check_out: str
    status: str
    booking_reference: Optional[str] = None

class ReasoningStep(BaseModel):
    step_name: str
    input: str
    output: str
    timestamp: str

class AgentPlanResponse(BaseModel):
    proposed_flight_segment: Optional[ProposedFlightSegment] = None
    proposed_hotel_booking: Optional[ProposedHotelBooking] = None
    confidence_score: float
    reasoning_steps: List[ReasoningStep]
