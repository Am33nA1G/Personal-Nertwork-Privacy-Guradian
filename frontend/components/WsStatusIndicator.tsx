import type { WsStatus } from '../hooks/useWebSocket';

interface WsStatusIndicatorProps {
  status: WsStatus;
}

export default function WsStatusIndicator({ status }: WsStatusIndicatorProps) {
  if (status === 'connected') {
    return (
      <span
        className="badge bg-success"
        aria-label="WebSocket connected"
        role="status"
      >
        &#9679; Live
      </span>
    );
  }

  if (status === 'connecting') {
    return (
      <span
        className="badge bg-warning text-dark"
        aria-label="WebSocket connecting"
        role="status"
      >
        &#8635; Connecting...
      </span>
    );
  }

  return (
    <span
      className="badge bg-danger"
      aria-label="WebSocket disconnected"
      role="status"
    >
      &#10005; Disconnected
    </span>
  );
}
