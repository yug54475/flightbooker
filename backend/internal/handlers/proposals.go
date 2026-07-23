package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/models"
	"github.com/yug54475/flightbooker/internal/validation"
)

// GetAgentProposal handles GET /v1/agent-proposals/:job_id.
func GetAgentProposal(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "job_id")

	ctx := r.Context()

	var proposal models.AgentProposal
	err := db.Pool.QueryRow(ctx,
		`SELECT ap.id, ap.job_id, ap.proposed_flight_segment, ap.proposed_hotel_booking,
		        ap.confidence_score, ap.reasoning_steps, ap.status, ap.created_at
		 FROM agent_proposals ap
		 WHERE ap.job_id = $1`, jobID,
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
