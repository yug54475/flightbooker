package models

import (
	"encoding/json"
	"time"
)

// ============================================================
// Database models — match §2 tables exactly
// ============================================================

// User represents a card member account.
type User struct {
	ID           string    `json:"id"`
	Name         string    `json:"name"`
	Email        string    `json:"email"`
	Phone        *string   `json:"phone,omitempty"`
	CardTier     string    `json:"card_tier"`
	CardToken    *string   `json:"-"` // never expose in API responses
	PasswordHash string    `json:"-"` // never expose
	CreatedAt    time.Time `json:"created_at"`
}

// UserPolicy represents per-member policy limits.
type UserPolicy struct {
	UserID             string  `json:"user_id,omitempty"`
	MaxPriceDelta      float64 `json:"max_price_delta"`
	AllowCabinDowngrade bool   `json:"allow_cabin_downgrade"`
	MaxHotelPriceDelta float64 `json:"max_hotel_price_delta"`
}

// Itinerary represents a trip.
type Itinerary struct {
	ID             string           `json:"id"`
	UserID         string           `json:"user_id,omitempty"`
	Status         string           `json:"status"`
	CreatedAt      time.Time        `json:"created_at,omitempty"`
	FlightSegments []FlightSegment  `json:"flight_segments"`
	HotelBookings  []HotelBooking   `json:"hotel_bookings"`
}

// FlightSegment represents one flight leg within an itinerary.
type FlightSegment struct {
	ID               string    `json:"id"`
	ItineraryID      string    `json:"itinerary_id,omitempty"`
	FlightNumber     string    `json:"flight_number"`
	Origin           string    `json:"origin"`
	Destination      string    `json:"destination"`
	DepartureTime    time.Time `json:"departure_time"`
	ArrivalTime      time.Time `json:"arrival_time"`
	CabinClass       string    `json:"cabin_class"`
	LoyaltyProgram   *string   `json:"loyalty_program,omitempty"`
	Status           string    `json:"status"`
	OriginalPrice    *float64  `json:"original_price,omitempty"`
	BookingReference *string   `json:"booking_reference,omitempty"`
}

// HotelBooking represents a hotel stay tied to an itinerary.
type HotelBooking struct {
	ID               string     `json:"id"`
	ItineraryID      string     `json:"itinerary_id,omitempty"`
	HotelName        *string    `json:"hotel_name,omitempty"`
	CheckIn          *time.Time `json:"check_in,omitempty"`
	CheckOut         *time.Time `json:"check_out,omitempty"`
	Status           string     `json:"status"`
	BookingReference *string    `json:"booking_reference,omitempty"`
}

// DisruptionEvent represents a detected disruption.
type DisruptionEvent struct {
	ID               string           `json:"id"`
	FlightSegmentID  string           `json:"flight_segment_id,omitempty"`
	Type             string           `json:"type"`
	DelayMinutes     *int             `json:"delay_minutes"`
	DetectedAt       time.Time        `json:"detected_at,omitempty"`
	RawSourcePayload json.RawMessage  `json:"raw_source_payload,omitempty"`
	// Joined fields for API responses
	FlightSegment    *FlightSegmentBrief `json:"flight_segment,omitempty"`
	JobID            *string             `json:"job_id"`
}

// FlightSegmentBrief is a minimal view of a flight segment for disruption responses.
type FlightSegmentBrief struct {
	ID           string `json:"id"`
	FlightNumber string `json:"flight_number"`
	Origin       string `json:"origin"`
	Destination  string `json:"destination"`
}

// Job represents a queue job wrapper.
type Job struct {
	ID                string    `json:"id"`
	DisruptionEventID string    `json:"disruption_event_id"`
	IdempotencyKey    string    `json:"idempotency_key"`
	Status            string    `json:"status"`
	Attempts          int       `json:"attempts"`
	SQSMessageID      *string   `json:"sqs_message_id,omitempty"`
	LastError         *string   `json:"last_error,omitempty"`
	CreatedAt         time.Time `json:"created_at"`
	UpdatedAt         time.Time `json:"updated_at"`
}

