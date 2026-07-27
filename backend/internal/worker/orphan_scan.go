package worker

import (
	"context"
	"log"
	"time"

	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/queue"
)

// RunOrphanDisruptionScanner periodically scans the database for disruption
// events that were recorded but never picked up by the worker (e.g. because
// the SQS publish failed). This acts as a self-healing mechanism so that
// no disruption is ever silently lost.
func RunOrphanDisruptionScanner(ctx context.Context) {
	// Run an initial scan immediately on startup, then every 30 seconds
	scanOrphanedDisruptions(ctx)

	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	log.Println("Orphan disruption scanner started (checking every 30s)")

	for {
		select {
		case <-ctx.Done():
			log.Println("Orphan disruption scanner stopping")
			return
		case <-ticker.C:
			scanOrphanedDisruptions(ctx)
		}
	}
}

// scanOrphanedDisruptions finds disruption_events that have no matching job
// and processes them directly via HandleMessage.
func scanOrphanedDisruptions(ctx context.Context) {
	rows, err := db.Pool.Query(ctx,
		`SELECT de.id
		 FROM disruption_events de
		 LEFT JOIN jobs j ON j.idempotency_key = 'disruption:' || de.id::text
		 WHERE j.id IS NULL`)
	if err != nil {
		log.Printf("Orphan scan: query error: %v", err)
		return
	}
	defer rows.Close()

	for rows.Next() {
		var disruptionID string
		if err := rows.Scan(&disruptionID); err != nil {
			log.Printf("Orphan scan: scan error: %v", err)
			continue
		}

		log.Printf("Orphan scan: found orphaned disruption %s — processing now", disruptionID)

		msg := queue.SQSMessage{
			DisruptionEventID: disruptionID,
			DetectedAt:        time.Now().UTC().Format(time.RFC3339),
		}

		if err := HandleMessage(ctx, msg, ""); err != nil {
			log.Printf("Orphan scan: failed to process disruption %s: %v", disruptionID, err)
		}
	}
}
