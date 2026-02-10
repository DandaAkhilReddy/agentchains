import { useEffect, useRef, useState } from "react";
import { feed } from "../lib/ws";
import type { FeedEvent } from "../types/api";

const MAX_EVENTS = 50;

export function useLiveFeed() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const started = useRef(false);

  useEffect(() => {
    if (!started.current) {
      feed.connect();
      started.current = true;
    }
    return feed.subscribe((event) => {
      setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS));
    });
  }, []);

  return events;
}
