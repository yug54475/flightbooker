package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

// GetItineraries handles GET /v1/itineraries/:user_id.
func GetItineraries(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "user_id")
	if !auth.CheckOwnership(w, r, userID) {
		return
	}

	ctx := r.Context()

	// Check user exists
	var exists bool
	err := db.Pool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)", userID).Scan(&exists)
	if err != nil || !exists {
		validation.WriteError(w, http.StatusNotFound, "not_found", "No itinerary found for this user_id.")
		return
	}

	// Load itineraries
	rows, err := db.Pool.Query(ctx,
		"SELECT id, user_id, status, created_at FROM itineraries WHERE user_id = $1 ORDER BY created_at DESC",
		userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load itineraries.")
		return
	}
	defer rows.Close()

	var itineraries []models.Itinerary
	for rows.Next() {
		var it models.Itinerary
		if err := rows.Scan(&it.ID, &it.UserID, &it.Status, &it.CreatedAt); err != nil {
			validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to scan itinerary.")
			return
		}
		it.FlightSegments = []models.FlightSegment{}
		it.HotelBookings = []models.HotelBooking{}
		itineraries = append(itineraries, it)
	}

	if itineraries == nil {
		itineraries = []models.Itinerary{}
	}

	// Load flight segments for each itinerary
	for i := range itineraries {
		segRows, err := db.Pool.Query(ctx,
			`SELECT id, flight_number, origin, destination, departure_time, arrival_time,
			        cabin_class, loyalty_program, status, original_price, booking_reference
			 FROM flight_segments WHERE itinerary_id = $1 ORDER BY departure_time`,
			itineraries[i].ID)
		if err != nil {
			validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load flight segments.")
			return
		}

		for segRows.Next() {
			var seg models.FlightSegment
			if err := segRows.Scan(
				&seg.ID, &seg.FlightNumber, &seg.Origin, &seg.Destination,
				&seg.DepartureTime, &seg.ArrivalTime, &seg.CabinClass,
				&seg.LoyaltyProgram, &seg.Status, &seg.OriginalPrice, &seg.BookingReference,
			); err != nil {
				segRows.Close()
				validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to scan flight segment.")
				return
			}
			itineraries[i].FlightSegments = append(itineraries[i].FlightSegments, seg)
		}
		segRows.Close()

		// Load hotel bookings for each itinerary
		htlRows, err := db.Pool.Query(ctx,
			`SELECT id, hotel_name, check_in, check_out, status, booking_reference
			 FROM hotel_bookings WHERE itinerary_id = $1 ORDER BY check_in`,
			itineraries[i].ID)
		if err != nil {
			validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load hotel bookings.")
			return
		}

		for htlRows.Next() {
			var hb models.HotelBooking
			if err := htlRows.Scan(
				&hb.ID, &hb.HotelName, &hb.CheckIn, &hb.CheckOut, &hb.Status, &hb.BookingReference,
			); err != nil {
				htlRows.Close()
				validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to scan hotel booking.")
				return
			}
			itineraries[i].HotelBookings = append(itineraries[i].HotelBookings, hb)
		}
		htlRows.Close()
	}

	validation.WriteJSON(w, http.StatusOK, itineraries)
}
