-- 000002_seed_data.up.sql
-- Seed data per §2.1: 3 users, itineraries, flight segments, hotels, 
-- a pre-triggered disruption, policies, and airport lounges.
--
-- Passwords are all "demo1234" hashed with bcrypt cost 12.
-- bcrypt hash for "demo1234": $2a$12$.WHLfVKXGF1p/qCHJxvw6u4OWpYqEVnPSzj.4kjFaBJkChbfuTbwa

-- ============================================================
-- USERS (one per card_tier)
-- ============================================================
INSERT INTO users (id, name, email, phone, card_tier, card_token, password_hash) VALUES
    ('9d3f1b2a-2222-4a3e-8b1a-111111111111', 'Amir Khan',    'amir@example.com',    '+1-555-0101', 'premium', 'tok_demo_premium_001', '$2a$12$.WHLfVKXGF1p/qCHJxvw6u4OWpYqEVnPSzj.4kjFaBJkChbfuTbwa'),
    ('b47e2c3d-3333-4b4f-9c2b-222222222222', 'Sara Patel',   'sara@example.com',    '+1-555-0102', 'mid',     'tok_demo_mid_002',     '$2a$12$.WHLfVKXGF1p/qCHJxvw6u4OWpYqEVnPSzj.4kjFaBJkChbfuTbwa'),
    ('c58f3d4e-4444-4c5a-ad3c-333333333333', 'Jordan Lee',   'jordan@example.com',  '+1-555-0103', 'entry',   'tok_demo_entry_003',   '$2a$12$.WHLfVKXGF1p/qCHJxvw6u4OWpYqEVnPSzj.4kjFaBJkChbfuTbwa');

-- ============================================================
-- USER POLICIES (defaults per §2)
-- ============================================================
INSERT INTO user_policies (user_id, max_price_delta, allow_cabin_downgrade, max_hotel_price_delta) VALUES
    ('9d3f1b2a-2222-4a3e-8b1a-111111111111', 150.00, false, 100.00),
    ('b47e2c3d-3333-4b4f-9c2b-222222222222', 150.00, false, 100.00),
    ('c58f3d4e-4444-4c5a-ad3c-333333333333', 150.00, false, 100.00);

-- ============================================================
-- ITINERARIES (one per user)
-- ============================================================
INSERT INTO itineraries (id, user_id, status) VALUES
    ('a1111111-aaaa-4aaa-aaaa-aaaaaaaaaaaa', '9d3f1b2a-2222-4a3e-8b1a-111111111111', 'disrupted'),
    ('b2222222-bbbb-4bbb-bbbb-bbbbbbbbbbbb', 'b47e2c3d-3333-4b4f-9c2b-222222222222', 'active'),
    ('c3333333-cccc-4ccc-cccc-cccccccccccc', 'c58f3d4e-4444-4c5a-ad3c-333333333333', 'active');

-- ============================================================
-- FLIGHT SEGMENTS (real IATA routes for Amadeus test env)
-- ============================================================
-- Amir: JFK → LHR (cancelled — will be disrupted) + LHR → CDG connecting
INSERT INTO flight_segments (id, itinerary_id, flight_number, origin, destination, departure_time, arrival_time, cabin_class, loyalty_program, status, original_price, booking_reference) VALUES
    ('f5111111-1111-4111-8111-111111111111', 'a1111111-aaaa-4aaa-aaaa-aaaaaaaaaaaa', 'BA112',  'JFK', 'LHR', '2026-07-28T21:10:00Z', '2026-07-29T09:05:00Z', 'business', 'BA Executive Club', 'cancelled', 4820.00, 'QF7X2K'),
    ('f5111111-1111-4111-8111-222222222222', 'a1111111-aaaa-4aaa-aaaa-aaaaaaaaaaaa', 'BA304',  'LHR', 'CDG', '2026-07-29T12:30:00Z', '2026-07-29T14:45:00Z', 'business', 'BA Executive Club', 'scheduled', 680.00,  'QF7X2L');

-- Sara: LAX → CDG
INSERT INTO flight_segments (id, itinerary_id, flight_number, origin, destination, departure_time, arrival_time, cabin_class, loyalty_program, status, original_price, booking_reference) VALUES
    ('f5222222-2222-4222-8222-111111111111', 'b2222222-bbbb-4bbb-bbbb-bbbbbbbbbbbb', 'AF65',   'LAX', 'CDG', '2026-07-30T16:25:00Z', '2026-07-31T11:40:00Z', 'premium_economy', 'Flying Blue', 'scheduled', 2150.00, 'AF9K3M');

-- Jordan: SFO → NRT
INSERT INTO flight_segments (id, itinerary_id, flight_number, origin, destination, departure_time, arrival_time, cabin_class, loyalty_program, status, original_price, booking_reference) VALUES
    ('f5333333-3333-4333-8333-111111111111', 'c3333333-cccc-4ccc-cccc-cccccccccccc', 'JL1',    'SFO', 'NRT', '2026-08-01T11:15:00Z', '2026-08-02T14:30:00Z', 'economy',  'JAL Mileage Bank', 'scheduled', 1280.00, 'JL5P8R');

-- ============================================================
-- HOTEL BOOKINGS
-- ============================================================
INSERT INTO hotel_bookings (id, itinerary_id, hotel_name, check_in, check_out, status, booking_reference) VALUES
    ('b1111111-1111-4111-8111-111111111111', 'a1111111-aaaa-4aaa-aaaa-aaaaaaaaaaaa', 'The Cadogan, London',       '2026-07-29T15:00:00Z', '2026-08-01T11:00:00Z', 'scheduled', 'HTL-4471'),
    ('b2222222-2222-4222-8222-111111111111', 'b2222222-bbbb-4bbb-bbbb-bbbbbbbbbbbb', 'Le Marais Boutique, Paris', '2026-07-31T14:00:00Z', '2026-08-03T11:00:00Z', 'scheduled', 'HTL-5582'),
    ('b3333333-3333-4333-8333-111111111111', 'c3333333-cccc-4ccc-cccc-cccccccccccc', 'Park Hotel Tokyo',         '2026-08-02T15:00:00Z', '2026-08-05T11:00:00Z', 'scheduled', 'HTL-6693');

-- ============================================================
-- PRE-TRIGGERED DISRUPTION (Amir's BA112 is cancelled)
-- ============================================================
INSERT INTO disruption_events (id, flight_segment_id, type, delay_minutes, detected_at, raw_source_payload) VALUES
    ('de111111-1111-4111-8111-111111111111', 'f5111111-1111-4111-8111-111111111111', 'cancelled', NULL, '2026-07-28T18:14:50Z',
     '{"source": "simulated", "flight": "BA112", "reason": "Aircraft mechanical issue", "cancelled_at": "2026-07-28T18:14:50Z"}'::jsonb);

-- ============================================================
-- AIRPORT LOUNGES (§10 — mix of centurion and priority_pass)
-- ============================================================
INSERT INTO airport_lounges (id, airport_code, lounge_type) VALUES
    ('19111111-1111-4111-8111-111111111111', 'JFK', 'centurion'),
    ('19222222-2222-4222-8222-111111111111', 'LHR', 'priority_pass'),
    ('19333333-3333-4333-8333-111111111111', 'LAX', 'centurion'),
    ('19444444-4444-4444-8444-111111111111', 'CDG', 'priority_pass'),
    ('19555555-5555-4555-8555-111111111111', 'SFO', 'centurion'),
    ('19666666-6666-4666-8666-111111111111', 'NRT', 'priority_pass');
