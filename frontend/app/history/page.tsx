import { HistoryPageClient } from "@/components/HistoryPageClient";
import { loadCachedForecastHistory, loadCachedMatches } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  try {
    const [runs, matches] = await Promise.all([loadCachedForecastHistory(), loadCachedMatches()]);
    return <HistoryPageClient initialRuns={runs} initialMatches={matches} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load forecast history";
    return <HistoryPageClient initialRuns={[]} initialMatches={[]} initialError={message} />;
  }
}
