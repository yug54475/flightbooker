package agentclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/yug54475/flightbooker/internal/models"
)

// CallAgent sends a plan request to the AI agent service and returns its response.
// Implements §4.2: 20s timeout, 2 retries with 2s backoff on timeout/5xx.
// Falls back to a mock response when the agent is unreachable.
func CallAgent(ctx context.Context, request models.AgentPlanRequest) (*models.AgentPlanResponse, error) {
	agentURL := os.Getenv("AGENT_SERVICE_URL")
	if agentURL == "" {
		agentURL = "http://localhost:8001"
	}
	endpoint := agentURL + "/agent/plan"

	body, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal agent request: %w", err)
	}

	var lastErr error
	maxAttempts := 3 // 1 initial + 2 retries

	for attempt := 1; attempt <= maxAttempts; attempt++ {
		if attempt > 1 {
			log.Printf("Retrying agent call (attempt %d/%d) after 2s backoff...", attempt, maxAttempts)
			select {
			case <-time.After(2 * time.Second):
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}

		resp, err := doAgentCall(ctx, endpoint, body)
		if err == nil {
			return resp, nil
		}
		lastErr = err
		log.Printf("Agent call attempt %d failed: %v", attempt, err)
	}

	// All retries exhausted — return error so caller can mark job as failed per §4.2
	return nil, fmt.Errorf("agent unreachable after %d attempts: %w", maxAttempts, lastErr)
}

func doAgentCall(ctx context.Context, endpoint string, body []byte) (*models.AgentPlanResponse, error) {
	// Create request with 20s timeout per §4.2
	callCtx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(callCtx, "POST", endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("agent call failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read agent response: %w", err)
	}

	// Retry on 5xx
	if resp.StatusCode >= 500 {
		return nil, fmt.Errorf("agent returned %d: %s", resp.StatusCode, string(respBody))
	}

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("agent returned unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var agentResp models.AgentPlanResponse
	if err := json.Unmarshal(respBody, &agentResp); err != nil {
		return nil, fmt.Errorf("failed to decode agent response: %w", err)
	}

	return &agentResp, nil
}

// generateMockAgentResponse creates a realistic fallback response when the agent is unavailable.
// This lets the backend work standalone for testing per the user's requirement.
func generateMockAgentResponse(request models.AgentPlanRequest) *models.AgentPlanResponse {
	log.Println("Generating mock agent response (agent service unavailable)")

	seg := request.DisruptionEvent.FlightSegment
	now := time.Now().UTC()

	// Create a mock proposed flight: same route, next day, same cabin
	mockDeparture := now.Add(12 * time.Hour)
	mockArrival := mockDeparture.Add(8 * time.Hour)

	// Increment the original price slightly for realism
	originalPrice := float64(0)
	if seg.OriginalPrice != nil {
		originalPrice = *seg.OriginalPrice
	}
	newPrice := originalPrice + 90.00

	proposedFlight := map[string]interface{}{
		"flight_number":     "MOCK-" + seg.FlightNumber,
		"origin":            seg.Origin,
		"destination":       seg.Destination,
		"departure_time":    mockDeparture.Format(time.RFC3339),
		"arrival_time":      mockArrival.Format(time.RFC3339),
		"cabin_class":       seg.CabinClass,
		"original_price":    newPrice,
		"booking_reference": fmt.Sprintf("MOCK-BK-%04d", now.UnixMilli()%10000),
	}

	reasoningSteps := []map[string]interface{}{
		{
			"step_name": "search_alternatives",
			"input":     fmt.Sprintf("%s-%s, %s, %s", seg.Origin, seg.Destination, mockDeparture.Format("2006-01-02"), seg.CabinClass),
			"output":    "3 options found (mock fallback)",
			"timestamp": now.Format(time.RFC3339),
		},
		{
			"step_name": "evaluate_cabin_match",
			"input":     "MOCK-" + seg.FlightNumber,
			"output":    "preserves " + seg.CabinClass + " class",
			"timestamp": now.Add(2 * time.Second).Format(time.RFC3339),
		},
		{
			"step_name": "compute_confidence",
			"input":     fmt.Sprintf("price_delta=+$90, cabin_match=1, loyalty_match=1, arrival_delta=moderate"),
			"output":    "0.91",
			"timestamp": now.Add(3 * time.Second).Format(time.RFC3339),
		},
	}

	flightJSON, _ := json.Marshal(proposedFlight)
	stepsJSON, _ := json.Marshal(reasoningSteps)

	return &models.AgentPlanResponse{
		ProposedFlightSegment: flightJSON,
		ProposedHotelBooking:  json.RawMessage("null"),
		ConfidenceScore:       0.91,
		ReasoningSteps:        stepsJSON,
	}
}
