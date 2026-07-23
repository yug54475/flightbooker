package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

// RespondToApproval handles POST /v1/approvals/:approval_id/respond.
func RespondToApproval(w http.ResponseWriter, r *http.Request) {
	approvalID := chi.URLParam(r, "approval_id")

	var req models.ApprovalRespondRequest
	if !validation.DecodeAndValidate(w, r, &req) {
		return
	}

	ctx := r.Context()

	// Load the approval
	var currentStatus, proposalID string
	err := db.Pool.QueryRow(ctx,
		"SELECT status, agent_proposal_id FROM approvals WHERE id = $1",
		approvalID,
	).Scan(&currentStatus, &proposalID)
	if err != nil {
		validation.WriteError(w, http.StatusNotFound, "not_found", "Approval not found.")
		return
	}

	// Check if already responded — 409 conflict
	if currentStatus != "pending" {
		validation.WriteError(w, http.StatusConflict, "conflict",
			fmt.Sprintf("This approval has already been %s. Responses are final.", currentStatus))
		return
	}

	now := time.Now().UTC()

	tx, err := db.Pool.Begin(ctx)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to begin transaction.")
		return
	}
	defer tx.Rollback(ctx)

	// Update approval
	_, err = tx.Exec(ctx,
		"UPDATE approvals SET status = $1, responded_at = $2 WHERE id = $3",
		req.Decision, now, approvalID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to update approval.")
		return
	}

	// Update agent_proposal status
	_, err = tx.Exec(ctx,
		"UPDATE agent_proposals SET status = $1 WHERE id = $2",
		req.Decision, proposalID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to update proposal.")
		return
	}

	// If approved, trigger mock booking and create notification
	if req.Decision == "approved" {
		if err := triggerBookingAfterApproval(ctx, tx, proposalID); err != nil {
			fmt.Printf("Warning: booking after approval failed: %v\n", err)
			// Non-fatal for the approval itself
		}
	}

	if err := tx.Commit(ctx); err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to commit transaction.")
		return
	}

	validation.WriteJSON(w, http.StatusOK, models.Approval{
		ID:          approvalID,
		Status:      req.Decision,
		RespondedAt: &now,
	})
}

// triggerBookingAfterApproval creates a mock booking record and notification
// after a member approves a pending proposal (§8).
func triggerBookingAfterApproval(ctx context.Context, _ interface{}, proposalID string) error {
	// Load proposal details to create booking
	var proposedFlight json.RawMessage
	var jobID string
	err := db.Pool.QueryRow(ctx,
		"SELECT proposed_flight_segment, job_id FROM agent_proposals WHERE id = $1",
		proposalID,
	).Scan(&proposedFlight, &jobID)
	if err != nil {
		return fmt.Errorf("failed to load proposal: %w", err)
	}

	// Load user from job chain: proposal → job → disruption_event → flight_segment → itinerary → user
	var userID, cardToken string
	err = db.Pool.QueryRow(ctx,
		`SELECT u.id, COALESCE(u.card_token, '')
		 FROM jobs j
		 JOIN disruption_events de ON j.disruption_event_id = de.id
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 JOIN users u ON i.user_id = u.id
		 WHERE j.id = $1`, jobID,
	).Scan(&userID, &cardToken)
	if err != nil {
		return fmt.Errorf("failed to load user for booking: %w", err)
	}

	// Parse price from proposed flight segment
	var flightData map[string]interface{}
	if err := json.Unmarshal(proposedFlight, &flightData); err == nil {
		price, _ := flightData["original_price"].(float64)
		bookingRef, _ := flightData["booking_reference"].(string)
		if bookingRef == "" {
			bookingRef = fmt.Sprintf("MOCK-BK-%s", uuid.New().String()[:4])
		}

		// Create mock_bookings record
		mockBookingID := uuid.New().String()
		_, execErr := db.Pool.Exec(ctx,
			`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token)
			 VALUES ($1, 'flight', $2, $3, $4, 'confirmed', $5, $6)`,
			mockBookingID, bookingRef, "approved-offer", userID, price, cardToken)
		if execErr != nil {
			return fmt.Errorf("failed to insert mock booking: %w", execErr)
		}

		// Create rebooking_confirmed notification
		flightNum, _ := flightData["flight_number"].(string)
		notifID := uuid.New().String()
		message := fmt.Sprintf("Your rebooking has been confirmed. You are now on flight %s.", flightNum)
		_, execErr = db.Pool.Exec(ctx,
			`INSERT INTO notifications (id, user_id, type, message, channel, sent_at)
			 VALUES ($1, $2, 'rebooking_confirmed', $3, 'push', $4)`,
			notifID, userID, message, time.Now().UTC())
		if execErr != nil {
			return fmt.Errorf("failed to insert notification: %w", execErr)
		}
	}

	return nil
}
