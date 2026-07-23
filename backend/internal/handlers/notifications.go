package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

// GetNotifications handles GET /v1/notifications/:user_id.
func GetNotifications(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "user_id")
	if !auth.CheckOwnership(w, r, userID) {
		return
	}

	ctx := r.Context()

	rows, err := db.Pool.Query(ctx,
		`SELECT id, type, message, channel, sent_at
		 FROM notifications
		 WHERE user_id = $1
		 ORDER BY sent_at DESC`, userID)
	if err != nil {
		validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to load notifications.")
		return
	}
	defer rows.Close()

	var notifications []models.Notification
	for rows.Next() {
		var n models.Notification
		if err := rows.Scan(&n.ID, &n.Type, &n.Message, &n.Channel, &n.SentAt); err != nil {
			validation.WriteError(w, http.StatusInternalServerError, "internal_error", "Failed to scan notification.")
			return
		}
		notifications = append(notifications, n)
	}

	if notifications == nil {
		notifications = []models.Notification{}
	}

	validation.WriteJSON(w, http.StatusOK, notifications)
}
