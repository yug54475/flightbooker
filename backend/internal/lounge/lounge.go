package lounge

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/yug54475/flightbooker/internal/db"
)

// LoungeResult holds the outcome of a lounge access check.
type LoungeResult struct {
	HasAccess   bool   `json:"has_access"`
	AirportCode string `json:"airport_code"`
	LoungeType  string `json:"lounge_type,omitempty"`
	Message     string `json:"message,omitempty"`
}

// CheckAccess implements §10: only premium members get lounge access.
// Called when the agent's proposed flight reroutes through a different airport.
//
// Rule:
//   - card_tier != 'premium' → return false immediately (don't even query)
//   - Query airport_lounges for any row matching new_airport_code
//   - If found, return lounge info for reasoning_steps annotation
//
// This never blocks or gates a booking — purely additive information.
func CheckAccess(ctx context.Context, cardTier, newAirportCode string) *LoungeResult {
	if cardTier != "premium" {
		return &LoungeResult{
			HasAccess:   false,
			AirportCode: newAirportCode,
		}
	}

	var loungeType string
	err := db.Pool.QueryRow(ctx,
		"SELECT lounge_type FROM airport_lounges WHERE airport_code = $1 LIMIT 1",
		newAirportCode,
	).Scan(&loungeType)
	if err != nil {
		// No lounge found at this airport
		return &LoungeResult{
			HasAccess:   false,
			AirportCode: newAirportCode,
		}
	}

	loungeNames := map[string]string{
		"centurion":     "Centurion Lounge",
		"priority_pass": "Priority Pass Lounge",
	}
	loungeName := loungeNames[loungeType]
	if loungeName == "" {
		loungeName = "Airport Lounge"
	}

	return &LoungeResult{
		HasAccess:   true,
		AirportCode: newAirportCode,
		LoungeType:  loungeType,
		Message:     fmt.Sprintf("Your new airport, %s, has %s access with your card.", newAirportCode, loungeName),
	}
}

// AppendLoungeToReasoningSteps adds a lounge_check step to the reasoning_steps array
// if lounge access is available at the new airport.
func AppendLoungeToReasoningSteps(existingSteps json.RawMessage, result *LoungeResult) json.RawMessage {
	if result == nil || !result.HasAccess {
		return existingSteps
	}

	var steps []map[string]interface{}
	if existingSteps != nil && len(existingSteps) > 0 {
		if err := json.Unmarshal(existingSteps, &steps); err != nil {
			log.Printf("Warning: could not parse reasoning_steps for lounge annotation: %v", err)
			return existingSteps
		}
	}

	steps = append(steps, map[string]interface{}{
		"step_name": "lounge_check",
		"input":     result.AirportCode,
		"output":    result.Message,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})

	updated, err := json.Marshal(steps)
	if err != nil {
		log.Printf("Warning: could not marshal updated reasoning_steps: %v", err)
		return existingSteps
	}

	return updated
}
