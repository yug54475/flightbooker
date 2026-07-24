interface DataErrorStateProps {
  title?: string;
  error: unknown;
  onRetry?: () => void;
}

export function DataErrorState({
  title = 'We could not load this view',
  error,
  onRetry,
}: DataErrorStateProps) {
  const message =
    error instanceof Error
      ? error.message
      : 'Something went wrong. Please try again.';

  return (
    <div className="card data-error" role="alert">
      <div className="data-error-code" aria-hidden="true">!</div>
      <div>
        <h2 className="data-error-title">{title}</h2>
        <p className="data-error-message">{message}</p>
        {onRetry && (
          <button className="btn btn-secondary btn-sm mt-4" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
