package mockapi

import (
	"context"
	"fmt"
	"math/rand"
	"net/http"
	"sync"

	"github.com/google/uuid"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

var (
	forceHotelFailure bool
	hotelFailureMu    sync.Mutex
)

// BookHotelOrder handles POST /mock/v1/booking/hotel-orders.
// Per §6.1, mirrors a simplified hotel booking flow.
func BookHotelOrder(w http.ResponseWriter, r *http.Request) {
	var req models.MockHotelOrderRequest
	if !validation.DecodeAndValidate(w, r, &req) {
		return
	}

	ctx := r.Context()

	// Verify UserID and CardToken
	var validUser string
	err := db.Pool.QueryRow(ctx, "SELECT id FROM users WHERE id = $1 AND card_token = $2", req.UserID, req.CardToken).Scan(&validUser)
	if err != nil {
		validation.WriteError(w, http.StatusBadRequest, "validation_error", "Invalid user_id or card_token.")
		return
	}

	reference, err := InternalBookHotel(ctx, db.Pool, req.UserID, req.CardToken, req.HotelID, req.TotalPrice)
	if err != nil {
		validation.WriteJSON(w, http.StatusUnprocessableEntity, models.MockHotelOrderResponse{
			BookingReference: nil,
			Status:           "failed",
		})
		return
	}

	validation.WriteJSON(w, http.StatusOK, models.MockHotelOrderResponse{
		BookingReference: &reference,
		Status:           "confirmed",
	})
}

// ForceNextHotelFailure handles POST /mock/v1/booking/force-next-hotel-failure.
func ForceNextHotelFailure(w http.ResponseWriter, r *http.Request) {
	hotelFailureMu.Lock()
	forceHotelFailure = true
	hotelFailureMu.Unlock()

	validation.WriteJSON(w, http.StatusOK, map[string]string{
		"message": "Next hotel booking will fail.",
	})
}

// InternalBookHotel performs the core hotel booking logic without HTTP.
func InternalBookHotel(ctx context.Context, ex db.Execer, userID, cardToken, hotelID string, price float64) (string, error) {
	shouldFail := false
	hotelFailureMu.Lock()
	if forceHotelFailure {
		shouldFail = true
		forceHotelFailure = false
	}
	hotelFailureMu.Unlock()

	if !shouldFail && rand.Float64() < 0.10 {
		shouldFail = true
	}

	if shouldFail {
		// Write failed-booking audit row via db.Pool (NOT ex/tx) so it persists
		// even if the caller's transaction rolls back.
		_, _ = db.Pool.Exec(ctx,
			`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token)
			 VALUES ($1, 'hotel', '', $2, $3, 'failed', $4, $5)`,
			uuid.New().String(), hotelID, userID, price, cardToken)
		return "", fmt.Errorf("hotel booking failed")
	}

	reference := fmt.Sprintf("HTL%03d", rand.Intn(900)+100)

	_, err := ex.Exec(ctx,
		`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token)
		 VALUES ($1, 'hotel', $2, $3, $4, 'confirmed', $5, $6)`,
		uuid.New().String(), reference, hotelID, userID, price, cardToken)
	if err != nil {
		return "", fmt.Errorf("failed to insert mock hotel booking: %w", err)
	}

	return reference, nil
}
