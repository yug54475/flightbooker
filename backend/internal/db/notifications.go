package db

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgconn"
)

// Execer is an interface for pgxpool.Pool and pgx.Tx to allow shared DB functions.
type Execer interface {
	Exec(ctx context.Context, sql string, arguments ...any) (pgconn.CommandTag, error)
}

// InsertNotification creates a new notification record.
func InsertNotification(ctx context.Context, ex Execer, userID, notifType, message string) (string, error) {
	id := uuid.New().String()
	_, err := ex.Exec(ctx,
		`INSERT INTO notifications (id, user_id, type, message, channel, sent_at)
		 VALUES ($1, $2, $3, $4, 'push', $5)`,
		id, userID, notifType, message, time.Now().UTC())
	return id, err
}
