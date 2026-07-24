from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# ==========================================
# Input Request Models (§4.4)
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
    original_price: Decimal  # §0: money fields must use Decimal, never float
    booking_reference: Optional[str] = None

class UserPayload(BaseModel):
    id: str
    card_tier: Literal["premium", "mid", "entry"]
    card_token: str
    # TODO(spec-gap): §4.4 does not include 'name' in the user payload, but §5.1
    # requires a traveler name for the booking request. If the backend doesn't send
    # this, the agent falls back to "Traveler {user_id[:8]}". Needs cross-team
    # resolution on whether to add 'name' to the §4.4 contract.
    name: Optional[str] = None
    loyalty_program: Optional[str] = None
    # TODO(spec-gap): §4.4 does not include user_policies fields (max_price_delta,
    # allow_cabin_downgrade, max_hotel_price_delta) in the request payload. The
    # confidence formula (§7) needs these per-member policy values. Until the backend
    # adds them to the POST /agent/plan wire contract, the agent falls back to DB
    # defaults — meaning custom member policy settings are silently ignored.
    # This is a contract gap between §4.4 and §7 requiring cross-team resolution.
    max_price_delta: Optional[Decimal] = Decimal("150.00")
    allow_cabin_downgrade: Optional[bool] = False
    max_hotel_price_delta: Optional[Decimal] = Decimal("100.00")

class ExistingHotel(BaseModel):
    id: str
    hotel_name: str
    check_in: str
    check_out: str
    status: str
    booking_reference: Optional[str] = None

class DisruptionEventPayload(BaseModel):
    id: str
    type: Literal["cancelled", "delayed", "missed_connection"]
    delay_minutes: Optional[int] = None
    flight_segment: FlightSegmentPayload
    user: UserPayload
    existing_hotel: Optional[ExistingHotel] = None
    itinerary_id: Optional[str] = None

class AgentPlanRequest(BaseModel):
    disruption_event: DisruptionEventPayload


# ==========================================
# Output Response Models (§4.5)
# ==========================================

class ProposedFlightSegment(BaseModel):
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    cabin_class: str
    original_price: Decimal  # §0: money fields must use Decimal, never float
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
