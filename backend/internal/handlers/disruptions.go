package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/queue"
	"github.com/yug54475/flightbooker/internal/validation"
)

// GetDisruptions handles GET /v1/disruptions/:user_id.
func GetDisruptions(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "user_id")
	if !auth.CheckOwnership(w, r, userID) {
		return
	}

	ctx := r.Context()

	rows, err := db.Pool.Query(ctx,
		`SELECT de.id, de.type, de.delay_minutes,
		        fs.id, fs.flight_number, fs.origin, fs.destination,
		        j.id as job_id
		 FROM disruption_events de
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 LEFT JOIN jobs j ON j.disruption_event_id = de.id
		 WHERE i.user_id = $1
		 ORDER BY de.detected_at DESC`, userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load disruptions.")
		return
	}
	defer rows.Close()

	var disruptions []models.DisruptionEvent
	for rows.Next() {
		var d models.DisruptionEvent
		var fs models.FlightSegmentBrief
		if err := rows.Scan(
			&d.ID, &d.Type, &d.DelayMinutes,
			&fs.ID, &fs.FlightNumber, &fs.Origin, &fs.Destination,
			&d.JobID,
		); err != nil {
			validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to scan disruption.")
			return
		}
		d.FlightSegment = &fs
		disruptions = append(disruptions, d)
	}

	if disruptions == nil {
		disruptions = []models.DisruptionEvent{}
	}

	validation.WriteJSON(w, http.StatusOK, disruptions)
}

// SimulateDisruption handles POST /v1/disruptions/simulate.
// Creates a disruption event, updates the flight segment, creates a notification,
// and publishes to SQS — all per §11's hard requirement.
func SimulateDisruption(w http.ResponseWriter, r *http.Request) {
	var req models.SimulateDisruptionRequest
	if !validation.DecodeAndValidate(w, r, &req) {
		return
	}

	callerID, ok := auth.GetUserID(r.Context())
	if !ok {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Could not identify caller.")
		return
	}

	ctx := r.Context()

	// Verify the flight segment exists and belongs to the caller
	var fsUserID, flightNumber, origin, destination, itineraryID string
	err := db.Pool.QueryRow(ctx,
		`SELECT i.user_id, fs.flight_number, fs.origin, fs.destination, fs.itinerary_id
		 FROM flight_segments fs
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 WHERE fs.id = $1`, req.FlightSegmentID,
	).Scan(&fsUserID, &flightNumber, &origin, &destination, &itineraryID)
	if err != nil {
		validation.WriteError(w, http.StatusNotFound, "not_found", "Flight segment not found.")
		return
	}
	if fsUserID != callerID {
		validation.WriteError(w, http.StatusForbidden, "forbidden", "You are not authorized to disrupt this flight segment.")
		return
	}

	tx, err := db.Pool.Begin(ctx)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to begin transaction.")
		return
	}
	defer tx.Rollback(ctx)

	// Update the flight segment status
	newStatus := "cancelled"
	if req.Type == "delayed" {
		newStatus = "delayed"
	}
	_, err = tx.Exec(ctx,
		"UPDATE flight_segments SET status = $1 WHERE id = $2",
		newStatus, req.FlightSegmentID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to update flight segment.")
		return
	}

	// Update itinerary status to disrupted
	_, err = tx.Exec(ctx,
		"UPDATE itineraries SET status = 'disrupted' WHERE id = $1",
		itineraryID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to update itinerary.")
		return
	}

	// Create disruption event
	disruptionID := uuid.New().String()
	now := time.Now().UTC()
	rawPayload, _ := json.Marshal(map[string]interface{}{
		"source":     "simulated",
		"flight":     flightNumber,
		"reason":     "Simulated disruption via API",
		"created_at": now.Format(time.RFC3339),
	})

	_, err = tx.Exec(ctx,
		`INSERT INTO disruption_events (id, flight_segment_id, type, delay_minutes, detected_at, raw_source_payload)
		 VALUES ($1, $2, $3, $4, $5, $6)`,
		disruptionID, req.FlightSegmentID, req.Type, req.DelayMinutes, now, rawPayload)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to create disruption event.")
		return
	}

	// Create notification — hard requirement per §11
	var message string
	switch req.Type {
	case "cancelled":
		message = fmt.Sprintf("Your flight %s (%s–%s) has been cancelled.", flightNumber, origin, destination)
	case "delayed":
		mins := 0
		if req.DelayMinutes != nil {
			mins = *req.DelayMinutes
		}
		message = fmt.Sprintf("Your flight %s (%s–%s) has been delayed by %d minutes.", flightNumber, origin, destination, mins)
	case "missed_connection":
		message = fmt.Sprintf("You may have missed your connection on flight %s (%s–%s).", flightNumber, origin, destination)
	}

	notifID, err := db.InsertNotification(ctx, tx, callerID, "disruption_alert", message)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to create notification.")
		return
	}

	if err := tx.Commit(ctx); err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to commit transaction.")
		return
	}

	// Publish to SQS (outside transaction — SQS is at-least-once anyway)
	if err := queue.Publish(ctx, disruptionID, now.Format(time.RFC3339)); err != nil {
		// Non-fatal: the disruption is recorded, worker can pick it up later via DB scan
		fmt.Printf("Warning: failed to publish to SQS: %v\n", err)
	}

	validation.WriteJSON(w, http.StatusCreated, map[string]interface{}{
		"disruption_event_id": disruptionID,
		"notification_id":     notifID,
		"message":             "Disruption simulated successfully. Worker will process shortly.",
	})
}
