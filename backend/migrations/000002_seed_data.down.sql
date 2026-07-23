-- 000002_seed_data.down.sql
-- Remove seed data in reverse dependency order

DELETE FROM airport_lounges;
DELETE FROM disruption_events;
DELETE FROM hotel_bookings;
DELETE FROM flight_segments;
DELETE FROM itineraries;
DELETE FROM user_policies;
DELETE FROM users;
