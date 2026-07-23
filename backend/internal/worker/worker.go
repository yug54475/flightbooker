package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
	"github.com/yug54475/flightbooker/internal/agentclient"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/insurance"
	"github.com/yug54475/flightbooker/internal/lounge"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/queue"
)

// HandleMessage processes a single SQS message per the worker flow in §4.
func HandleMessage(ctx context.Context, msg queue.SQSMessage, receiptHandle string) error {
	log.Printf("Processing disruption event: %s", msg.DisruptionEventID)

	// Step 1: Idempotency check (§4.1)
	idempotencyKey := fmt.Sprintf("disruption:%s", msg.DisruptionEventID)

	var existingJobID string
	err := db.Pool.QueryRow(ctx,
		"SELECT id FROM jobs WHERE idempotency_key = $1", idempotencyKey,
	).Scan(&existingJobID)
	if err == nil {
		log.Printf("Job already exists for disruption %s (job=%s), skipping", msg.DisruptionEventID, existingJobID)
		return nil // Already processed — SQS redelivery, safe to skip
	}

	// Step 2: Load disruption context from Postgres (single source of truth per §4.3)
	var (
		disruptionType string
		delayMinutes   *int
		segID          string
		flightNumber   string
		origin         string
		destination    string
		departureTime  time.Time
		arrivalTime    time.Time
		cabinClass     string
		loyaltyProgram *string
		originalPrice  *float64
		bookingRef     *string
		userID         string
		cardTier       string
		cardToken      *string
	)

	err = db.Pool.QueryRow(ctx,
		`SELECT de.type, de.delay_minutes,
		        fs.id, fs.flight_number, fs.origin, fs.destination,
		        fs.departure_time, fs.arrival_time, fs.cabin_class,
		        fs.loyalty_program, fs.original_price, fs.booking_reference,
		        u.id, u.card_tier, u.card_token
		 FROM disruption_events de
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 JOIN users u ON i.user_id = u.id
		 WHERE de.id = $1`, msg.DisruptionEventID,
	).Scan(
		&disruptionType, &delayMinutes,
		&segID, &flightNumber, &origin, &destination,
		&departureTime, &arrivalTime, &cabinClass,
		&loyaltyProgram, &originalPrice, &bookingRef,
		&userID, &cardTier, &cardToken,
	)
	if err != nil {
		return fmt.Errorf("failed to load disruption context: %w", err)
	}

	// Step 3: Create job row (status=processing)
	jobID := uuid.New().String()
	_, err = db.Pool.Exec(ctx,
		`INSERT INTO jobs (id, disruption_event_id, idempotency_key, status, attempts, created_at, updated_at)
		 VALUES ($1, $2, $3, 'processing', 1, $4, $4)`,
		jobID, msg.DisruptionEventID, idempotencyKey, time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to create job: %w", err)
	}

	// Step 4: Run insurance check (independent of confidence score, per §9)
	go func() {
		insCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := insurance.CheckEligibility(insCtx, msg.DisruptionEventID, userID, cardTier, disruptionType, delayMinutes); err != nil {
			log.Printf("Insurance check failed: %v", err)
		}
	}()

	// Step 5: Call AI agent (§4.4)
	agentReq := models.AgentPlanRequest{
		DisruptionEvent: models.AgentDisruptionPayload{
			ID:           msg.DisruptionEventID,
			Type:         disruptionType,
			DelayMinutes: delayMinutes,
			FlightSegment: models.AgentFlightSegPayload{
				ID:               segID,
				FlightNumber:     flightNumber,
				Origin:           origin,
				Destination:      destination,
				DepartureTime:    departureTime.Format(time.RFC3339),
				ArrivalTime:      arrivalTime.Format(time.RFC3339),
				CabinClass:       cabinClass,
				LoyaltyProgram:   loyaltyProgram,
				OriginalPrice:    originalPrice,
				BookingReference: bookingRef,
			},
			User: models.AgentUserPayload{
				ID:             userID,
				CardTier:       cardTier,
				CardToken:      cardToken,
				LoyaltyProgram: loyaltyProgram,
			},
		},
	}

	agentResp, err := agentclient.CallAgent(ctx, agentReq)
	if err != nil {
		// Mark job as failed and send reassurance notification (§4.2)
		failJob(ctx, jobID, err.Error())
		sendReassurance(ctx, userID)
		return fmt.Errorf("agent call failed after retries: %w", err)
	}

	// Step 6: Determine status based on confidence score (§7)
	proposalStatus := "pending_approval"
	if agentResp.ConfidenceScore > 0.9 {
		proposalStatus = "auto_approved"
	}

	// Step 7: Check lounge access if airport changed (§10)
	reasoningSteps := agentResp.ReasoningSteps
	var proposedDestination string
	if agentResp.ProposedFlightSegment != nil {
		var seg map[string]interface{}
		if json.Unmarshal(agentResp.ProposedFlightSegment, &seg) == nil {
			if dest, ok := seg["destination"].(string); ok {
				proposedDestination = dest
			}
			// Check for reroute through different airport
			if proposedOrigin, ok := seg["origin"].(string); ok && proposedOrigin != origin {
				loungeResult := lounge.CheckAccess(ctx, cardTier, proposedOrigin)
				reasoningSteps = lounge.AppendLoungeToReasoningSteps(reasoningSteps, loungeResult)
			}
			if proposedDestination != "" && proposedDestination != destination {
				loungeResult := lounge.CheckAccess(ctx, cardTier, proposedDestination)
				reasoningSteps = lounge.AppendLoungeToReasoningSteps(reasoningSteps, loungeResult)
			}
		}
	}

	// Step 8: Store agent_proposals row
	proposalID := uuid.New().String()
	_, err = db.Pool.Exec(ctx,
		`INSERT INTO agent_proposals (id, job_id, proposed_flight_segment, proposed_hotel_booking,
		                              confidence_score, reasoning_steps, status, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		proposalID, jobID,
		agentResp.ProposedFlightSegment, agentResp.ProposedHotelBooking,
		agentResp.ConfidenceScore, reasoningSteps,
		proposalStatus, time.Now().UTC())
	if err != nil {
		failJob(ctx, jobID, "failed to store proposal: "+err.Error())
		return fmt.Errorf("failed to store agent proposal: %w", err)
	}

	// Step 9: Handle based on status
	if proposalStatus == "auto_approved" {
		// Create rebooking_confirmed notification
		flightNum := extractFlightNumber(agentResp.ProposedFlightSegment, flightNumber)
		notifID := uuid.New().String()
		message := fmt.Sprintf("You've been automatically rebooked on %s. Confidence: %.0f%%.", flightNum, agentResp.ConfidenceScore*100)

		if loungeResult := lounge.CheckAccess(ctx, cardTier, proposedDestination); loungeResult != nil && loungeResult.HasAccess {
			message += " " + loungeResult.Message
		}

		_, _ = db.Pool.Exec(ctx,
			`INSERT INTO notifications (id, user_id, type, message, channel, sent_at)
			 VALUES ($1, $2, 'rebooking_confirmed', $3, 'push', $4)`,
			notifID, userID, message, time.Now().UTC())

	} else {
		// Create approval row with 30-minute expiry (§7.1)
		approvalID := uuid.New().String()
		now := time.Now().UTC()
		expiresAt := now.Add(30 * time.Minute)

		_, err = db.Pool.Exec(ctx,
			`INSERT INTO approvals (id, agent_proposal_id, status, expires_at)
			 VALUES ($1, $2, 'pending', $3)`,
			approvalID, proposalID, expiresAt)
		if err != nil {
			log.Printf("Warning: failed to create approval row: %v", err)
		}

		// Create approval_request notification
		flightNum := extractFlightNumber(agentResp.ProposedFlightSegment, flightNumber)
		notifID := uuid.New().String()
		message := fmt.Sprintf("We've found an alternative flight %s. Confidence: %.0f%%. Please review and approve within 30 minutes.", flightNum, agentResp.ConfidenceScore*100)
		_, _ = db.Pool.Exec(ctx,
			`INSERT INTO notifications (id, user_id, type, message, channel, sent_at)
			 VALUES ($1, $2, 'approval_request', $3, 'push', $4)`,
			notifID, userID, message, time.Now().UTC())
	}

	// Step 10: Mark job as completed
	_, _ = db.Pool.Exec(ctx,
		"UPDATE jobs SET status = 'completed', updated_at = $1 WHERE id = $2",
		time.Now().UTC(), jobID)

	log.Printf("Successfully processed disruption %s → job %s, status=%s, confidence=%.3f",
		msg.DisruptionEventID, jobID, proposalStatus, agentResp.ConfidenceScore)

	return nil
}

// failJob marks a job as failed with the given error.
func failJob(ctx context.Context, jobID, errMsg string) {
	_, _ = db.Pool.Exec(ctx,
		"UPDATE jobs SET status = 'failed', last_error = $1, updated_at = $2 WHERE id = $3",
		errMsg, time.Now().UTC(), jobID)
}

// sendReassurance creates a reassurance notification per §4.2.
func sendReassurance(ctx context.Context, userID string) {
	notifID := uuid.New().String()
	message := "We're still working on rebooking you — you won't be charged extra and we'll follow up shortly."
	_, _ = db.Pool.Exec(ctx,
		`INSERT INTO notifications (id, user_id, type, message, channel, sent_at)
		 VALUES ($1, $2, 'reassurance', $3, 'push', $4)`,
		notifID, userID, message, time.Now().UTC())
}

// extractFlightNumber tries to get the flight number from the proposed segment JSON.
func extractFlightNumber(data json.RawMessage, fallback string) string {
	if data == nil {
		return fallback
	}
	var seg map[string]interface{}
	if json.Unmarshal(data, &seg) == nil {
		if fn, ok := seg["flight_number"].(string); ok {
			return fn
		}
	}
	return fallback
}
