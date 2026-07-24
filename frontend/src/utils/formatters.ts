// Utility formatters — dates, prices, IATA codes, confidence

/** Format ISO8601 to a readable date */
export function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

/** Format ISO8601 to HH:MM (24h) */
export function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return iso;
  }
}

/** Format ISO8601 to full datetime for display */
export function fmtDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return iso;
  }
}

/** Format a price with currency symbol */
export function fmtPrice(amount: number | null | undefined, currency = 'USD'): string {
  if (amount == null) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

/** Format confidence score as percentage */
export function fmtConfidence(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/** Return confidence tier for styling */
export function confidenceTier(score: number): 'high' | 'mid' | 'low' {
  if (score > 0.9) return 'high';
  if (score >= 0.7) return 'mid';
  return 'low';
}

/** Humanize a step_name like search_alternatives → Search Alternatives */
export function fmtStepName(name: string): string {
  return name
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/** Humanize cabin class */
export function fmtCabin(cabin: string): string {
  const map: Record<string, string> = {
    economy: 'Economy',
    premium_economy: 'Premium Economy',
    business: 'Business',
    first: 'First',
  };
  return map[cabin] ?? cabin;
}

/** Get initials from a name */
export function initials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

/** Humanize card tier */
export function fmtTier(tier: string): string {
  const map: Record<string, string> = {
    premium: 'Premium',
    mid: 'Mid-Tier',
    entry: 'Entry',
  };
  return map[tier] ?? tier;
}

/** Humanize disruption type */
export function fmtDisruptionType(type: string): string {
  const map: Record<string, string> = {
    cancelled: 'Cancelled',
    delayed: 'Delayed',
    missed_connection: 'Missed Connection',
  };
  return map[type] ?? type;
}

/** Humanize notification type */
export function fmtNotifType(type: string): string {
  const map: Record<string, string> = {
    disruption_alert: 'Disruption Alert',
    rebooking_confirmed: 'Rebooking Confirmed',
    approval_request: 'Approval Request',
    reassurance: 'Update',
    insurance_eligible: 'Insurance',
  };
  return map[type] ?? type;
}
