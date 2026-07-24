import type { FlightSegment, ProposedFlightSegment } from '../types';
import { FlightStatusBadge } from './ui/Badge';
import { fmtTime, fmtDate, fmtPrice, fmtCabin } from '../utils/formatters';

interface FlightCardProps {
  segment: FlightSegment | ProposedFlightSegment;
  strikethrough?: boolean;
  compact?: boolean;
}

export function FlightCard({ segment, strikethrough = false, compact = false }: FlightCardProps) {
  return (
    <div className={`flight-card ${strikethrough ? 'flight-cancelled' : ''}`}>
      <div className="flight-route">
        <div className="flight-airport">
          <div className="airport-code mono-lg">{segment.origin}</div>
          <div className="airport-time mono">{fmtTime(segment.departure_time)}</div>
        </div>

        <div className="flight-line">
          <span className="flight-number mono">{segment.flight_number}</span>
          <div className="flight-track" />
          <span className="flight-cabin mono">{fmtCabin(segment.cabin_class)}</span>
        </div>

        <div className="flight-airport" style={{ textAlign: 'right' }}>
          <div className="airport-code mono-lg">{segment.destination}</div>
          <div className="airport-time mono">{fmtTime(segment.arrival_time)}</div>
        </div>
      </div>

      {!compact && (
        <div className="flight-meta">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {segment.status && <FlightStatusBadge status={segment.status} />}
            {segment.booking_reference && (
              <span className="flight-ref mono">REF: {segment.booking_reference}</span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
            {segment.original_price != null && (
              <span className="flight-price mono">{fmtPrice(segment.original_price)}</span>
            )}
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.7rem',
                color: 'var(--text-tertiary)',
              }}
            >
              {fmtDate(segment.departure_time)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
