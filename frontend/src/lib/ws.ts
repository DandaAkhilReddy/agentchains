import type { FeedEvent } from "../types/api";

type FeedCallback = (event: FeedEvent) => void;

class MarketplaceFeed {
  private ws: WebSocket | null = null;
  private listeners = new Set<FeedCallback>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    this.ws = new WebSocket(`${protocol}//${window.location.host}/ws/feed`);

    this.ws.onmessage = (evt) => {
      try {
        const event: FeedEvent = JSON.parse(evt.data);
        this.listeners.forEach((cb) => cb(event));
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    };

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
    };
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
