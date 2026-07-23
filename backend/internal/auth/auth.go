package auth

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/yug54475/flightbooker/internal/models"
)

type contextKey string

const UserClaimsKey contextKey = "user_claims"

// Claims represents JWT claims.
type Claims struct {
	jwt.RegisteredClaims
}

// GenerateToken creates a signed JWT for the given user ID (24hr expiry).
func GenerateToken(userID string) (string, error) {
	secret := os.Getenv("JWT_SECRET")
	if secret == "" {
		return "", fmt.Errorf("JWT_SECRET is not set")
	}

	now := time.Now().UTC()
	claims := Claims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID,
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(24 * time.Hour)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(secret))
}

// AuthMiddleware validates the JWT on every request.
func AuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			writeError(w, http.StatusUnauthorized, "unauthorized", "Missing Authorization header.")
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			writeError(w, http.StatusUnauthorized, "unauthorized", "Invalid Authorization header format. Expected: Bearer <token>.")
			return
		}

		tokenStr := parts[1]
		secret := os.Getenv("JWT_SECRET")
		if secret == "" {
			writeError(w, http.StatusInternalServerError, "internal_error", "Server misconfiguration.")
			return
		}

		claims := &Claims{}
		token, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (interface{}, error) {
			if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
			}
			return []byte(secret), nil
		})

		if err != nil || !token.Valid {
			writeError(w, http.StatusUnauthorized, "unauthorized", "Invalid or expired token.")
			return
		}

		ctx := context.WithValue(r.Context(), UserClaimsKey, claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// GetUserID extracts the user ID from the context (set by AuthMiddleware).
func GetUserID(ctx context.Context) (string, bool) {
	claims, ok := ctx.Value(UserClaimsKey).(*Claims)
	if !ok {
		return "", false
	}
	return claims.Subject, true
}

// CheckOwnership verifies that the JWT subject matches the requested user_id.
// Returns a 403 error response if they don't match.
func CheckOwnership(w http.ResponseWriter, r *http.Request, requestedUserID string) bool {
	callerID, ok := GetUserID(r.Context())
	if !ok {
		writeError(w, http.StatusUnauthorized, "unauthorized", "Could not identify caller.")
		return false
	}
	if callerID != requestedUserID {
		writeError(w, http.StatusForbidden, "forbidden", "You are not authorized to access this resource.")
		return false
	}
	return true
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	resp := models.ErrorResponse{
		Error: models.ErrorDetail{
			Code:    code,
			Message: message,
		},
	}
	_ = encodeJSON(w, resp)
}

func encodeJSON(w http.ResponseWriter, v interface{}) error {
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	return enc.Encode(v)
}
