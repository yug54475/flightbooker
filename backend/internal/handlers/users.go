package handlers

import (
	"net/http"

	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

// GetMe handles GET /v1/users/me.
func GetMe(w http.ResponseWriter, r *http.Request) {
	userID, ok := auth.GetUserID(r.Context())
	if !ok {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Could not identify caller.")
		return
	}

	var user models.User
	err := db.Pool.QueryRow(r.Context(),
		"SELECT id, name, email, card_tier FROM users WHERE id = $1", userID,
	).Scan(&user.ID, &user.Name, &user.Email, &user.CardTier)
	if err != nil {
		validation.WriteError(w, http.StatusNotFound, "not_found", "User not found.")
		return
	}

	validation.WriteJSON(w, http.StatusOK, user)
}

// GetPolicy handles GET /v1/users/me/policy.
func GetPolicy(w http.ResponseWriter, r *http.Request) {
	userID, ok := auth.GetUserID(r.Context())
	if !ok {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Could not identify caller.")
		return
	}

	var policy models.UserPolicy
	err := db.Pool.QueryRow(r.Context(),
		"SELECT max_price_delta, allow_cabin_downgrade, max_hotel_price_delta FROM user_policies WHERE user_id = $1",
		userID,
	).Scan(&policy.MaxPriceDelta, &policy.AllowCabinDowngrade, &policy.MaxHotelPriceDelta)
	if err != nil {
		validation.WriteError(w, http.StatusNotFound, "not_found", "Policy not found for this user.")
		return
	}

	validation.WriteJSON(w, http.StatusOK, policy)
}

// UpdatePolicy handles PATCH /v1/users/me/policy.
func UpdatePolicy(w http.ResponseWriter, r *http.Request) {
	userID, ok := auth.GetUserID(r.Context())
	if !ok {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Could not identify caller.")
		return
	}

	var req models.PolicyUpdateRequest
	if !validation.DecodeAndValidate(w, r, &req) {
		return
	}

	ctx := r.Context()

	// Load current policy
	var policy models.UserPolicy
	err := db.Pool.QueryRow(ctx,
		"SELECT max_price_delta, allow_cabin_downgrade, max_hotel_price_delta FROM user_policies WHERE user_id = $1",
		userID,
	).Scan(&policy.MaxPriceDelta, &policy.AllowCabinDowngrade, &policy.MaxHotelPriceDelta)
	if err != nil {
		validation.WriteError(w, http.StatusNotFound, "not_found", "Policy not found for this user.")
		return
	}

	// Apply partial updates
	if req.MaxPriceDelta != nil {
		policy.MaxPriceDelta = *req.MaxPriceDelta
	}
	if req.AllowCabinDowngrade != nil {
		policy.AllowCabinDowngrade = *req.AllowCabinDowngrade
	}
	if req.MaxHotelPriceDelta != nil {
		policy.MaxHotelPriceDelta = *req.MaxHotelPriceDelta
	}

	_, err = db.Pool.Exec(ctx,
		`UPDATE user_policies
		 SET max_price_delta = $1, allow_cabin_downgrade = $2, max_hotel_price_delta = $3, updated_at = now()
		 WHERE user_id = $4`,
		policy.MaxPriceDelta, policy.AllowCabinDowngrade, policy.MaxHotelPriceDelta, userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to update policy.")
		return
	}

	validation.WriteJSON(w, http.StatusOK, policy)
}
