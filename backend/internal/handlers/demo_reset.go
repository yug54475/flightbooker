package handlers

import (
	"log"
	"net/http"

	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/validation"
)

// ResetDemoData wipes all disruption-related data for the logged-in user
// and resets their flights/itineraries to a clean state so they can
// re-run the simulate disruption flow.
func ResetDemoData(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	callerID, ok := auth.GetUserID(ctx)
	if !ok {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Unauthorized")
		return
	}

	tx, err := db.Pool.Begin(ctx)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to start transaction.")
		return
	}
	defer tx.Rollback(ctx)

	// 1. Delete insurance claims
	_, err = tx.Exec(ctx,
		`DELETE FROM insurance_claims WHERE user_id = $1`, callerID)
	if err != nil {
		log.Printf("Failed to delete insurance claims: %v", err)
	}

	// 2. Delete mock bookings
	_, err = tx.Exec(ctx,
		`DELETE FROM mock_bookings WHERE user_id = $1`, callerID)
	if err != nil {
		log.Printf("Failed to delete mock bookings: %v", err)
	}

	// 3. Delete notifications
	_, err = tx.Exec(ctx,
		`DELETE FROM notifications WHERE user_id = $1`, callerID)
	if err != nil {
		log.Printf("Failed to delete notifications: %v", err)
	}

	// 4. Delete approvals linked to this user's proposals
	_, err = tx.Exec(ctx,
		`DELETE FROM approvals WHERE agent_proposal_id IN (
			SELECT ap.id FROM agent_proposals ap
			JOIN jobs j ON ap.job_id = j.id
			JOIN disruption_events de ON j.disruption_event_id = de.id
			JOIN flight_segments fs ON de.flight_segment_id = fs.id
			JOIN itineraries i ON fs.itinerary_id = i.id
			WHERE i.user_id = $1
		)`, callerID)
	if err != nil {
		log.Printf("Failed to delete approvals: %v", err)
	}

	// 5. Delete agent proposals
	_, err = tx.Exec(ctx,
		`DELETE FROM agent_proposals WHERE job_id IN (
			SELECT j.id FROM jobs j
			JOIN disruption_events de ON j.disruption_event_id = de.id
			JOIN flight_segments fs ON de.flight_segment_id = fs.id
			JOIN itineraries i ON fs.itinerary_id = i.id
			WHERE i.user_id = $1
		)`, callerID)
	if err != nil {
		log.Printf("Failed to delete agent proposals: %v", err)
	}

	// 6. Delete jobs
	_, err = tx.Exec(ctx,
		`DELETE FROM jobs WHERE disruption_event_id IN (
			SELECT de.id FROM disruption_events de
			JOIN flight_segments fs ON de.flight_segment_id = fs.id
			JOIN itineraries i ON fs.itinerary_id = i.id
			WHERE i.user_id = $1
		)`, callerID)
	if err != nil {
		log.Printf("Failed to delete jobs: %v", err)
	}

	// 7. Delete disruption events
	_, err = tx.Exec(ctx,
		`DELETE FROM disruption_events WHERE flight_segment_id IN (
			SELECT fs.id FROM flight_segments fs
			JOIN itineraries i ON fs.itinerary_id = i.id
			WHERE i.user_id = $1
		)`, callerID)
	if err != nil {
		log.Printf("Failed to delete disruption events: %v", err)
	}

	// 8. Reset all flight segments to scheduled
	_, err = tx.Exec(ctx,
		`UPDATE flight_segments SET status = 'scheduled'
		 WHERE itinerary_id IN (SELECT id FROM itineraries WHERE user_id = $1)`, callerID)
	if err != nil {
		log.Printf("Failed to reset flight segments: %v", err)
	}

	// 9. Reset itinerary status to active
	_, err = tx.Exec(ctx,
		`UPDATE itineraries SET status = 'active' WHERE user_id = $1`, callerID)
	if err != nil {
		log.Printf("Failed to reset itineraries: %v", err)
	}

	if err := tx.Commit(ctx); err != nil {
		log.Printf("Failed to commit reset demo data: %v", err)
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to reset demo data.")
		return
	}

	validation.WriteJSON(w, http.StatusOK, map[string]string{
		"message": "Demo data reset successfully. You can simulate disruptions again.",
	})
}
