import type { WsStatus } from '../hooks/useWebSocket';

interface Props {
  status: WsStatus;
}

export default function WsStatusIndicator({ status }: Props) {
  if (status === 'connected') {
    return (
      <span className="status-pill pill-live" role="status" aria-label="WebSocket connected">
        <span className="status-dot" />
        Live
      </span>
    );
  }

  if (status === 'connecting') {
    return (
      <span className="status-pill pill-connecting" role="status" aria-label="WebSocket connecting">
        <span className="status-dot" />
        Connecting
      </span>
    );
  }

  return (
    <span className="status-pill pill-offline" role="status" aria-label="WebSocket disconnected">
      <span className="status-dot" />
      Disconnected
    </span>
  );
}
