import { useToast } from '../../store/toast';

export function ToastSurface() {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" role="region" aria-label="Notifications" aria-live="polite">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`toast ${t.type === 'error' ? 'toast-error' : t.type === 'success' ? 'toast-success' : ''}`}
          role="alert"
        >
          <span style={{ fontSize: '1rem', flexShrink: 0 }}>
            {t.type === 'error' ? '⚠' : t.type === 'success' ? '✓' : 'ℹ'}
          </span>
          <span className="toast-msg">{t.message}</span>
          <button
            className="toast-close"
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
