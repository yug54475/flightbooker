package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/booking"
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

	callerID, ok := auth.GetUserID(ctx)
	if !ok {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Could not identify caller.")
		return
	}

	// Load the approval and verify ownership
	var currentStatus, proposalID string
	err := db.Pool.QueryRow(ctx,
		`SELECT a.status, a.agent_proposal_id
		 FROM approvals a
		 JOIN agent_proposals ap ON a.agent_proposal_id = ap.id
		 JOIN jobs j ON ap.job_id = j.id
		 JOIN disruption_events de ON j.disruption_event_id = de.id
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 WHERE a.id = $1 AND i.user_id = $2`,
		approvalID, callerID,
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
			log.Printf("Booking after approval failed: %v", err)
			validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Booking failed after approval. Please try again.")
			return
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

// triggerBookingAfterApproval creates mock booking records and notifications
// after a member approves a pending proposal (§8).
func triggerBookingAfterApproval(ctx context.Context, tx pgx.Tx, proposalID string) error {
	// Load proposal details to create booking
	var proposedFlight, proposedHotel json.RawMessage
	var jobID string
	err := tx.QueryRow(ctx,
		"SELECT proposed_flight_segment, proposed_hotel_booking, job_id FROM agent_proposals WHERE id = $1",
		proposalID,
	).Scan(&proposedFlight, &proposedHotel, &jobID)
	if err != nil {
		return fmt.Errorf("failed to load proposal: %w", err)
	}

	flightNum, err := booking.ExecuteProposedBooking(ctx, tx, jobID, proposedFlight, proposedHotel)
	if err != nil {
		return err
	}

	// Load user for notification
	var userID string
	err = tx.QueryRow(ctx,
		`SELECT i.user_id
		 FROM jobs j
		 JOIN disruption_events de ON j.disruption_event_id = de.id
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 WHERE j.id = $1`, jobID,
	).Scan(&userID)
	if err != nil {
		return fmt.Errorf("failed to load user for notification: %w", err)
	}

	message := fmt.Sprintf("Your rebooking has been confirmed. You are now on flight %s.", flightNum)
	if proposedHotel != nil && string(proposedHotel) != "null" {
		message = fmt.Sprintf("Your rebooking has been confirmed. You are now on flight %s, and your hotel has been updated.", flightNum)
	}

	_, execErr := db.InsertNotification(ctx, tx, userID, "rebooking_confirmed", message)
	if execErr != nil {
		return fmt.Errorf("failed to insert notification: %w", execErr)
	}

	return nil
}
