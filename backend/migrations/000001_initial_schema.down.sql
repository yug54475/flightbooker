-- 000001_initial_schema.down.sql
-- Drop everything in reverse dependency order

DROP INDEX IF EXISTS idx_notifications_user;
DROP INDEX IF EXISTS idx_agent_proposals_job;
DROP INDEX IF EXISTS idx_jobs_disruption_event;
DROP INDEX IF EXISTS idx_disruption_events_segment;
DROP INDEX IF EXISTS idx_flight_segments_itinerary;

DROP TABLE IF EXISTS airport_lounges;
DROP TABLE IF EXISTS user_policies;
DROP TABLE IF EXISTS mock_bookings;
DROP TABLE IF EXISTS insurance_claims;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS approvals;
DROP TABLE IF EXISTS agent_proposals;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS disruption_events;
DROP TABLE IF EXISTS hotel_bookings;
DROP TABLE IF EXISTS flight_segments;
DROP TABLE IF EXISTS itineraries;
DROP TABLE IF EXISTS users;
