import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../store/auth';
import {
  getDisruptions,
  respondToApproval,
  getTimeline,
} from '../api/endpoints';
import { useToast } from '../store/toast';
import { ApiRequestError } from '../api/client';
import { ReasoningTrace } from '../components/ReasoningTrace';
import { FlightCard } from '../components/FlightCard';
import { HotelCard } from '../components/HotelCard';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';
import {
  ProposalStatusBadge,
  DisruptionTypeBadge,
} from '../components/ui/Badge';
import { DataErrorState } from '../components/ui/DataState';
import {
  fmtDateTime,
  fmtDisruptionType,
} from '../utils/formatters';
import type { AgentProposal } from '../types';
import { useProposalPolling } from '../hooks/useProposalPolling';

// -----------------------------------------------------------------------
// Disruption & Decision page (the signature page)
// Merges: disruption alert + reasoning trace + approve/decline
// -----------------------------------------------------------------------
export function DisruptionPage() {
  const { jobId: routeJobId, eventId } = useParams<{
    jobId?: string;
    eventId?: string;
  }>();
  const { token, userId } = useAuth();
  const { showError, showSuccess } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const assignmentStartedAt = useRef(Date.now());
  const [assignmentElapsed, setAssignmentElapsed] = useState(0);

  useEffect(() => {
    assignmentStartedAt.current = Date.now();
    setAssignmentElapsed(0);
    if (!eventId) return;

    const timer = window.setInterval(() => {
      setAssignmentElapsed(
        Math.floor((Date.now() - assignmentStartedAt.current) / 1_000),
      );
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [eventId]);

  // Phase A — poll every two seconds until the worker assigns a job.
  const {
    data: disruptions,
    error: disruptionsError,
    refetch: refetchDisruptions,
  } = useQuery({
    queryKey: ['disruptions', userId],
    queryFn: () => getDisruptions(userId!, token!),
    enabled: !!token && !!userId,
    retry: false,
    refetchInterval: (query) => {
      if (!eventId) return false;
      const current = query.state.data?.find((d) => d.id === eventId);
      return current?.job_id ? false : 2_000;
    },
  });
  const disruption = eventId
    ? disruptions?.find((d) => d.id === eventId)
    : disruptions?.find((d) => d.job_id === routeJobId);
  const activeJobId = routeJobId ?? disruption?.job_id ?? undefined;

  const {
    data: proposal,
    error: proposalError,
    refetch: refetchProposal,
    elapsedSeconds: proposalElapsed,
    isNotReady,
    isTakingLonger,
  } = useProposalPolling(activeJobId, token);

  useEffect(() => {
    if (eventId && disruption?.job_id) {
      navigate(`/disruption/${disruption.job_id}`, { replace: true });
    }
  }, [disruption?.job_id, eventId, navigate]);

  // Respond to approval
  const [responded, setResponded] = useState(false);
  const respondMutation = useMutation({
    mutationFn: ({ decision }: { decision: 'approved' | 'declined' }) =>
      respondToApproval(proposal!.approval_id!, { decision }, token!),
    onMutate: () => {
      setResponded(true);
    },
    onSuccess: (_, { decision }) => {
      showSuccess(
        decision === 'approved'
          ? 'Rebooking approved — your new flight is confirmed.'
          : 'Rebooking declined. Please contact support if you need assistance.',
      );
      queryClient.invalidateQueries({ queryKey: ['proposal', activeJobId] });
      queryClient.invalidateQueries({ queryKey: ['notifications', userId] });
      queryClient.invalidateQueries({ queryKey: ['disruptions', userId] });
      queryClient.invalidateQueries({ queryKey: ['itineraries', userId] });
    },
    onError: (err: Error) => {
      if (err instanceof ApiRequestError && err.status === 409) {
        // Already responded — just refresh
        queryClient.invalidateQueries({ queryKey: ['proposal', activeJobId] });
      } else {
        setResponded(false);
        showError(err.message);
      }
    },
  });

  // Timeline for fallback diagnostics
  const { data: timeline } = useQuery({
    queryKey: ['timeline', userId],
    queryFn: () => getTimeline(userId!, token!),
    enabled: isTakingLonger && !!token && !!userId,
  });

  if (!routeJobId && !eventId) {
    return (
      <div className="page-container">
        <div className="empty-state">
          <div className="empty-state-title">No job ID specified</div>
          <Link to="/dashboard" className="btn btn-secondary mt-4">
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Back nav */}
      <button
        className="btn btn-ghost btn-sm mb-6"
        onClick={() => navigate('/dashboard')}
        id="back-to-dashboard"
        style={{ paddingLeft: 0 }}
      >
        ← Dashboard
      </button>

      {/* Page header */}
      <div className="page-header">
        <div className="row mb-2">
          {disruption && (
            <DisruptionTypeBadge type={disruption.type} />
          )}
          {proposal && <ProposalStatusBadge status={proposal.status} />}
        </div>
        <h1 className="page-title">
          {disruption
            ? `${fmtDisruptionType(disruption.type)}: ${disruption.flight_segment.flight_number}`
            : 'Flight Disruption'}
        </h1>
        {disruption && (
          <p className="page-subtitle" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.875rem' }}>
            {disruption.flight_segment.origin} → {disruption.flight_segment.destination}
            {disruption.delay_minutes ? ` · ${disruption.delay_minutes} min delay` : ''}
          </p>
        )}
      </div>

      {/* Two-column layout on desktop */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.4fr)',
          gap: 'var(--space-6)',
          alignItems: 'start',
        }}
        className="disruption-grid"
      >
        {/* Left: Proposal + decision */}
        <div className="stack">
          {disruptionsError && (
            <DataErrorState
              title="We could not load this disruption"
              error={disruptionsError}
              onRetry={() => void refetchDisruptions()}
            />
          )}

          {/* Phase A: disruption recorded, waiting for worker assignment */}
          {eventId && !activeJobId && !disruptionsError && (
            <div className="card card-amber live-status-card" role="status">
              <span className="status-orbit" aria-hidden="true" />
              <div>
                <div className="live-status-kicker">Detected</div>
                <h2>Assigning your concierge</h2>
                <p>
                  The disruption is recorded. A specialist agent is being
                  assigned to search and evaluate alternatives.
                </p>
                <div className="live-status-meta mono">
                  {assignmentElapsed < 30
                    ? `${assignmentElapsed}s since detection`
                    : 'Still working on it — your disruption remains safely queued.'}
                </div>
              </div>
            </div>
          )}

          {/* Loading / not-ready state */}
          {activeJobId && !proposal && !isTakingLonger && (isNotReady || !proposalError) && (
            <div className="card card-amber" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
              <div style={{ marginBottom: 'var(--space-4)' }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    border: '3px solid var(--border-amber)',
                    borderTopColor: 'var(--accent-amber)',
                    animation: 'spin 0.8s linear infinite',
                  }}
                />
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                {proposalElapsed < 10
                  ? 'Your concierge is searching for alternatives…'
                  : proposalElapsed < 60
                  ? 'Evaluating options against your policy…'
                  : 'This is taking a bit longer than usual — still working…'}
              </p>
              <p
                className="mono"
                style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem', marginTop: '8px' }}
              >
                {proposalElapsed}s elapsed
              </p>
            </div>
          )}

          {proposalError && !isNotReady && (
            <DataErrorState
              title="Proposal updates are temporarily unavailable"
              error={proposalError}
              onRetry={() => void refetchProposal()}
            />
          )}

          {/* Timeout fallback */}
          {isTakingLonger && (
            <div className="card">
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 'var(--space-4)' }}>
                The agent is taking longer than expected. Here's what's happened so far:
              </p>
              {timeline && timeline.length > 0 && (
                <div className="timeline">
                  {timeline.slice(-5).map((entry, i) => (
                    <div key={i} className="timeline-item">
                      <div className="timeline-dot" />
                      <div className="timeline-content">
                        <div className="timeline-name">{entry.step_name}</div>
                        <div className="timeline-time">{fmtDateTime(entry.timestamp)}</div>
                        <div className="timeline-desc">{entry.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Proposal */}
          {proposal && (
            <ProposalPanel
              proposal={proposal}
              responded={responded}
              responding={respondMutation.isPending}
              onRespond={(d) => respondMutation.mutate({ decision: d })}
            />
          )}
        </div>

        {/* Right: Reasoning trace */}
        <div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--text-tertiary)',
              marginBottom: 'var(--space-3)',
            }}
          >
            Agent Reasoning
          </div>
          <ReasoningTrace
            steps={proposal?.reasoning_steps ?? []}
            isLive={!proposal && Boolean(activeJobId)}
          />
        </div>
      </div>

      {/* Responsive fix for narrow screens */}
      <style>{`
        @media (max-width: 800px) {
          .disruption-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

// -----------------------------------------------------------------------
// Proposal panel + decision controls
// -----------------------------------------------------------------------
interface ProposalPanelProps {
  proposal: AgentProposal;
  responded: boolean;
  responding: boolean;
  onRespond: (decision: 'approved' | 'declined') => void;
}

function ProposalPanel({ proposal, responded, responding, onRespond }: ProposalPanelProps) {
  const isActionable =
    proposal.status === 'pending_approval' && proposal.approval_id && !responded;

  return (
    <div className="stack">
      {/* Confidence score */}
      <div className="card">
        <ConfidenceBar score={proposal.confidence_score} />
      </div>

      {/* Proposed rebooking */}
      {proposal.proposed_flight_segment && (
        <div className="card">
          <div className="proposal-label">Proposed Flight</div>
          <FlightCard segment={proposal.proposed_flight_segment} />
        </div>
      )}

      {proposal.proposed_hotel_booking && (
        <div className="card">
          <div className="proposal-label">Proposed Hotel Change</div>
          <HotelCard hotel={proposal.proposed_hotel_booking} />
        </div>
      )}

      {/* Decision panel */}
      {isActionable && (
        <div className="decision-panel">
          <div className="row-between mb-4">
            <h3 style={{ fontSize: '1rem', margin: 0 }}>Your approval required</h3>
            <div className="countdown">30-minute response policy</div>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-4)' }}>
            Your concierge found this alternative and needs your go-ahead before booking.
            Respond within ~30 minutes — after that, it will book the best available option automatically.
          </p>
          <div className="decision-actions">
            <button
              id="approve-btn"
              className="btn btn-teal"
              onClick={() => onRespond('approved')}
              disabled={responding}
              style={{ flex: 1 }}
            >
              {responding ? 'Processing…' : '✓ Approve rebooking'}
            </button>
            <button
              id="decline-btn"
              className="btn btn-coral"
              onClick={() => onRespond('declined')}
              disabled={responding}
              style={{ flex: 1 }}
            >
              Decline
            </button>
          </div>
        </div>
      )}

      {/* Post-decision states */}
      <StatusNote proposal={proposal} responded={responded} />
    </div>
  );
}

function StatusNote({
  proposal,
  responded,
}: {
  proposal: AgentProposal;
  responded: boolean;
}) {
  if (proposal.status === 'auto_approved') {
    return (
      <div
        className="card card-teal"
        style={{ display: 'flex', alignItems: 'center', gap: '12px' }}
      >
        <span style={{ fontSize: '1.5rem' }}>✓</span>
        <div>
          <div style={{ fontWeight: 600, color: 'var(--accent-teal)', marginBottom: '4px' }}>
            Auto-approved & confirmed
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            Confidence was above 90%, so your concierge booked this automatically. Check your notifications
            for confirmation details.
          </p>
        </div>
      </div>
    );
  }

  if (proposal.status === 'approved' || (responded && proposal.status !== 'declined')) {
    return (
      <div
        className="card card-teal"
        style={{ display: 'flex', alignItems: 'center', gap: '12px' }}
      >
        <span style={{ fontSize: '1.5rem' }}>✓</span>
        <div>
          <div style={{ fontWeight: 600, color: 'var(--accent-teal)', marginBottom: '4px' }}>
            Approved — booking confirmed
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            Your new flight is booked. Check your notifications for the confirmation.
          </p>
        </div>
      </div>
    );
  }

  if (proposal.status === 'declined') {
    return (
      <div className="card status-declined">
        <div className="declined-note">
          <strong style={{ color: 'var(--accent-coral)' }}>Rebooking declined.</strong>{' '}
          No further automated action will be taken. If you need help finding an alternative,
          please contact your card's travel support line.
        </div>
      </div>
    );
  }

  if (proposal.status === 'timed_out') {
    return (
      <div className="card status-timed-out">
        <div className="timedout-note">
          <strong style={{ color: 'var(--text-primary)' }}>
            A decision was made on your behalf.
          </strong>{' '}
          You didn't respond within 30 minutes, so your concierge automatically booked the best
          available option to make sure you weren't left stranded. Check your notifications for
          what was booked.
        </div>
      </div>
    );
  }

  return null;
}
