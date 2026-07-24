// ============================================================
// TypeScript types — mirrors backend/internal/models/models.go
// ============================================================

// Auth
export interface AuthResponse {
  token: string;
  user_id: string;
}

export interface SignupRequest {
  name: string;
  email: string;
  password: string;
  card_tier: 'premium' | 'mid' | 'entry';
}

export interface LoginRequest {
  email: string;
  password: string;
}

// User
export interface User {
  id: string;
  name: string;
  email: string;
  card_tier: 'premium' | 'mid' | 'entry';
}

export interface UserPolicy {
  max_price_delta: number;
  allow_cabin_downgrade: boolean;
  max_hotel_price_delta: number;
}

export interface PolicyUpdateRequest {
  max_price_delta?: number;
  allow_cabin_downgrade?: boolean;
  max_hotel_price_delta?: number;
}

// Itinerary / Flights / Hotels
export type ItineraryStatus = 'active' | 'disrupted' | 'resolved';
export type FlightStatus = 'scheduled' | 'delayed' | 'cancelled' | 'rebooked';
export type CabinClass = 'economy' | 'premium_economy' | 'business' | 'first';
export type HotelStatus = 'scheduled' | 'changed' | 'cancelled';

export interface FlightSegment {
  id: string;
  itinerary_id?: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string; // ISO8601
  arrival_time: string;   // ISO8601
  cabin_class: CabinClass;
  loyalty_program?: string | null;
  status: FlightStatus;
  original_price?: number | null;
  booking_reference?: string | null;
}

export interface HotelBooking {
  id: string;
  itinerary_id?: string;
  hotel_name?: string | null;
  check_in?: string | null;
  check_out?: string | null;
  status: HotelStatus;
  booking_reference?: string | null;
}

export interface ProposedFlightSegment {
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  cabin_class: CabinClass;
  original_price?: number | null;
  booking_reference?: string | null;
  loyalty_program?: string | null;
  status?: FlightStatus;
}

export interface ProposedHotelBooking {
  id?: string | null;
  hotel_name: string;
  check_in: string;
  check_out: string;
  status?: HotelStatus;
  booking_reference?: string | null;
}

export interface Itinerary {
  id: string;
  user_id?: string;
  status: ItineraryStatus;
  created_at?: string;
  flight_segments: FlightSegment[];
  hotel_bookings: HotelBooking[];
}

// Disruptions
export type DisruptionType = 'cancelled' | 'delayed' | 'missed_connection';

export interface FlightSegmentBrief {
  id: string;
  flight_number: string;
  origin: string;
  destination: string;
}

export interface DisruptionEvent {
  id: string;
  type: DisruptionType;
  delay_minutes: number | null;
  job_id: string | null;
  flight_segment: FlightSegmentBrief;
}

export interface SimulateDisruptionRequest {
  flight_segment_id: string;
  type: DisruptionType;
  delay_minutes?: number | null;
}

export interface SimulateDisruptionResponse {
  disruption_event_id: string;
  notification_id: string;
  message: string;
}

// Agent Proposals
export type ProposalStatus =
  | 'auto_approved'
  | 'pending_approval'
  | 'approved'
  | 'declined'
  | 'timed_out';

export interface ReasoningStep {
  step_name: string;
  input: string;
  output: string;
  timestamp: string;
}

export interface AgentProposal {
  id?: string;
  job_id?: string;
  confidence_score: number;
  status: ProposalStatus;
  proposed_flight_segment: ProposedFlightSegment | null;
  proposed_hotel_booking: ProposedHotelBooking | null;
  reasoning_steps: ReasoningStep[];
  approval_id?: string | null;
  created_at?: string;
}

// Approvals
export interface ApprovalRespondRequest {
  decision: 'approved' | 'declined';
}

export interface ApprovalRespondResponse {
  id: string;
  status: string;
  responded_at: string;
}

// Notifications
export type NotificationType =
  | 'disruption_alert'
  | 'rebooking_confirmed'
  | 'approval_request'
  | 'reassurance'
  | 'insurance_eligible';

export type NotificationChannel = 'push' | 'sms' | 'email';

export interface Notification {
  id: string;
  type: NotificationType;
  message: string;
  channel: NotificationChannel;
  sent_at: string;
}

// Insurance
export type InsuranceStatus = 'not_eligible' | 'eligible' | 'initiated';
export type ClaimType = 'delay' | 'cancellation';

export interface InsuranceClaim {
  id: string;
  disruption_event_id?: string;
  eligible: boolean;
  claim_type: ClaimType | null;
  amount: number | null;
  status: InsuranceStatus;
  created_at?: string;
}

// Timeline
export interface TimelineEntry {
  step_name: string;
  timestamp: string;
  description: string;
}

// Error envelope
export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
