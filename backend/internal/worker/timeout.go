package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/yug54475/flightbooker/internal/booking"
	"github.com/yug54475/flightbooker/internal/db"
)

// RunApprovalTimeoutTicker implements §7.1: checks for expired approvals every 60 seconds.
// On timeout:
//  1. Sets approval status to 'timed_out'
//  2. Sets agent_proposals status to 'timed_out'
//  3. Falls back to auto-booking the proposal (rather than leaving the member stranded)
//  4. Creates a rebooking_confirmed notification explaining the timeout
func RunApprovalTimeoutTicker(ctx context.Context) {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	log.Println("Approval timeout ticker started (checking every 60s)")

	for {
		select {
		case <-ctx.Done():
			log.Println("Approval timeout ticker stopping")
			return
		case <-ticker.C:
			checkExpiredApprovals(ctx)
		}
	}
}

func checkExpiredApprovals(ctx context.Context) {
	rows, err := db.Pool.Query(ctx,
		`SELECT a.id, a.agent_proposal_id, ap.proposed_flight_segment, ap.proposed_hotel_booking, ap.job_id
		 FROM approvals a
		 JOIN agent_proposals ap ON a.agent_proposal_id = ap.id
		 WHERE a.status = 'pending' AND a.expires_at < now()`)
	if err != nil {
		log.Printf("Error checking expired approvals: %v", err)
		return
	}
	defer rows.Close()

	for rows.Next() {
		var approvalID, proposalID, jobID string
		var proposedFlight, proposedHotel json.RawMessage
		if err := rows.Scan(&approvalID, &proposalID, &proposedFlight, &proposedHotel, &jobID); err != nil {
			log.Printf("Error scanning expired approval: %v", err)
			continue
		}

		log.Printf("Approval %s has expired, auto-booking fallback...", approvalID)
		handleExpiredApproval(ctx, approvalID, proposalID, proposedFlight, proposedHotel, jobID)
	}
}

func handleExpiredApproval(ctx context.Context, approvalID, proposalID string, proposedFlight, proposedHotel json.RawMessage, jobID string) {
	tx, err := db.Pool.Begin(ctx)
	if err != nil {
		log.Printf("Failed to begin transaction for expired approval: %v", err)
		return
	}
	defer tx.Rollback(ctx)

	now := time.Now().UTC()

	// 1. Set approval status to timed_out (compare-and-swap)
	tag, err := tx.Exec(ctx,
		"UPDATE approvals SET status = 'timed_out', responded_at = $1 WHERE id = $2 AND status = 'pending'",
		now, approvalID)
	if err != nil {
		log.Printf("Failed to update expired approval: %v", err)
		return
	}
	if tag.RowsAffected() == 0 {
		// another instance already claimed this approval — nothing to do
		return
	}

	// 2. Set agent_proposals status to timed_out
	_, err = tx.Exec(ctx,
		"UPDATE agent_proposals SET status = 'timed_out' WHERE id = $1",
		proposalID)
	if err != nil {
		log.Printf("Failed to update proposal status: %v", err)
		return
	}

	// 3. Execute the mock booking (which includes parsing, mock API calls, and flight segment update)
	flightNum, err := booking.ExecuteProposedBooking(ctx, tx, jobID, proposedFlight, proposedHotel)

	// 4. Create notification explaining the timeout and auto-booking
	var message string
	if err != nil {
		message = "Your approval window expired, and we encountered an issue trying to automatically rebook you. We're still working on rebooking you and will follow up shortly."
	} else {
		message = fmt.Sprintf("Your approval window has expired. To avoid leaving you stranded, we've automatically rebooked you on %s. Contact us if you need changes.", flightNum)
	}

	// 5. Find the user for notification
	var userID string
	err = tx.QueryRow(ctx,
		`SELECT i.user_id
		 FROM jobs j
		 JOIN disruption_events de ON j.disruption_event_id = de.id
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 WHERE j.id = $1`, jobID,
	).Scan(&userID)
	if err == nil {
		_, _ = db.InsertNotification(ctx, tx, userID, "rebooking_confirmed", message)
	} else {
		log.Printf("Failed to find user for timeout notification: %v", err)
	}

	if err := tx.Commit(ctx); err != nil {
		log.Printf("Failed to commit expired approval handling: %v", err)
	} else {
		log.Printf("Handled expired approval %s: timed out + auto-rebooked", approvalID)
	}
}
