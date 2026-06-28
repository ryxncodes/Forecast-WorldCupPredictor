import "server-only";
import { unstable_cache } from "next/cache";
import {
  loadAccuracy,
  loadBracket,
  loadDashboard,
  loadForecastHistory,
  loadMatches,
} from "./api";

export const loadCachedDashboard = unstable_cache(loadDashboard, ["dashboard"], {
  revalidate: 60,
  tags: ["dashboard"],
});

export const loadCachedThirdPlacePage = loadCachedDashboard;

export const loadCachedForecastHistory = unstable_cache(loadForecastHistory, ["forecast-history"], {
  revalidate: 60,
  tags: ["forecast-history"],
});

export const loadCachedMatches = unstable_cache(loadMatches, ["matches-v2"], {
  revalidate: 15,
  tags: ["matches"],
});

export const loadCachedBracket = unstable_cache(loadBracket, ["bracket"], {
  revalidate: 180,
  tags: ["bracket"],
});

export const loadCachedAccuracy = unstable_cache(loadAccuracy, ["accuracy"], {
  revalidate: 180,
  tags: ["accuracy"],
});
