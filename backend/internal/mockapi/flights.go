package mockapi

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"net/http"
	"sync"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
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

	if req.Data.CardToken == "" {
		validation.WriteError(w, http.StatusBadRequest, "validation_error", "card_token is required.")
		return
	}

	if len(req.Data.Travelers) == 0 {
		validation.WriteError(w, http.StatusBadRequest, "validation_error", "travelers array cannot be empty.")
		return
	}

	offerID := extractOfferID(req.Data.FlightOffers)
	if offerID == "unknown-offer" {
		validation.WriteError(w, http.StatusBadRequest, "validation_error", "flightOffers must contain a valid offer.")
		return
	}

	ctx := r.Context()

	var userID string
	err := db.Pool.QueryRow(ctx,
		`SELECT id FROM users WHERE card_token = $1`, req.Data.CardToken,
	).Scan(&userID)
	if err != nil {
		validation.WriteError(w, http.StatusBadRequest, "validation_error", "Unknown card_token.")
		return
	}

	chargedAmount := extractPrice(req.Data.FlightOffers).InexactFloat64()
	orderID, reference, err := InternalBookFlight(ctx, db.Pool, userID, req.Data.CardToken, offerID, chargedAmount)
	if err != nil {
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

// InternalBookFlight performs the core flight booking logic without HTTP.
func InternalBookFlight(ctx context.Context, ex db.Execer, userID, cardToken, offerID string, chargedAmount float64) (string, string, error) {
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

	if shouldFail {
		bookingID := uuid.New().String()
		// Write failed-booking audit row via db.Pool (NOT ex/tx) so it persists
		// even if the caller's transaction rolls back. This is the whole point of
		// the audit row — recording that a booking was attempted and failed.
		_, _ = db.Pool.Exec(ctx,
			`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token)
			 VALUES ($1, 'flight', '', $2, $3, 'failed', 0, $4)`,
			bookingID, offerID, userID, cardToken)
		return "", "", fmt.Errorf("flight booking failed")
	}

	orderID := uuid.New().String()
	reference := fmt.Sprintf("MOCK-BK-%04d", rand.Intn(9000)+1000)

	_, err := ex.Exec(ctx,
		`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token)
		 VALUES ($1, 'flight', $2, $3, $4, 'confirmed', $5, $6)`,
		orderID, reference, offerID, userID, chargedAmount, cardToken)
	if err != nil {
		return "", "", fmt.Errorf("failed to insert mock_bookings row: %w", err)
	}

	return orderID, reference, nil
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
func extractPrice(data json.RawMessage) decimal.Decimal {
	if data == nil {
		return decimal.Zero
	}
	var offers []map[string]interface{}
	if err := json.Unmarshal(data, &offers); err == nil && len(offers) > 0 {
		if price, ok := offers[0]["price"].(map[string]interface{}); ok {
			if total, ok := price["total"].(string); ok {
				if d, err := decimal.NewFromString(total); err == nil {
					return d
				}
			}
		}
	}
	return decimal.Zero
}
