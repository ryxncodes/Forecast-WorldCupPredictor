import "server-only";
import { unstable_cache } from "next/cache";
import {
  loadAccuracy,
  loadBracket,
  loadDashboard,
  loadForecastHistory,
  loadMatches,
} from "./api";

export const loadCachedDashboard = loadDashboard;

export const loadCachedThirdPlacePage = loadCachedDashboard;

export const loadCachedForecastHistory = unstable_cache(loadForecastHistory, ["forecast-history-v3"], {
  revalidate: 60,
  tags: ["forecast-history"],
});

export const loadCachedMatches = loadMatches;

export const loadCachedBracket = loadBracket;

export const loadCachedAccuracy = unstable_cache(loadAccuracy, ["accuracy"], {
  revalidate: 180,
  tags: ["accuracy"],
});
