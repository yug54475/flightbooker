import type { ProposalStatus, DisruptionType, FlightStatus, ItineraryStatus, InsuranceStatus } from '../../types';

type BadgeVariant = 'amber' | 'teal' | 'coral' | 'green' | 'muted';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  live?: boolean;
}

export function Badge({ variant = 'muted', children, live = false }: BadgeProps) {
  return (
    <span className={`badge badge-${variant}`}>
      {live && <span className="live-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function ProposalStatusBadge({ status }: { status: ProposalStatus }) {
  const map: Record<ProposalStatus, { label: string; variant: BadgeVariant; live?: boolean }> = {
    auto_approved:    { label: 'Auto-Approved', variant: 'teal' },
    pending_approval: { label: 'Awaiting Decision', variant: 'amber', live: true },
    approved:         { label: 'Approved', variant: 'green' },
    declined:         { label: 'Declined', variant: 'coral' },
    timed_out:        { label: 'Auto-Booked', variant: 'muted' },
  };
  const { label, variant, live } = map[status];
  return <Badge variant={variant} live={live}>{label}</Badge>;
}

export function DisruptionTypeBadge({ type }: { type: DisruptionType }) {
  const map: Record<DisruptionType, { label: string; variant: BadgeVariant }> = {
    cancelled:         { label: 'Cancelled', variant: 'coral' },
    delayed:           { label: 'Delayed', variant: 'amber' },
    missed_connection: { label: 'Missed Connection', variant: 'amber' },
  };
  const { label, variant } = map[type];
  return <Badge variant={variant}>{label}</Badge>;
}

export function FlightStatusBadge({ status }: { status: FlightStatus }) {
  const map: Record<FlightStatus, { label: string; variant: BadgeVariant }> = {
    scheduled: { label: 'Scheduled', variant: 'muted' },
    delayed:   { label: 'Delayed', variant: 'amber' },
    cancelled: { label: 'Cancelled', variant: 'coral' },
    rebooked:  { label: 'Rebooked', variant: 'teal' },
  };
  const { label, variant } = map[status];
  return <Badge variant={variant}>{label}</Badge>;
}

export function ItineraryStatusBadge({ status }: { status: ItineraryStatus }) {
  const map: Record<ItineraryStatus, { label: string; variant: BadgeVariant; live?: boolean }> = {
    active:    { label: 'Active', variant: 'teal' },
    disrupted: { label: 'Disrupted', variant: 'coral', live: true },
    resolved:  { label: 'Resolved', variant: 'green' },
  };
  const { label, variant, live } = map[status];
  return <Badge variant={variant} live={live}>{label}</Badge>;
}

export function InsuranceStatusBadge({ status }: { status: InsuranceStatus }) {
  const map: Record<InsuranceStatus, { label: string; variant: BadgeVariant }> = {
    not_eligible: { label: 'Not Eligible', variant: 'muted' },
    eligible:     { label: 'Eligible', variant: 'green' },
    initiated:    { label: 'Initiated', variant: 'amber' },
  };
  const { label, variant } = map[status];
  return <Badge variant={variant}>{label}</Badge>;
}