// AgentProposal represents what the AI agent proposed.
type AgentProposal struct {
	ID                    string          `json:"id,omitempty"`
	JobID                 string          `json:"job_id,omitempty"`
	ProposedFlightSegment json.RawMessage `json:"proposed_flight_segment"`
	ProposedHotelBooking  json.RawMessage `json:"proposed_hotel_booking"`
	ConfidenceScore       float64         `json:"confidence_score"`
	ReasoningSteps        json.RawMessage `json:"reasoning_steps"`
	Status                string          `json:"status"`
	CreatedAt             time.Time       `json:"created_at,omitempty"`
	// Joined for convenience
	ApprovalID            *string         `json:"approval_id,omitempty"`
}

// Approval represents a member's response when asked.
type Approval struct {
	ID              string     `json:"id"`
	AgentProposalID string     `json:"agent_proposal_id,omitempty"`
	Status          string     `json:"status"`
	ExpiresAt       time.Time  `json:"expires_at,omitempty"`
	RespondedAt     *time.Time `json:"responded_at,omitempty"`
}

// Notification represents an outbound member notification.
type Notification struct {
	ID      string    `json:"id"`
	UserID  string    `json:"user_id,omitempty"`
	Type    string    `json:"type"`
	Message string    `json:"message"`
	Channel string    `json:"channel"`
	SentAt  time.Time `json:"sent_at"`
}

// InsuranceClaim represents insurance eligibility + stub claim tracking.
type InsuranceClaim struct {
	ID                string   `json:"id,omitempty"`
	DisruptionEventID string   `json:"disruption_event_id,omitempty"`
	UserID            string   `json:"user_id,omitempty"`
	Eligible          bool     `json:"eligible"`
	ClaimType         *string    `json:"claim_type"`
	Amount            *float64   `json:"amount"`
	Status            string     `json:"status"`
	CreatedAt         time.Time  `json:"created_at,omitempty"`
}

// MockBooking represents a record of a mock booking made.
type MockBooking struct {
	ID              string   `json:"id"`
	Type            string   `json:"type"`
	ReferenceCode   string   `json:"reference_code"`
	ExternalOfferID string   `json:"external_offer_id"`
	UserID          string   `json:"user_id"`
	Status          string   `json:"status"`
	ChargedAmount   *float64 `json:"charged_amount,omitempty"`
	CardToken       *string  `json:"-"`
}

// AirportLounge represents lounge availability at an airport.
type AirportLounge struct {
	ID          string `json:"id"`
	AirportCode string `json:"airport_code"`
	LoungeType  string `json:"lounge_type"`
}

// ============================================================
// Request / Response models
// ============================================================

// SignupRequest is the body for POST /v1/auth/signup.
type SignupRequest struct {
	Name     string `json:"name" validate:"required,min=1,max=200"`
	Email    string `json:"email" validate:"required,email"`
	Password string `json:"password" validate:"required,min=6,max=128"`
	CardTier string `json:"card_tier" validate:"required,oneof=premium mid entry"`
}

// LoginRequest is the body for POST /v1/auth/login.
type LoginRequest struct {
	Email    string `json:"email" validate:"required,email"`
	Password string `json:"password" validate:"required"`
}

// AuthResponse is the response for signup and login.
type AuthResponse struct {
	Token  string `json:"token"`
	UserID string `json:"user_id"`
}

// PolicyUpdateRequest is the body for PATCH /v1/users/me/policy.
type PolicyUpdateRequest struct {
	MaxPriceDelta      *float64 `json:"max_price_delta" validate:"omitempty,gte=0"`
	AllowCabinDowngrade *bool   `json:"allow_cabin_downgrade"`
	MaxHotelPriceDelta *float64 `json:"max_hotel_price_delta" validate:"omitempty,gte=0"`
}

// ApprovalRespondRequest is the body for POST /v1/approvals/:approval_id/respond.
type ApprovalRespondRequest struct {
	Decision string `json:"decision" validate:"required,oneof=approved declined"`
}

// SimulateDisruptionRequest is the body for POST /v1/disruptions/simulate.
type SimulateDisruptionRequest struct {
	FlightSegmentID string `json:"flight_segment_id" validate:"required,uuid"`
	Type            string `json:"type" validate:"required,oneof=cancelled delayed missed_connection"`
	DelayMinutes    *int   `json:"delay_minutes" validate:"omitempty,gte=0"`
}

