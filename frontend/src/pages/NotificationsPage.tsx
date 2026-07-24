import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../store/auth';
import { getNotifications } from '../api/endpoints';
import { NotificationItem } from '../components/NotificationItem';
import { LoadingCenter } from '../components/ui/Spinner';
import { DataErrorState } from '../components/ui/DataState';

export function NotificationsPage() {
  const { token, userId } = useAuth();

  const {
    data: notifications,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['notifications', userId],
    queryFn: () => getNotifications(userId!, token!),
    enabled: !!token && !!userId,
    refetchInterval: 30_000,
  });

  if (isLoading) return <LoadingCenter label="Loading notifications…" />;

  if (error) {
    return (
      <div className="page-container">
        <DataErrorState
          title="Notifications are temporarily unavailable"
          error={error}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const sorted = [...(notifications ?? [])].sort(
    (a, b) => new Date(b.sent_at).getTime() - new Date(a.sent_at).getTime(),
  );

  return (
    <div className="page-container">
      <div className="page-header row-between">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">
            {sorted.length} {sorted.length === 1 ? 'message' : 'messages'} — newest first
          </p>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon">◎</div>
          <div className="empty-state-title">No notifications yet</div>
          <p className="empty-state-desc">
            Alerts, rebooking confirmations, and approval requests will appear here.
          </p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {sorted.map((n) => (
            <NotificationItem key={n.id} notification={n} />
          ))}
        </div>
      )}
    </div>
  );
}
