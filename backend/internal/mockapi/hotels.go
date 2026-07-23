package mockapi

import (
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

	// Check forced failure or ~10% random failure rate
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

	ctx := r.Context()

	if shouldFail {
		// Insert failed booking record
		_, _ = db.Pool.Exec(ctx,
			`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token)
			 VALUES ($1, 'hotel', '', $2, $3, 'failed', 0, $4)`,
			uuid.New().String(), req.HotelID, req.UserID, req.CardToken)

		validation.WriteJSON(w, http.StatusUnprocessableEntity, models.MockHotelOrderResponse{
			BookingReference: nil,
			Status:           "failed",
		})
		return
	}

	// Success path
	reference := fmt.Sprintf("HTL%03d", rand.Intn(900)+100)

	_, err := db.Pool.Exec(ctx,
		`INSERT INTO mock_bookings (id, type, reference_code, external_offer_id, user_id, status, charged_amount, card_token, created_at)
		 VALUES ($1, 'hotel', $2, $3, $4, 'confirmed', 0, $5, $6)`,
		uuid.New().String(), reference, req.HotelID, req.UserID, req.CardToken, time.Now().UTC())
	if err != nil {
		fmt.Printf("Warning: failed to insert mock hotel booking: %v\n", err)
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