// ErrorResponse is the standard error envelope per §3.2.
type ErrorResponse struct {
	Error ErrorDetail `json:"error"`
}

// ErrorDetail is the inner error object.
type ErrorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

// TimelineEntry represents a single step in the user's timeline.
type TimelineEntry struct {
	StepName    string `json:"step_name"`
	Timestamp   string `json:"timestamp"`
	Description string `json:"description"`
}

// ============================================================
// Agent communication models (§4.4 / §4.5)
// ============================================================

// AgentPlanRequest is sent to POST /agent/plan.
type AgentPlanRequest struct {
	DisruptionEvent AgentDisruptionPayload `json:"disruption_event"`
}

// AgentDisruptionPayload carries the disruption context to the agent.
type AgentDisruptionPayload struct {
	ID            string                   `json:"id"`
	Type          string                   `json:"type"`
	DelayMinutes  *int                     `json:"delay_minutes"`
	FlightSegment AgentFlightSegPayload    `json:"flight_segment"`
	User          AgentUserPayload         `json:"user"`
}

// AgentFlightSegPayload is the flight segment context sent to the agent.
type AgentFlightSegPayload struct {
	ID               string   `json:"id"`
	FlightNumber     string   `json:"flight_number"`
	Origin           string   `json:"origin"`
	Destination      string   `json:"destination"`
	DepartureTime    string   `json:"departure_time"`
	ArrivalTime      string   `json:"arrival_time"`
	CabinClass       string   `json:"cabin_class"`
	LoyaltyProgram   *string  `json:"loyalty_program"`
	OriginalPrice    *float64 `json:"original_price"`
	BookingReference *string  `json:"booking_reference"`
}

// AgentUserPayload is the user context sent to the agent.
type AgentUserPayload struct {
	ID             string  `json:"id"`
	CardTier       string  `json:"card_tier"`
	CardToken      *string `json:"card_token"`
	LoyaltyProgram *string `json:"loyalty_program"`
}

// AgentPlanResponse is what the agent returns.
type AgentPlanResponse struct {
	ProposedFlightSegment json.RawMessage `json:"proposed_flight_segment"`
	ProposedHotelBooking  json.RawMessage `json:"proposed_hotel_booking"`
	ConfidenceScore       float64         `json:"confidence_score"`
	ReasoningSteps        json.RawMessage `json:"reasoning_steps"`
}

// ============================================================
// Mock API models (§5, §6)
// ============================================================

// MockFlightOrderRequest mirrors Amadeus Flight Create Orders request.
type MockFlightOrderRequest struct {
	Data MockFlightOrderData `json:"data"`
}

// MockFlightOrderData is the data field in the booking request.
type MockFlightOrderData struct {
	Type         string          `json:"type"`
	FlightOffers json.RawMessage `json:"flightOffers"`
	Travelers    json.RawMessage `json:"travelers"`
	CardToken    string          `json:"card_token"`
}

// MockFlightOrderResponse mirrors Amadeus Flight Create Orders response.
type MockFlightOrderResponse struct {
	Data MockFlightOrderResponseData `json:"data"`
}

// MockFlightOrderResponseData is the response data.
type MockFlightOrderResponseData struct {
	Type      string  `json:"type"`
	ID        *string `json:"id"`
	Reference *string `json:"reference"`
	Status    string  `json:"status"`
}

// MockHotelOrderRequest is the body for POST /mock/v1/booking/hotel-orders.
type MockHotelOrderRequest struct {
	HotelID    string  `json:"hotel_id" validate:"required"`
	HotelName  string  `json:"hotel_name" validate:"required"`
	UserID     string  `json:"user_id" validate:"required,uuid"`
	CheckIn    string  `json:"check_in" validate:"required"`
	CheckOut   string  `json:"check_out" validate:"required"`
	CardToken  string  `json:"card_token" validate:"required"`
	TotalPrice float64 `json:"total_price" validate:"gte=0"`
}

// MockHotelOrderResponse is the response for hotel booking.
type MockHotelOrderResponse struct {
	BookingReference *string `json:"booking_reference"`
	Status           string  `json:"status"`
}
