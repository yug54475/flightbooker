import type { HotelBooking, ProposedHotelBooking } from '../types';
import { fmtDate } from '../utils/formatters';

interface HotelCardProps {
  hotel: HotelBooking | ProposedHotelBooking;
}

const statusColor: Record<string, string> = {
  scheduled: 'var(--text-secondary)',
  changed: 'var(--accent-amber)',
  cancelled: 'var(--accent-coral)',
};

export function HotelCard({ hotel }: HotelCardProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: '8px',
          background: 'var(--bg-elevated)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.58rem',
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: 'var(--accent-teal)',
          flexShrink: 0,
        }}
        aria-hidden="true"
      >
        HTL
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontWeight: 600,
            fontSize: '0.9rem',
            color: 'var(--text-primary)',
            marginBottom: '4px',
          }}
        >
          {hotel.hotel_name ?? 'Hotel'}
        </div>
        {hotel.check_in && hotel.check_out && (
          <div
            className="mono"
            style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}
          >
            {fmtDate(hotel.check_in)} → {fmtDate(hotel.check_out)}
          </div>
        )}
        {hotel.booking_reference && (
          <div
            className="mono"
            style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem', marginTop: '2px' }}
          >
            REF: {hotel.booking_reference}
          </div>
        )}
      </div>
      {hotel.status && (
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: statusColor[hotel.status] ?? 'var(--text-tertiary)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            flexShrink: 0,
          }}
        >
          {hotel.status}
        </span>
      )}
    </div>
  );
}
