package handlers

import (
	"fmt"
	"math/rand"
	"net/http"

	"github.com/google/uuid"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
	"golang.org/x/crypto/bcrypt"
)

// Signup handles POST /v1/auth/signup.
func Signup(w http.ResponseWriter, r *http.Request) {
	var req models.SignupRequest
	if !validation.DecodeAndValidate(w, r, &req) {
		return
	}

	ctx := r.Context()

	// Check if email already exists
	var exists bool
	err := db.Pool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM users WHERE email = $1)", req.Email).Scan(&exists)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Database error.")
		return
	}
	if exists {
		validation.WriteError(w, http.StatusConflict, "conflict", "Email is already registered.")
		return
	}

	// Hash password with bcrypt cost 12
	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), 12)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to hash password.")
		return
	}

	userID := uuid.New().String()
	cardToken := fmt.Sprintf("tok_demo_%s_%03d", req.CardTier, rand.Intn(900)+100)

	// Insert user and default policy in a transaction
	tx, err := db.Pool.Begin(ctx)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to begin transaction.")
		return
	}
	defer tx.Rollback(ctx)

	_, err = tx.Exec(ctx,
		`INSERT INTO users (id, name, email, card_tier, card_token, password_hash)
		 VALUES ($1, $2, $3, $4, $5, $6)`,
		userID, req.Name, req.Email, req.CardTier, cardToken, string(hash))
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to create user.")
		return
	}

	// Insert default policy row — a user must never exist without one (§7)
	_, err = tx.Exec(ctx,
		`INSERT INTO user_policies (user_id, max_price_delta, allow_cabin_downgrade, max_hotel_price_delta)
		 VALUES ($1, 150.00, false, 100.00)`,
		userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to create default policy.")
		return
	}

	if err := tx.Commit(ctx); err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to commit transaction.")
		return
	}

	// Generate JWT
	token, err := auth.GenerateToken(userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to generate token.")
		return
	}

	validation.WriteJSON(w, http.StatusCreated, models.AuthResponse{
		Token:  token,
		UserID: userID,
	})
}

// Login handles POST /v1/auth/login.
func Login(w http.ResponseWriter, r *http.Request) {
	var req models.LoginRequest
	if !validation.DecodeAndValidate(w, r, &req) {
		return
	}

	ctx := r.Context()

	var userID, passwordHash string
	err := db.Pool.QueryRow(ctx,
		"SELECT id, password_hash FROM users WHERE email = $1", req.Email,
	).Scan(&userID, &passwordHash)
	if err != nil {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Invalid email or password.")
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(passwordHash), []byte(req.Password)); err != nil {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Invalid email or password.")
		return
	}

	token, err := auth.GenerateToken(userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to generate token.")
		return
	}

	validation.WriteJSON(w, http.StatusOK, models.AuthResponse{
		Token:  token,
		UserID: userID,
	})
}


