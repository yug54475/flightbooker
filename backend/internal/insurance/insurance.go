package insurance

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
	"github.com/yug54475/flightbooker/internal/db"
)

// CheckEligibility evaluates insurance eligibility per §9 rules and writes to insurance_claims.
// Called by the worker right after a disruption_events row is created — independent of confidence score.
//
// Rules:
//   premium: delay >6hrs → $500 (delay); cancellation → $10,000 (cancellation)
//   mid:     delay >12hrs → $300 (delay only); NO cancellation coverage
//   entry:   never eligible
//
// Always inserts a row (even if not eligible) so GET /v1/insurance-claims has something to return.
func CheckEligibility(ctx context.Context, disruptionEventID, userID, cardTier, disruptionType string, delayMinutes *int) error {
	eligible := false
	var claimType *string
	var amount *float64
	status := "not_eligible"

	switch cardTier {
	case "premium":
		switch disruptionType {
		case "cancelled", "missed_connection":
			eligible = true
			ct := "cancellation"
			claimType = &ct
			a := 10000.00
			amount = &a
			status = "eligible"
		case "delayed":
			if delayMinutes != nil && *delayMinutes > 360 { // strictly greater than 6 hours
				eligible = true
				ct := "delay"
				claimType = &ct
				a := 500.00
				amount = &a
				status = "eligible"
			}
		}

	case "mid":
		// Mid tier has delay coverage ONLY — no cancellation coverage
		if disruptionType == "delayed" && delayMinutes != nil && *delayMinutes > 720 { // strictly greater than 12 hours
			eligible = true
			ct := "delay"
			claimType = &ct
			a := 300.00
			amount = &a
			status = "eligible"
		}
		// cancelled/missed_connection → NOT eligible for mid tier (common misread per §9)

	case "entry":
		// Never eligible — still insert row with eligible=false for audit completeness
	}

	claimID := uuid.New().String()
	_, err := db.Pool.Exec(ctx,
		`INSERT INTO insurance_claims (id, disruption_event_id, user_id, eligible, claim_type, amount, status, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		claimID, disruptionEventID, userID, eligible, claimType, amount, status, time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to insert insurance claim: %w", err)
	}

	// If eligible, create a notification so the member hears about it immediately (§9)
	if eligible {
		notifID := uuid.New().String()
		var message string
		if claimType != nil {
			switch *claimType {
			case "cancellation":
				message = fmt.Sprintf("You may be eligible for trip cancellation insurance coverage of $%.2f. We'll follow up with details.", *amount)
			case "delay":
				message = fmt.Sprintf("You may be eligible for flight delay insurance coverage of $%.2f. We'll follow up with details.", *amount)
			}
		}

		_, err = db.Pool.Exec(ctx,
			`INSERT INTO notifications (id, user_id, type, message, channel, sent_at)
			 VALUES ($1, $2, 'insurance_eligible', $3, 'push', $4)`,
			notifID, userID, message, time.Now().UTC())
		if err != nil {
			log.Printf("Warning: failed to create insurance notification: %v", err)
			// Non-fatal — the claim itself was already recorded
		}
	}

	log.Printf("Insurance check: user=%s tier=%s type=%s eligible=%v", userID, cardTier, disruptionType, eligible)
	return nil
}
