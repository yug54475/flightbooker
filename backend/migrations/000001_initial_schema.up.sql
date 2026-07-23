-- 000001_initial_schema.up.sql
-- Travel Disruption Concierge — full schema per implementation_spec_v3 §2

-- Member accounts
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    card_tier TEXT NOT NULL CHECK (card_tier IN ('premium', 'mid', 'entry')),
    card_token TEXT,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- A trip
CREATE TABLE IF NOT EXISTS itineraries (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    status TEXT NOT NULL CHECK (status IN ('active', 'disrupted', 'resolved')) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- One flight leg within an itinerary
CREATE TABLE IF NOT EXISTS flight_segments (
    id UUID PRIMARY KEY,
    itinerary_id UUID NOT NULL REFERENCES itineraries(id),
    flight_number TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_time TIMESTAMPTZ NOT NULL,
    arrival_time TIMESTAMPTZ NOT NULL,
    cabin_class TEXT NOT NULL CHECK (cabin_class IN ('economy', 'premium_economy', 'business', 'first')),
    loyalty_program TEXT,
    status TEXT NOT NULL CHECK (status IN ('scheduled', 'delayed', 'cancelled', 'rebooked')) DEFAULT 'scheduled',
    original_price NUMERIC(10, 2),
    booking_reference TEXT
);

-- Hotel tied to an itinerary
CREATE TABLE IF NOT EXISTS hotel_bookings (
    id UUID PRIMARY KEY,
    itinerary_id UUID NOT NULL REFERENCES itineraries(id),
    hotel_name TEXT,
    check_in TIMESTAMPTZ,
    check_out TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('scheduled', 'changed', 'cancelled')) DEFAULT 'scheduled',
    booking_reference TEXT
);

-- A detected disruption
CREATE TABLE IF NOT EXISTS disruption_events (
    id UUID PRIMARY KEY,
    flight_segment_id UUID NOT NULL REFERENCES flight_segments(id),
    type TEXT NOT NULL CHECK (type IN ('cancelled', 'delayed', 'missed_connection')),
    delay_minutes INT,
    detected_at TIMESTAMPTZ DEFAULT now(),
    raw_source_payload JSONB
);

-- Queue job wrapper (mirrors SQS message, used for idempotency + tracking)
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    disruption_event_id UUID NOT NULL REFERENCES disruption_events(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')) DEFAULT 'pending',
    attempts INT DEFAULT 0,
    sqs_message_id TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- What the AI agent proposed
CREATE TABLE IF NOT EXISTS agent_proposals (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(id),
    proposed_flight_segment JSONB,
    proposed_hotel_booking JSONB,
    confidence_score NUMERIC(4, 3) CHECK (confidence_score BETWEEN 0 AND 1),
    reasoning_steps JSONB,
    status TEXT NOT NULL CHECK (status IN ('auto_approved', 'pending_approval', 'approved', 'declined', 'timed_out')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Member's response when asked
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY,
    agent_proposal_id UUID NOT NULL REFERENCES agent_proposals(id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'declined', 'timed_out')) DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ
);

-- Outbound member notifications
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    type TEXT NOT NULL CHECK (type IN ('disruption_alert', 'rebooking_confirmed', 'approval_request', 'reassurance', 'insurance_eligible')),
    message TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('push', 'sms', 'email')),
    sent_at TIMESTAMPTZ DEFAULT now()
);

-- Insurance eligibility + stub claim tracking
CREATE TABLE IF NOT EXISTS insurance_claims (
    id UUID PRIMARY KEY,
    disruption_event_id UUID NOT NULL REFERENCES disruption_events(id),
    user_id UUID NOT NULL REFERENCES users(id),
    eligible BOOLEAN NOT NULL,
    claim_type TEXT CHECK (claim_type IN ('delay', 'cancellation')),
    amount NUMERIC(10, 2),
    status TEXT NOT NULL CHECK (status IN ('not_eligible', 'eligible', 'initiated')) DEFAULT 'not_eligible',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Records of mock bookings made (flight or hotel)
CREATE TABLE IF NOT EXISTS mock_bookings (
    id UUID PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('flight', 'hotel')),
    reference_code TEXT NOT NULL,
    external_offer_id TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    status TEXT NOT NULL CHECK (status IN ('confirmed', 'failed')),
    charged_amount NUMERIC(10, 2),
    card_token TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Per-member policy limits
CREATE TABLE IF NOT EXISTS user_policies (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    max_price_delta NUMERIC(10, 2) NOT NULL DEFAULT 150.00,
    allow_cabin_downgrade BOOLEAN NOT NULL DEFAULT false,
    max_hotel_price_delta NUMERIC(10, 2) NOT NULL DEFAULT 100.00,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Airport lounge availability
CREATE TABLE IF NOT EXISTS airport_lounges (
    id UUID PRIMARY KEY,
    airport_code TEXT NOT NULL,
    lounge_type TEXT NOT NULL CHECK (lounge_type IN ('centurion', 'priority_pass'))
);

-- Indexes worth adding day 1
CREATE INDEX IF NOT EXISTS idx_flight_segments_itinerary ON flight_segments(itinerary_id);
CREATE INDEX IF NOT EXISTS idx_disruption_events_segment ON disruption_events(flight_segment_id);
CREATE INDEX IF NOT EXISTS idx_jobs_disruption_event ON jobs(disruption_event_id);
CREATE INDEX IF NOT EXISTS idx_agent_proposals_job ON agent_proposals(job_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
