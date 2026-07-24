interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

export function Spinner({ size = 'md', label = 'Loading…' }: SpinnerProps) {
  return (
    <span
      className={`spinner ${size === 'lg' ? 'spinner-lg' : ''}`}
      role="status"
      aria-label={label}
    />
  );
}

export function LoadingCenter({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="loading-center">
      <Spinner size="lg" label={label} />
      <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
        {label}
      </span>
    </div>
  );
}
