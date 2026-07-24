package booking

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/jackc/pgx/v5"
	"github.com/yug54475/flightbooker/internal/mockapi"
)

// ExecuteProposedBooking creates mock booking records and notifications,
// and updates the flight_segments status to 'rebooked'.
// This is used by auto-approval, manual approval, and timeout fallbacks.
func ExecuteProposedBooking(ctx context.Context, tx pgx.Tx, jobID string, proposedFlight, proposedHotel json.RawMessage) (string, error) {
	// Load user from job chain: proposal → job → disruption_event → flight_segment → itinerary → user
	var userID, cardToken, segmentID string
	err := tx.QueryRow(ctx,
		`SELECT u.id, COALESCE(u.card_token, ''), fs.id
		 FROM jobs j
		 JOIN disruption_events de ON j.disruption_event_id = de.id
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 JOIN users u ON i.user_id = u.id
		 WHERE j.id = $1`, jobID,
	).Scan(&userID, &cardToken, &segmentID)
	if err != nil {
		return "", fmt.Errorf("failed to load user/segment for booking: %w", err)
	}

	var externalFlightOfferID string
	var flightPrice float64 = 0
	flightNum := "alternative flight"
	var newBookingRef string = "MOCK-BK-AUTO"

	if proposedFlight != nil && string(proposedFlight) != "null" {
		var flightData map[string]interface{}
		if json.Unmarshal(proposedFlight, &flightData) == nil {
			if fn, ok := flightData["flight_number"].(string); ok {
				flightNum = fn
			}
			// Try multiple plausible field names for the offer identifier.
			// §4.5 uses booking_reference (set after agent pre-books on auto-approve),
			// but pending-approval proposals won't have one. Fall back to offer_id or id.
			for _, key := range []string{"booking_reference", "offer_id", "id"} {
				if ref, ok := flightData[key].(string); ok && ref != "" {
					externalFlightOfferID = ref
					break
				}
			}
			// §4.5 uses "original_price" to mean the new flight's price (semantic overload).
			// Also try "price" and "offer_price" in case the agent uses a clearer name.
			for _, key := range []string{"original_price", "price", "offer_price"} {
				if p, ok := flightData[key].(float64); ok {
					flightPrice = p
					break
				}
			}
		}
	}
	if externalFlightOfferID == "" {
		// No real offer ID available — use flight_number as a human-readable audit trail
		externalFlightOfferID = "offer:" + flightNum
	}

	var externalHotelOfferID string
	var hotelPrice float64 = 0
	if proposedHotel != nil && string(proposedHotel) != "null" {
		var hotelData map[string]interface{}
		if json.Unmarshal(proposedHotel, &hotelData) == nil {
			for _, key := range []string{"hotel_id", "booking_reference", "offer_id", "id"} {
				if ref, ok := hotelData[key].(string); ok && ref != "" {
					externalHotelOfferID = ref
					break
				}
			}
			if p, ok := hotelData["total_price"].(float64); ok {
				hotelPrice = p
			}
		}
	}
	if externalHotelOfferID == "" {
		externalHotelOfferID = "offer:hotel-unknown"
	}

	// Create mock bookings via the mockapi handlers
	_, flightRef, flightErr := mockapi.InternalBookFlight(ctx, tx, userID, cardToken, externalFlightOfferID, flightPrice)
	var hotelErr error
	if proposedHotel != nil && string(proposedHotel) != "null" {
		_, hotelErr = mockapi.InternalBookHotel(ctx, tx, userID, cardToken, externalHotelOfferID, hotelPrice)
	}

	if flightErr != nil {
		return flightNum, fmt.Errorf("failed to insert mock flight booking: %w", flightErr)
	}
	if flightRef != "" {
		newBookingRef = flightRef
	}
	if hotelErr != nil {
		// Hotel failure is non-fatal — the flight rebook is the primary action.
		// The failed hotel audit row was already persisted via db.Pool in InternalBookHotel.
		log.Printf("Warning: hotel booking failed (flight booking succeeded): %v", hotelErr)
	}

	// Update flight_segments status
	_, err = tx.Exec(ctx,
		"UPDATE flight_segments SET status = 'rebooked', booking_reference = $1 WHERE id = $2",
		newBookingRef, segmentID)
	if err != nil {
		return flightNum, fmt.Errorf("failed to update flight_segments: %w", err)
	}

	return flightNum, nil
}
