import { HistoryPageClient } from "@/components/HistoryPageClient";
import { loadCachedForecastHistory } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  try {
    return <HistoryPageClient initialRuns={await loadCachedForecastHistory()} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load forecast history";
    return <HistoryPageClient initialRuns={[]} initialError={message} />;
  }
}
