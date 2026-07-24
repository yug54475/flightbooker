package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

// GetAgentProposal handles GET /v1/agent-proposals/:job_id.
func GetAgentProposal(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "job_id")

	ctx := r.Context()

	callerID, ok := auth.GetUserID(ctx)
	if !ok {
		validation.WriteError(w, http.StatusUnauthorized, "unauthorized", "Could not identify caller.")
		return
	}

	var proposal models.AgentProposal
	err := db.Pool.QueryRow(ctx,
		`SELECT ap.id, ap.job_id, ap.proposed_flight_segment, ap.proposed_hotel_booking,
		        ap.confidence_score, ap.reasoning_steps, ap.status, ap.created_at
		 FROM agent_proposals ap
		 JOIN jobs j ON ap.job_id = j.id
		 JOIN disruption_events de ON j.disruption_event_id = de.id
		 JOIN flight_segments fs ON de.flight_segment_id = fs.id
		 JOIN itineraries i ON fs.itinerary_id = i.id
		 WHERE ap.job_id = $1 AND i.user_id = $2`, jobID, callerID,
	).Scan(
		&proposal.ID, &proposal.JobID,
		&proposal.ProposedFlightSegment, &proposal.ProposedHotelBooking,
		&proposal.ConfidenceScore, &proposal.ReasoningSteps,
		&proposal.Status, &proposal.CreatedAt,
	)
	if err != nil {
		validation.WriteError(w, http.StatusNotFound, "not_found", "No proposal found for this job_id.")
		return
	}

	// Check if there's a pending approval for this proposal
	var approvalID *string
	_ = db.Pool.QueryRow(ctx,
		"SELECT id FROM approvals WHERE agent_proposal_id = $1",
		proposal.ID,
	).Scan(&approvalID)
	proposal.ApprovalID = approvalID

	// Build response matching §3.3 shape
	resp := map[string]interface{}{
		"confidence_score":        proposal.ConfidenceScore,
		"status":                  proposal.Status,
		"proposed_flight_segment": proposal.ProposedFlightSegment,
		"proposed_hotel_booking":  proposal.ProposedHotelBooking,
		"reasoning_steps":         proposal.ReasoningSteps,
	}

	if approvalID != nil {
		resp["approval_id"] = *approvalID
	}

	validation.WriteJSON(w, http.StatusOK, resp)
}
