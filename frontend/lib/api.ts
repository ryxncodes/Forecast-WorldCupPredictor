import type { AccuracyReport, Forecast, Match, Standings } from "./types";

function cleanApiUrl(value: string | undefined) {
  const trimmed = value?.trim();
  if (!trimmed || trimmed === "/") return null;
  if (trimmed.startsWith("/backend")) return trimmed.replace(/\/+$/, "");
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return null;
  }
  const url = new URL(trimmed);
  const local = ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  if (!local && !url.pathname.startsWith("/backend")) return null;
  return trimmed.replace(/\/+$/, "");
}

function defaultApiUrl() {
  if (typeof window !== "undefined") {
    const serviceUrl = cleanApiUrl(process.env.NEXT_PUBLIC_BACKEND_URL);
    if (serviceUrl) return serviceUrl;
    const local = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
    return local ? `http://${window.location.hostname}:8000` : "/backend";
  }
  const serviceUrl = cleanApiUrl(process.env.BACKEND_URL);
  if (serviceUrl) return serviceUrl;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}/backend`;
  return "http://127.0.0.1:8000";
}

function apiUrl() {
  return cleanApiUrl(process.env.NEXT_PUBLIC_API_URL) ?? defaultApiUrl();
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (options?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${apiUrl()}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(`Expected JSON from API but received ${contentType || "unknown content"}`);
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

export function loadAccuracy() {
  return request<AccuracyReport>("/accuracy");
}

export async function loadThirdPlacePage() {
  const [forecast, standings] = await Promise.all([
    request<Forecast>("/forecast/latest"),
    request<Standings>("/standings"),
  ]);
  return { forecast, standings };
}
