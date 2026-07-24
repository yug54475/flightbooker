import type { Notification } from '../types';
import { fmtDateTime, fmtNotifType } from '../utils/formatters';

const icons: Record<string, string> = {
  disruption_alert:    'ALRT',
  rebooking_confirmed: 'OK',
  approval_request:    'ASK',
  reassurance:         'INFO',
  insurance_eligible:  'COV',
};

const iconClasses: Record<string, string> = {
  disruption_alert:    'notif-icon-disruption',
  rebooking_confirmed: 'notif-icon-rebooking',
  approval_request:    'notif-icon-approval',
  reassurance:         'notif-icon-reassurance',
  insurance_eligible:  'notif-icon-insurance',
};

const channelLabel: Record<string, string> = {
  push: 'Push',
  sms:  'SMS',
  email:'Email',
};

interface NotificationItemProps {
  notification: Notification;
}

export function NotificationItem({ notification: n }: NotificationItemProps) {
  return (
    <div className="notif-item">
      <div className={`notif-icon ${iconClasses[n.type] ?? ''}`} aria-hidden="true">
        {icons[n.type] ?? '•'}
      </div>
      <div className="notif-body">
        <div className="notif-msg">{n.message}</div>
        <div className="notif-meta">
          <span className="mono">{fmtDateTime(n.sent_at)}</span>
          <span>·</span>
          <span>{fmtNotifType(n.type)}</span>
          <span>·</span>
          <span>{channelLabel[n.channel] ?? n.channel}</span>
        </div>
      </div>
    </div>
  );
}
