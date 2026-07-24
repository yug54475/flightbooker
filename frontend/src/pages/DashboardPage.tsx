import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../store/auth';
import { getItineraries, getDisruptions, simulateDisruption } from '../api/endpoints';
import { useToast } from '../store/toast';
import { FlightCard } from '../components/FlightCard';
import { HotelCard } from '../components/HotelCard';
import { ItineraryStatusBadge, DisruptionTypeBadge, ProposalStatusBadge } from '../components/ui/Badge';
import { LoadingCenter } from '../components/ui/Spinner';
import { DataErrorState } from '../components/ui/DataState';
import { fmtDate, fmtDisruptionType } from '../utils/formatters';
import type { Itinerary, DisruptionEvent, AgentProposal, FlightSegment } from '../types';
import { useProposalPolling } from '../hooks/useProposalPolling';

// -----------------------------------------------------------------------
// Dashboard — shows all itineraries; disrupted ones get a proposal overlay
// -----------------------------------------------------------------------
export function DashboardPage() {
  const { token, userId, user } = useAuth();
  const { showError, showSuccess } = useToast();
  const navigate = useNavigate();

  const {
    data: itineraries,
    isLoading: loadingItin,
    error: itinerariesError,
    refetch: refetchItineraries,
  } = useQuery({
    queryKey: ['itineraries', userId],
    queryFn: () => getItineraries(userId!, token!),
    enabled: !!token && !!userId,
    refetchInterval: 30_000,
  });

  const {
    data: disruptions,
    error: disruptionsError,
    refetch: refetchDisruptions,
  } = useQuery({
    queryKey: ['disruptions', userId],
    queryFn: () => getDisruptions(userId!, token!),
    enabled: !!token && !!userId,
    refetchInterval: 10_000,
  });

  if (loadingItin) return <LoadingCenter label="Loading your trips…" />;

  if (itinerariesError) {
    return (
      <div className="page-container">
        <DataErrorState
          title="Your trips are temporarily unavailable"
          error={itinerariesError}
          onRetry={() => void refetchItineraries()}
        />
      </div>
    );
  }

  const trips = itineraries ?? [];

  return (
    <div className="page-container">
      <div className="page-header row-between">
        <div>
          <h1 className="page-title">
            {user ? `${user.name.split(' ')[0]}'s Trips` : 'Your Trips'}
          </h1>
          <p className="page-subtitle">
            {trips.length} {trips.length === 1 ? 'itinerary' : 'itineraries'} on file
          </p>
        </div>
      </div>

      {disruptionsError && (
        <div className="mb-6">
          <DataErrorState
            title="Disruption updates are temporarily unavailable"
            error={disruptionsError}
            onRetry={() => void refetchDisruptions()}
          />
        </div>
      )}

      {trips.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon mono">TRIP</div>
          <div className="empty-state-title">No trips on file</div>
          <p className="empty-state-desc">
            Trip data is seeded server-side. Make sure the backend is running with seed data applied.
          </p>
        </div>
      )}

      <div className="stack">
        {trips.map((itin) => {
          const relatedDisruption = disruptions?.find((d) =>
            itin.flight_segments.some((seg) => seg.id === d.flight_segment.id),
          );
          return (
            <ItineraryCard
              key={itin.id}
              itinerary={itin}
              disruption={relatedDisruption}
              token={token!}
              userId={userId!}
              onNavigateToDisruption={(jobId) => navigate(`/disruption/${jobId}`)}
              onAssignmentStarted={(eventId) =>
                navigate(`/disruption/event/${eventId}`)
              }
              onSimulateSuccess={showSuccess}
              onSimulateError={showError}
            />
          );
        })}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------
// Individual itinerary card
// -----------------------------------------------------------------------
interface ItineraryCardProps {
  itinerary: Itinerary;
  disruption?: DisruptionEvent;
  token: string;
  userId: string;
  onNavigateToDisruption: (jobId: string) => void;
  onAssignmentStarted: (eventId: string) => void;
  onSimulateSuccess: (msg: string) => void;
  onSimulateError: (msg: string) => void;
}

function ItineraryCard({
  itinerary,
  disruption,
  token,
  userId,
  onNavigateToDisruption,
  onAssignmentStarted,
  onSimulateSuccess,
  onSimulateError,
}: ItineraryCardProps) {
  const queryClient = useQueryClient();

  // For disrupted itineraries with a job_id, fetch the proposal to overlay
  const {
    data: proposal,
    error: proposalError,
    isNotReady,
    isTakingLonger,
  } = useProposalPolling(disruption?.job_id, token);

  const simulateMutation = useMutation({
    mutationFn: (segmentId: string) =>
      simulateDisruption({ flight_segment_id: segmentId, type: 'cancelled' }, token),
    onSuccess: (data) => {
      onSimulateSuccess('Disruption detected. Your concierge is taking over.');
      queryClient.invalidateQueries({ queryKey: ['disruptions', userId] });
      queryClient.invalidateQueries({ queryKey: ['itineraries', userId] });
      onAssignmentStarted(data.disruption_event_id);
    },
    onError: (err: Error) => onSimulateError(err.message),
  });

  const cardClass = [
    'card',
    itinerary.status === 'disrupted' ? 'card-coral' : '',
    itinerary.status === 'resolved' ? 'card-teal' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={cardClass}>
      {/* Header */}
      <div className="row-between mb-4">
        <div className="row">
          <ItineraryStatusBadge status={itinerary.status} />
          {disruption && <DisruptionTypeBadge type={disruption.type} />}
        </div>
        <span
          className="mono"
          style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}
        >
          {itinerary.created_at ? fmtDate(itinerary.created_at) : ''}
        </span>
      </div>

      {/* Flight segments */}
      {itinerary.flight_segments.map((seg) => (
        <div key={seg.id} style={{ marginBottom: 'var(--space-4)' }}>
          <FlightCard
            segment={seg}
            strikethrough={
              seg.status === 'cancelled' &&
              itinerary.status === 'disrupted'
            }
          />

          {/* Disruption overlay — shows original vs proposed (§8.1) */}
          {disruption?.flight_segment.id === seg.id && (
            <DisruptionOverlay
              originalSeg={seg}
              proposal={proposal}
              proposalError={proposalError}
              proposalIsNotReady={isNotReady}
              isTakingLonger={isTakingLonger}
              disruption={disruption}
              onViewDecision={
                disruption.job_id
                  ? () => onNavigateToDisruption(disruption.job_id!)
                  : undefined
              }
            />
          )}

          {/* Simulate disruption control — only for scheduled flights */}
          {seg.status === 'scheduled' && !disruption && (
            <div style={{ marginTop: 'var(--space-3)' }}>
              <button
                className="simulate-btn"
                onClick={() => simulateMutation.mutate(seg.id)}
                disabled={simulateMutation.isPending}
                title="Demo: trigger a disruption event for this flight segment"
                id={`simulate-${seg.id}`}
              >
                {simulateMutation.isPending ? 'Simulating…' : 'DEMO · Simulate disruption'}
              </button>
            </div>
          )}
        </div>
      ))}

      {/* Hotels */}
      {itinerary.hotel_bookings.length > 0 && (
        <>
          <hr className="divider" />
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            {itinerary.hotel_bookings.map((h) => (
              <HotelCard key={h.id} hotel={h} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------
// Disruption overlay on a cancelled segment (§8.1)
// -----------------------------------------------------------------------
interface DisruptionOverlayProps {
  originalSeg: FlightSegment;
  proposal?: AgentProposal;
  proposalError: Error | null;
  proposalIsNotReady: boolean;
  isTakingLonger: boolean;
  disruption: DisruptionEvent;
  onViewDecision?: () => void;
}

function DisruptionOverlay({
  originalSeg,
  proposal,
  proposalError,
  proposalIsNotReady,
  isTakingLonger,
  disruption,
  onViewDecision,
}: DisruptionOverlayProps) {
  const proposed = proposal?.proposed_flight_segment;

  return (
    <div className="disruption-overlay">
      <div className="overlay-original">
        Original: {originalSeg.flight_number} — {fmtDisruptionType(disruption.type)}
      </div>

      {!disruption.job_id && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: 'var(--accent-amber)',
            fontSize: '0.875rem',
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: 'var(--accent-amber)',
              animation: 'pulse-dot 1.5s infinite',
              display: 'inline-block',
            }}
          />
          Detected — assigning to your concierge…
        </div>
      )}

      {disruption.job_id && !proposal && (!proposalError || proposalIsNotReady) && !isTakingLonger && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: 'var(--accent-amber)',
            fontSize: '0.875rem',
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: 'var(--accent-amber)',
              animation: 'pulse-dot 1.5s infinite',
              display: 'inline-block',
            }}
          />
          Agent is searching for alternatives…
        </div>
      )}

      {isTakingLonger && !proposed && (
        <div className="overlay-waiting">
          This search is taking longer than usual. Your concierge is still
          working; open the decision view for the latest timeline.
        </div>
      )}

      {proposalError && !proposalIsNotReady && !isTakingLonger && (
        <div className="overlay-error">
          Proposal updates could not be loaded right now.
        </div>
      )}

      {proposed && (
        <div className="overlay-new">
          <span style={{ color: 'var(--accent-teal)' }}>✓</span>
          <span>
            Now on: <span className="mono">{proposed.flight_number}</span>{' '}
            {proposed.origin} → {proposed.destination}
          </span>
          {proposal && <ProposalStatusBadge status={proposal.status} />}
        </div>
      )}

      {onViewDecision && (
        <button
          className="btn btn-ghost btn-sm"
          style={{ marginTop: '8px', paddingLeft: 0 }}
          onClick={onViewDecision}
          id={`view-decision-${disruption.id}`}
        >
          View full decision →
        </button>
      )}
    </div>
  );
}
