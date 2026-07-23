package mockapi

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"net/http"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

var (
	forceFlightFailure bool
	flightFailureMu    sync.Mutex
)

// BookFlightOrder handles POST /mock/v1/booking/flight-orders.
// Mirrors Amadeus Flight Create Orders per §5.1.
func BookFlightOrder(w http.ResponseWriter, r *http.Request) {
	var req models.MockFlightOrderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		validation.WriteError(w, http.StatusBadRequest, "validation_error", "Invalid JSON body: "+err.Error())
		return
	}

	if req.Data.Type != "flight-order" {
		validation.WriteError(w, http.StatusBadRequest, "validation_error", "data.type must be 'flight-order'.")
		return
	}

	// Check forced failure or ~10% random failure rate
	shouldFail := false
	flightFailureMu.Lock()
	if forceFlightFailure {
		shouldFail = true
		forceFlightFailure = false
	}
	flightFailureMu.Unlock()

	if !shouldFail && rand.Float64() < 0.10 {
		shouldFail = true
	}

	ctx := r.Context()

	if shouldFail {
		// Insert failed booking record
		bookingID := uuid.New().String()
		_, _ = db.Pool.Exec(ctx,
			`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token)
			 VALUES ($1, 'flight', '', $2, $3, 'failed', 0, $4)`,
			bookingID, extractOfferID(req.Data.FlightOffers), extractUserFromTravelers(req.Data.Travelers), req.Data.CardToken)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_ = json.NewEncoder(w).Encode(models.MockFlightOrderResponse{
			Data: models.MockFlightOrderResponseData{
				Type:      "flight-order",
				ID:        nil,
				Reference: nil,
				Status:    "failed",
			},
		})
		return
	}

	// Success path
	orderID := uuid.New().String()
	reference := fmt.Sprintf("MOCK-BK-%04d", rand.Intn(9000)+1000)
	offerID := extractOfferID(req.Data.FlightOffers)
	chargedAmount := extractPrice(req.Data.FlightOffers)

	_, err := db.Pool.Exec(ctx,
		`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token, created_at)
		 VALUES ($1, 'flight', $2, $3, $4, 'confirmed', $5, $6, $7)`,
		uuid.New().String(), reference, offerID, extractUserFromTravelers(req.Data.Travelers),
		chargedAmount, req.Data.CardToken, time.Now().UTC())
	if err != nil {
		fmt.Printf("Warning: failed to insert mock_bookings row: %v\n", err)
	}

	validation.WriteJSON(w, http.StatusOK, models.MockFlightOrderResponse{
		Data: models.MockFlightOrderResponseData{
			Type:      "flight-order",
			ID:        &orderID,
			Reference: &reference,
			Status:    "confirmed",
		},
	})
}

// ForceNextFlightFailure handles POST /mock/v1/booking/force-next-failure.
// Sets a flag so the next flight booking will fail — for demo reliability.
func ForceNextFlightFailure(w http.ResponseWriter, r *http.Request) {
	flightFailureMu.Lock()
	forceFlightFailure = true
	flightFailureMu.Unlock()

	validation.WriteJSON(w, http.StatusOK, map[string]string{
		"message": "Next flight booking will fail.",
	})
}

// extractOfferID tries to extract an offer ID from the flightOffers JSON array.
func extractOfferID(data json.RawMessage) string {
	if data == nil {
		return "unknown"
	}
	var offers []map[string]interface{}
	if err := json.Unmarshal(data, &offers); err == nil && len(offers) > 0 {
		if id, ok := offers[0]["id"].(string); ok {
			return id
		}
	}
	return "unknown-offer"
}

// extractPrice tries to extract a price from the flightOffers JSON.
func extractPrice(data json.RawMessage) float64 {
	if data == nil {
		return 0
	}
	var offers []map[string]interface{}
	if err := json.Unmarshal(data, &offers); err == nil && len(offers) > 0 {
		if price, ok := offers[0]["price"].(map[string]interface{}); ok {
			if total, ok := price["total"].(string); ok {
				var f float64
				fmt.Sscanf(total, "%f", &f)
				return f
			}
		}
	}
	return 0
}

// extractUserFromTravelers tries to get a user identifier from travelers.
// Falls back to a placeholder since mock bookings don't always have a real user_id in travelers.
func extractUserFromTravelers(data json.RawMessage) string {
	// In practice the agent passes the user_id separately via card_token lookup,
	// but we need a non-null value for the FK. The worker will set the real user_id.
	// Return a placeholder that the worker will overwrite.
	return "00000000-0000-0000-0000-000000000000"
}
