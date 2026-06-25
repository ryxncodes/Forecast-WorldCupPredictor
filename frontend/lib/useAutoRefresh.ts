"use client";

import { useEffect, useRef } from "react";


export function useAutoRefresh(refresh: () => void | Promise<void>, intervalMs = 60_000) {
  const inFlight = useRef(false);

  useEffect(() => {
    const refreshWhenVisible = async () => {
      if (document.visibilityState !== "visible" || inFlight.current) return;
      inFlight.current = true;
      try {
        await refresh();
      } finally {
        inFlight.current = false;
      }
    };
    const timer = window.setInterval(refreshWhenVisible, intervalMs);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [intervalMs, refresh]);
}
