package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

// GetTimeline handles GET /v1/timeline/:user_id.
// Assembles a chronological timeline from disruption_events, agent_proposals, and notifications.
func GetTimeline(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "user_id")
	if !auth.CheckOwnership(w, r, userID) {
		return
	}

	ctx := r.Context()
	var timeline []models.TimelineEntry

	// 1. Disruption events
	deRows, err := db.Pool.Query(ctx,
		`SELECT de.detected_at, fs.flight_number, fs.origin, fs.destination, de.type, de.delay_minutes
		 FROM disruption_events de
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 WHERE i.user_id = $1
		 ORDER BY de.detected_at`, userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load disruption events.")
		return
	}
	defer deRows.Close()

	for deRows.Next() {
		var detectedAt time.Time
		var flightNum, origin, dest, disType string
		var delayMins *int
		if err := deRows.Scan(&detectedAt, &flightNum, &origin, &dest, &disType, &delayMins); err != nil {
			continue
		}
		desc := ""
		switch disType {
		case "cancelled":
			desc = flightNum + " (" + origin + "–" + dest + ") was cancelled."
		case "delayed":
			mins := 0
			if delayMins != nil {
				mins = *delayMins
			}
			desc = flightNum + " (" + origin + "–" + dest + ") delayed by " + intToStr(mins) + " minutes."
		case "missed_connection":
			desc = "Missed connection on " + flightNum + " (" + origin + "–" + dest + ")."
		}
		timeline = append(timeline, models.TimelineEntry{
			StepName:    "disruption_detected",
			Timestamp:   detectedAt.Format(time.RFC3339),
			Description: desc,
		})
	}

	// 2. Agent proposals
	apRows, err := db.Pool.Query(ctx,
		`SELECT ap.created_at, ap.confidence_score, ap.status, ap.proposed_flight_segment
		 FROM agent_proposals ap
		 JOIN jobs j ON ap.job_id = j.id
		 JOIN disruption_events de ON j.disruption_event_id = de.id
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 WHERE i.user_id = $1
		 ORDER BY ap.created_at`, userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load agent proposals.")
		return
	}
	defer apRows.Close()

	for apRows.Next() {
		var createdAt time.Time
		var confidence float64
		var status string
		var proposedFlight []byte
		if err := apRows.Scan(&createdAt, &confidence, &status, &proposedFlight); err != nil {
			continue
		}

		// Extract flight number from proposed segment JSON
		flightNum := "alternative flight"
		var seg map[string]interface{}
		if err := jsonUnmarshal(proposedFlight, &seg); err == nil {
			if fn, ok := seg["flight_number"].(string); ok {
				flightNum = fn
			}
		}

		desc := "Agent proposed " + flightNum + ", confidence " + formatFloat(confidence) + ", " + status + "."
		timeline = append(timeline, models.TimelineEntry{
			StepName:    "agent_proposal_created",
			Timestamp:   createdAt.Format(time.RFC3339),
			Description: desc,
		})
	}

	// 3. Rebooking confirmations from notifications
	nRows, err := db.Pool.Query(ctx,
		`SELECT sent_at, type, message
		 FROM notifications
		 WHERE user_id = $1 AND type IN ('rebooking_confirmed', 'approval_request', 'reassurance', 'insurance_eligible')
		 ORDER BY sent_at`, userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load notifications.")
		return
	}
	defer nRows.Close()

	for nRows.Next() {
		var sentAt time.Time
		var nType, message string
		if err := nRows.Scan(&sentAt, &nType, &message); err != nil {
			continue
		}
		stepName := "notification_sent"
		switch nType {
		case "rebooking_confirmed":
			stepName = "rebooking_confirmed"
		case "approval_request":
			stepName = "approval_requested"
		case "insurance_eligible":
			stepName = "insurance_eligible"
		}
		timeline = append(timeline, models.TimelineEntry{
			StepName:    stepName,
			Timestamp:   sentAt.Format(time.RFC3339),
			Description: message,
		})
	}

	// Sort timeline by timestamp
	sortTimeline(timeline)

	if timeline == nil {
		timeline = []models.TimelineEntry{}
	}

	validation.WriteJSON(w, http.StatusOK, timeline)
}

// Helper functions

func intToStr(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	neg := false
	if n < 0 {
		neg = true
		n = -n
	}
	for n > 0 {
		s = string(rune('0'+n%10)) + s
		n /= 10
	}
	if neg {
		s = "-" + s
	}
	return s
}

func formatFloat(f float64) string {
	// Simple format to 2 decimal places
	whole := int(f)
	frac := int((f - float64(whole)) * 100)
	if frac < 0 {
		frac = -frac
	}
	return intToStr(whole) + "." + padLeft(intToStr(frac), 2, '0')
}

func padLeft(s string, length int, pad byte) string {
	for len(s) < length {
		s = string(pad) + s
	}
	return s
}

func sortTimeline(entries []models.TimelineEntry) {
	// Simple insertion sort (timeline is small)
	for i := 1; i < len(entries); i++ {
		for j := i; j > 0 && entries[j].Timestamp < entries[j-1].Timestamp; j-- {
			entries[j], entries[j-1] = entries[j-1], entries[j]
		}
	}
}

func jsonUnmarshal(data []byte, v interface{}) error {
	if len(data) == 0 {
		return nil
	}
	return json.Unmarshal(data, v)
}
