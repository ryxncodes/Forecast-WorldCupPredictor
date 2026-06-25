import type { Forecast, Match, Standings } from "./types";

function defaultApiUrl() {
  if (typeof window !== "undefined") {
    const local = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
    return local ? `http://${window.location.hostname}:8000` : `${window.location.origin}/backend`;
  }
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}/backend`;
  return "http://127.0.0.1:8000";
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? defaultApiUrl();

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (options?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json();
}

export async function loadDashboard() {
  const [forecast, standings] = await Promise.all([
    request<Forecast>("/forecast/latest"),
    request<Standings>("/standings"),
  ]);
  return { forecast, standings };
}

export function loadForecastHistory() {
  // The group stage has at most 72 completed-match snapshots plus the
  // pre-tournament baseline, so 100 keeps the full replay without pagination.
  return request<Forecast[]>("/forecast/history?limit=100");
}

export function loadMatches() {
  return request<Match[]>("/matches");
}

export async function loadThirdPlacePage() {
  const [forecast, standings] = await Promise.all([
    request<Forecast>("/forecast/latest"),
    request<Standings>("/standings"),
  ]);
  return { forecast, standings };
}
