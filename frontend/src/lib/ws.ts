import type { FeedEvent } from "../types/api";

type FeedCallback = (event: FeedEvent) => void;

class MarketplaceFeed {
  private ws: WebSocket | null = null;
  private listeners = new Set<FeedCallback>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private token: string | null = null;
  private connecting = false;

  setToken(token: string | null) {
    this.token = token;
  }

  private async resolveSocketUrl(protocol: string): Promise<string> {
    try {
      const response = await fetch("/api/v2/events/stream-token", {
        headers: { Authorization: `Bearer ${this.token}` },
      });
      if (response.ok) {
        const body = await response.json() as { stream_token?: string; ws_url?: string };
        if (body.stream_token) {
          const wsPath = body.ws_url || "/ws/v2/events";
          return `${protocol}//${window.location.host}${wsPath}?token=${encodeURIComponent(body.stream_token)}`;
        }
      }
    } catch {
      // fall back to legacy path for compatibility
    }

    return `${protocol}//${window.location.host}/ws/feed?token=${encodeURIComponent(this.token ?? "")}`;
  }

  private attachHandlers(ws: WebSocket) {
    ws.onmessage = (evt) => {
      try {
        const event: FeedEvent = JSON.parse(evt.data);
        this.listeners.forEach((cb) => cb(event));
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    };

    ws.onopen = () => {
      this.reconnectDelay = 1000;
    };
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING || this.connecting) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

    if (!this.token) {
      this.ws = new WebSocket(`${protocol}//${window.location.host}/ws/feed`);
      this.attachHandlers(this.ws);
      return;
    }

    this.connecting = true;
    void this.resolveSocketUrl(protocol)
      .then((url) => {
        this.ws = new WebSocket(url);
        this.attachHandlers(this.ws);
      })
      .finally(() => {
        this.connecting = false;
      });
  }

  subscribe(cb: FeedCallback) {
    this.listeners.add(cb);
    return () => {
      this.listeners.delete(cb);
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}

export const feed = new MarketplaceFeed();
